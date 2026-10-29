# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Gemini Antigravity Demo Agent with Per-Request & Per-Conversation Token Telemetry.

Runs a Google Antigravity SDK agent (`LocalAgentConfig`) as a native ADK root
agent node (`google.adk.labs.antigravity.AntigravityAgent`) deployed to Vertex
AI Agent Runtime and registered with Gemini Enterprise.

Reference:
https://github.com/google/adk-python/blob/main/docs/guides/labs/antigravity/index.md
"""

from __future__ import annotations

import logging
import mimetypes
import os
import re
import time
from typing import Any, AsyncGenerator, Iterable

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

from google.adk.agents.invocation_context import InvocationContext
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.labs.antigravity import AntigravityAgent
from google.antigravity import LocalAgentConfig
from google.antigravity.hooks import policy
from google import genai
from google.genai import types as genai_types
from typing_extensions import override

from app.telemetry import (
    ANTIGRAVITY_CONVERSATION_ID_STATE_KEY,
    GE_CONVERSATION_ID_STATE_KEY,
    TokenCounts,
    backup_trajectory_to_gcs,
    record_turn_telemetry,
    resolve_conversation_ids,
    restore_trajectory_from_gcs,
)

logger = logging.getLogger(__name__)

_LOCAL_TMP_MARKDOWN_IMAGE_RE = re.compile(
    r"!?\[[^\]]*\]\((?:file://)?/tmp/[^)]+\)\s*"
)

_GENERATED_MEDIA_TOOL_NAMES = frozenset(
    {"generate_image", "generate_video", "generate_video_clip"}
)
_pending_generated_video_paths: list[str] = []


def _drain_pending_generated_video_paths() -> list[str]:
    """Drains local file paths recorded directly by `generate_video` during a turn."""
    if not _pending_generated_video_paths:
        return []
    paths = list(_pending_generated_video_paths)
    _pending_generated_video_paths.clear()
    return paths


def _detect_image_mime_type(path: str, data: bytes) -> str:
    """Detects the IANA image or video MIME type from magic bytes or file extension."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    guessed, _ = mimetypes.guess_type(path)
    if guessed and (guessed.startswith("image/") or guessed.startswith("video/")):
        return guessed
    if path.lower().endswith(".mp4"):
        return "video/mp4"
    return "image/jpeg"


def _extract_generated_image_paths_from_event(event: Event) -> list[str]:
    """Extracts local file paths produced by `generate_image` or `generate_video` FunctionResponse events."""
    paths: list[str] = []
    if not event.content or not event.content.parts:
        return paths
    for part in event.content.parts:
        fn_resp = getattr(part, "function_response", None)
        if (
            fn_resp is None
            or getattr(fn_resp, "name", None) not in _GENERATED_MEDIA_TOOL_NAMES
        ):
            continue
        resp_dict = getattr(fn_resp, "response", None)
        if isinstance(resp_dict, dict):
            output_path = resp_dict.get("output_path")
            if isinstance(output_path, str) and output_path:
                paths.append(output_path)
    return paths


def _extract_generated_image_paths_from_steps(steps: Iterable[Any]) -> list[str]:
    """Extracts local file paths from completed `generate_image` or `generate_video` trajectory steps."""
    paths: list[str] = []
    for step in steps:
        tool_calls = getattr(step, "tool_calls", None) or []
        for call in tool_calls:
            if getattr(call, "name", None) not in _GENERATED_MEDIA_TOOL_NAMES:
                continue
            args = getattr(call, "args", None)
            if isinstance(args, dict):
                output_path = args.get("output_path")
                if isinstance(output_path, str) and output_path:
                    paths.append(output_path)
            canonical_path = getattr(call, "canonical_path", None)
            if isinstance(canonical_path, str) and canonical_path:
                paths.append(canonical_path)
    return paths


def _load_generated_image_parts(paths: Iterable[str]) -> list[genai_types.Part]:
    """Reads generated image/video files from disk into ADK `inline_data` `Part`s."""
    parts: list[genai_types.Part] = []
    seen: set[str] = set()
    for raw_path in paths:
        if not raw_path:
            continue
        abs_path = os.path.abspath(raw_path)
        if abs_path in seen or not os.path.isfile(abs_path):
            continue
        seen.add(abs_path)
        try:
            with open(abs_path, "rb") as f:
                media_bytes = f.read()
            if not media_bytes:
                continue
            mime_type = _detect_image_mime_type(abs_path, media_bytes)
            parts.append(
                genai_types.Part(
                    inline_data=genai_types.Blob(
                        data=media_bytes,
                        mime_type=mime_type,
                        display_name=os.path.basename(abs_path),
                    )
                )
            )
        except Exception as exc:
            logger.warning("Failed to read generated media at %s: %s", abs_path, exc)
    return parts


def _strip_local_tmp_image_markdown(event: Event) -> None:
    """Removes local `/tmp/...` Markdown media links that GE's sanitizer cannot load."""
    if not event.content or not event.content.parts:
        return
    for part in event.content.parts:
        if part.text and "/tmp/" in part.text:
            cleaned = _LOCAL_TMP_MARKDOWN_IMAGE_RE.sub("", part.text).strip()
            part.text = cleaned or "Here is the generated media:"


def _collect_turn_text_artifacts_markdown(
    turn_start_epoch: float, existing_text: str
) -> str:
    """Appends newly written `.html` / `.ics` workspace files as fenced blocks in Agent Runtime."""
    if not os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"):
        return ""
    if not os.path.isdir(_WORKSPACE_DIR):
        return ""
    snippets: list[str] = []
    try:
        entries = sorted(os.listdir(_WORKSPACE_DIR))
    except OSError:
        return ""
    for fname in entries:
        lower = fname.lower()
        if not (lower.endswith(".html") or lower.endswith(".ics")):
            continue
        fpath = os.path.join(_WORKSPACE_DIR, fname)
        try:
            st = os.stat(fpath)
            if not os.path.isfile(fpath) or st.st_mtime < (turn_start_epoch - 1.0):
                continue
            if st.st_size == 0 or st.st_size > 200_000:
                continue
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().strip()
        except OSError:
            continue
        if not content:
            continue
        if lower.endswith(".html") and "```html" not in existing_text.lower():
            snippets.append(f"\n\n### `{fname}`\n```html\n{content}\n```")
        elif lower.endswith(".ics") and "BEGIN:VCALENDAR" not in existing_text:
            snippets.append(f"\n\n### `{fname}`\n```ics\n{content}\n```")
    return "".join(snippets)

# Ensure Vertex AI global endpoint is configured by default for Gemini 3.7
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")
os.environ.setdefault(
    "SHARED_AGENT_BUCKET",
    f"{os.environ.get('GOOGLE_CLOUD_PROJECT', 'gemini-enterprise-demo-cb')}-agents-shared",
)
_SHARED_AGENT_BUCKET = os.environ["SHARED_AGENT_BUCKET"]

MODEL = "gemini-3.7-flash"
VEO_MODELS = (
    "veo-3.1-lite-generate-001",
    "veo-3.1-fast-generate-001",
    "veo-3.1-generate-001",
)

# Configure writable sandbox directories for the Antigravity local harness.
# Using /tmp/antigravity_harness by default ensures full read/write permissions both
# locally and inside Vertex AI Agent Runtime / Cloud Run containers.
_BASE_DIR = os.path.abspath(
    os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness")
)
_WORKSPACE_DIR = os.path.abspath(
    os.environ.get("ANTIGRAVITY_WORKSPACE_DIR", os.path.join(_BASE_DIR, "sandbox"))
)
_TRAJECTORIES_DIR = os.path.abspath(
    os.environ.get(
        "ANTIGRAVITY_TRAJECTORIES_DIR", os.path.join(_BASE_DIR, "trajectories")
    )
)
_APP_DATA_DIR = os.path.abspath(
    os.environ.get("ANTIGRAVITY_APP_DATA_DIR", os.path.join(_BASE_DIR, "app_data"))
)
_VIDEOS_DIR = os.path.abspath(
    os.environ.get("ANTIGRAVITY_VIDEOS_DIR", os.path.join(_APP_DATA_DIR, "videos"))
)

os.makedirs(_WORKSPACE_DIR, exist_ok=True)
os.makedirs(_TRAJECTORIES_DIR, exist_ok=True)
os.makedirs(_APP_DATA_DIR, exist_ok=True)
os.makedirs(_VIDEOS_DIR, exist_ok=True)


def generate_video(
    prompt: str,
    video_name: str = "generated_video",
    aspect_ratio: str = "16:9",
    duration_seconds: int = 4,
) -> dict[str, Any]:
    """Generates an MP4 video clip from a text prompt using Vertex AI Veo 3.1.

    Use this tool whenever the user asks to generate, create, or animate a video.
    The generated MP4 video is automatically attached inline to your response in
    Gemini Enterprise.

    Args:
        prompt: Detailed visual description of the video scene, subject, motion, lighting, and camera movement.
        video_name: Short snake_case name for the video file (up to 3 words, e.g. 'playful_golden_retriever').
        aspect_ratio: Video aspect ratio, either '16:9' (landscape, default) or '9:16' (portrait).
        duration_seconds: Video duration in seconds (4, 6, or 8; default 4).
    """
    safe_name = (
        re.sub(r"[^a-z0-9_]+", "_", (video_name or "generated_video").lower()).strip("_")
        or "generated_video"
    )
    valid_aspect = aspect_ratio if aspect_ratio in ("16:9", "9:16") else "16:9"
    try:
        dur = int(duration_seconds)
    except (TypeError, ValueError):
        dur = 4
    if dur >= 8:
        valid_duration = 8
    elif dur >= 6:
        valid_duration = 6
    else:
        valid_duration = 4

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb")
    veo_location = os.environ.get("VEO_LOCATION", "us-central1")
    client = genai.Client(vertexai=True, project=project, location=veo_location)

    last_error: Exception | str | None = None
    for veo_model in VEO_MODELS:
        try:
            operation = client.models.generate_videos(
                model=veo_model,
                source=genai_types.GenerateVideosSource(prompt=prompt),
                config=genai_types.GenerateVideosConfig(
                    aspect_ratio=valid_aspect,
                    duration_seconds=valid_duration,
                    number_of_videos=1,
                ),
            )
            deadline = time.monotonic() + 180.0
            while not operation.done and time.monotonic() < deadline:
                time.sleep(2.0)
                operation = client.operations.get(operation)

            if not operation.done:
                last_error = f"Video generation timed out on model {veo_model}"
                continue
            if operation.error:
                last_error = str(operation.error)
                continue

            generated_videos = (
                getattr(operation.result, "generated_videos", None)
                if operation.result
                else None
            )
            if not generated_videos:
                last_error = f"No video returned by {veo_model}"
                continue

            video_obj = generated_videos[0].video
            video_bytes = getattr(video_obj, "video_bytes", None)
            if not video_bytes:
                last_error = f"Empty video_bytes returned by {veo_model}"
                continue

            os.makedirs(_VIDEOS_DIR, exist_ok=True)
            filename = f"{safe_name}_{int(time.time() * 1000)}.mp4"
            output_path = os.path.join(_VIDEOS_DIR, filename)
            with open(output_path, "wb") as f:
                f.write(video_bytes)

            _pending_generated_video_paths.append(output_path)
            return {
                "video_name": safe_name,
                "model": veo_model,
                "aspect_ratio": valid_aspect,
                "duration_seconds": valid_duration,
                "mime_type": "video/mp4",
                "output_path": output_path,
            }
        except Exception as exc:
            logger.warning("Veo model %s failed: %s", veo_model, exc)
            last_error = exc

    raise RuntimeError(f"Video generation failed: {last_error}")


SYSTEM_INSTRUCTIONS = f"""\
You are the **Gemini Antigravity Agent**, an autonomous AI software engineer, \
researcher, and problem-solver powered by the Google Antigravity SDK harness \
running inside Google ADK and Gemini Enterprise.

### Capabilities & Operating Environment
- **Sandbox Workspace**: `{_WORKSPACE_DIR}`
- **Private Shared Agent GCS Bucket**: `gs://{_SHARED_AGENT_BUCKET}` (accessible to all agents via `google-cloud-storage` or `gcloud storage`, with Public Access Prevention enforced)
- **Built-in & Custom Harness Tools**:
  - **File Operations** (`view_file`, `create_file`, `edit_file`): Create, inspect, and iteratively edit code, scripts, markdown reports, HTML apps, and data files inside `{_WORKSPACE_DIR}`. Always use clean absolute paths inside `{_WORKSPACE_DIR}`.
  - **Shell Execution** (`run_command`): Run bash commands, Python scripts, tests, data analysis, and CLI tools to verify your work and compute exact answers.
  - **Web Research** (`search_web`, `read_url_content`): Search the live web and read full web pages or documentation when answering research questions.
  - **Sub-Agent & Workflow Orchestration** (`invoke_subagent`, `run_workflow`): Delegate parallel research or specialized sub-tasks when tackling complex multi-step problems.
  - **Image Generation** (`generate_image`): Generate or edit visual image assets when requested.
  - **Video Generation** (`generate_video`): Generate MP4 video clips using Vertex AI Veo 3.1 when asked to generate, create, or animate a video.
  - **Agent Builder & Dynamic Tool Synthesis** (`list_registered_agents_and_tools`, `create_custom_tool`, `build_custom_agent`):
    - `list_registered_agents_and_tools()`: Inspect all available built-in tools, pre-built `SCENARIO_TOOLS`, dynamically synthesized Python tools, and currently registered Custom Agents.
    - `create_custom_tool(tool_name, description, python_code)`: Dynamically synthesize, AST-validate, persist (`app/dynamic_tools/<tool_name>.py`), and live-register a brand-new Python tool callable with explicit type hints so newly built agents can immediately use it.
    - `build_custom_agent(agent_id, display_name, description, dag_topology, system_instructions, tool_names, dag_nodes_json="[]", dag_edges_json="[]", enable_subagents=False, subagent_specs_json="[]")`: Compile and register a real Antigravity Custom Agent (`agents/<agent_id>.md` + `agents/registry/<agent_id>.json`) immediately runnable on the Single API Gateway.

### Guidelines
1. Be proactive and action-oriented: when asked to write code, analyze data, test a script, or research a topic, use your Antigravity harness tools to actually execute, verify, and produce concrete results.
2. When asked to **create a custom Python tool** or **build/register a Custom Agent (or DAG Agent)**, ALWAYS use `create_custom_tool` and `build_custom_agent` (calling `list_registered_agents_and_tools` first if you need to check exact tool names) — do NOT manually write `.md` or `.py` files with `create_file` as a substitute for `create_custom_tool` / `build_custom_agent`.
3. Keep all regular sandbox file creation and edits strictly within `{_WORKSPACE_DIR}`.
4. When you call `generate_image` or `generate_video`, the generated image or MP4 video file is automatically attached inline to your response for the user — do NOT include local `/tmp/...` Markdown links (`![...](/tmp/...)` or `[...](/tmp/...)`) in your text reply.
5. Present clear, well-structured Markdown responses summarizing the actions taken, outputs verified, and final deliverables.
6. **Interactive Workshop Agent Design Modes** (when a user wants to design or build one of the 5 showcase agents — `trailer-director`, `shark-tank-panel`, `food-crawl-planner`, `arcade-builder`, `six-degrees-detective` — or their own custom agent):
   - **Option 1 (Interactive Walkthrough -> BRD -> Build)**: Interview the user interactively with 2–3 fun, concrete multiple-choice or short-answer questions at a time to gather their preferences, draft a crisp Business & Technical Requirements Doc (BRD) for confirmation, and then compile it via `build_custom_agent` (and `create_custom_tool` if needed).
   - **Option 2 (Skeleton Fill-in-the-Blanks BRD)**: Present a structured "Mad-Libs" Skeleton BRD with `[BLANKS]` for the fun persona/constraint choices while keeping the underlying DAG tools intact, then compile once they fill it in.
   - **Option 3 (Bring Your Own Idea — Blank BRD or Freestyle)**: Offer either a Blank BRD template or take their freestyle idea, propose a multi-step DAG topology + tools, and build it via `build_custom_agent`.
"""


class TelemetryAntigravityAgent(AntigravityAgent):
    """Extends `AntigravityAgent` with 1-to-1 GE App conversation alignment and token telemetry."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if self.mode == "single_turn":
            async for event in super()._run_async_impl(ctx):
                yield event
            return

        start_t = time.perf_counter()
        turn_start_epoch = time.time()
        ge_conv_id, ag_conv_id = resolve_conversation_ids(ctx)
        prompt_text = self._extract_user_prompt(ctx)
        user_id = getattr(ctx, "user_id", None) or getattr(
            ctx.session, "user_id", "default_user"
        )

        save_dir = getattr(self.config, "save_dir", None) or _TRAJECTORIES_DIR
        restore_trajectory_from_gcs(ag_conv_id, save_dir)

        _drain_pending_generated_video_paths()
        active = await self._enter_sdk_agent(ag_conv_id)
        buffered_events: list[Event] = []
        generated_image_paths: list[str] = []

        try:
            async with active:
                prior_history_len = len(active.agent.conversation.history)
                prior_model_responses = sum(
                    1
                    for s in active.agent.conversation.history
                    if getattr(s, "is_complete_response", False)
                )
                turn_number = max(
                    int(ctx.session.state.get("antigravity_turn_count", 0) or 0) + 1,
                    prior_model_responses + 1,
                )

                async for event in self._run_turn(active, ctx):
                    generated_image_paths.extend(
                        _extract_generated_image_paths_from_event(event)
                    )
                    _strip_local_tmp_image_markdown(event)
                    # Yield intermediate/partial events immediately for low-latency streaming,
                    # and hold the final completed model text event briefly so we can stamp
                    # the completed turn's usage_metadata, custom_metadata, and state_delta on it.
                    if buffered_events:
                        yield buffered_events.pop(0)
                    buffered_events.append(event)

                generated_image_paths.extend(
                    _extract_generated_image_paths_from_steps(
                        active.agent.conversation.history[prior_history_len:]
                    )
                )
                generated_image_paths.extend(_drain_pending_generated_video_paths())
                image_parts = _load_generated_image_parts(generated_image_paths)

                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                actual_ag_conv_id = active.agent.conversation_id or ag_conv_id

                last_turn_usage = active.agent.conversation.last_turn_usage
                total_usage = active.agent.conversation.total_usage
                request_counts = TokenCounts.from_sdk_usage(
                    last_turn_usage if last_turn_usage is not None else total_usage
                )
                conversation_counts = TokenCounts.from_sdk_usage(total_usage)
                traj_usages = active.agent.conversation.trajectory_usages

                telemetry_record = record_turn_telemetry(
                    ge_conversation_id=ge_conv_id,
                    antigravity_conversation_id=actual_ag_conv_id,
                    request_invocation_id=ctx.invocation_id,
                    user_id=str(user_id),
                    model=str(getattr(self.config, "model", None) or MODEL),
                    prompt_text=prompt_text,
                    turn_number=turn_number,
                    request_counts=request_counts,
                    conversation_counts=conversation_counts,
                    trajectory_usages=traj_usages,
                    latency_ms=elapsed_ms,
                )

                state_delta = {
                    self._conversation_id_state_key(): actual_ag_conv_id,
                    ANTIGRAVITY_CONVERSATION_ID_STATE_KEY: actual_ag_conv_id,
                    GE_CONVERSATION_ID_STATE_KEY: ge_conv_id,
                    "antigravity_turn_count": turn_number,
                    "antigravity_last_request_tokens": request_counts.to_dict(),
                    "antigravity_conversation_tokens": conversation_counts.to_dict(),
                }

                if buffered_events:
                    final_event = buffered_events.pop(0)
                    _strip_local_tmp_image_markdown(final_event)
                    if (
                        final_event.author == self.name
                        and final_event.content
                        and final_event.content.role == "model"
                    ):
                        existing_text = "\n".join(
                            p.text for p in (final_event.content.parts or []) if p.text
                        )
                        extra_md = _collect_turn_text_artifacts_markdown(
                            turn_start_epoch, existing_text
                        )
                        if extra_md:
                            parts_list = list(final_event.content.parts or [])
                            if parts_list and parts_list[-1].text:
                                parts_list[-1].text = parts_list[-1].text + extra_md
                            else:
                                parts_list.append(genai_types.Part(text=extra_md.lstrip()))
                            final_event.content.parts = parts_list
                    if image_parts:
                        if (
                            final_event.author == self.name
                            and final_event.content
                            and final_event.content.role == "model"
                        ):
                            final_event.content.parts = list(
                                final_event.content.parts or []
                            ) + image_parts
                        else:
                            yield final_event
                            final_event = Event(
                                invocation_id=ctx.invocation_id,
                                author=self.name,
                                branch=ctx.branch,
                                content=genai_types.Content(
                                    role="model",
                                    parts=image_parts,
                                ),
                            )
                    final_event.usage_metadata = (
                        request_counts.to_genai_usage_metadata()
                    )
                    final_event.custom_metadata = telemetry_record
                    if final_event.actions and final_event.actions.state_delta:
                        final_event.actions.state_delta.update(state_delta)
                    else:
                        final_event.actions = EventActions(state_delta=state_delta)
                    yield final_event
                else:
                    yield Event(
                        invocation_id=ctx.invocation_id,
                        author=self.name,
                        branch=ctx.branch,
                        content=(
                            genai_types.Content(role="model", parts=image_parts)
                            if image_parts
                            else None
                        ),
                        usage_metadata=request_counts.to_genai_usage_metadata(),
                        custom_metadata=telemetry_record,
                        actions=EventActions(state_delta=state_delta),
                    )
        finally:
            backup_trajectory_to_gcs(ag_conv_id, save_dir)


from app.agent_builder import (
    ROOT_AGENT_ALIASES,
    build_custom_agent,
    build_local_agent_config,
    create_custom_tool,
    ensure_localharness_env,
    list_agents_catalog,
    list_registered_agents_and_tools,
)

# 1. Configure the Antigravity SDK agent.
sdk_config = LocalAgentConfig(
    model=MODEL,
    vertex=os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").lower()
    in ("true", "1"),
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    system_instructions=SYSTEM_INSTRUCTIONS,
    tools=[
        generate_video,
        create_custom_tool,
        build_custom_agent,
        list_registered_agents_and_tools,
    ],
    workspaces=[_WORKSPACE_DIR],
    env=ensure_localharness_env(),
    policies=[
        policy.allow_all(),
        *policy.workspace_only([_WORKSPACE_DIR]),
    ],
    save_dir=_TRAJECTORIES_DIR,
    app_data_dir=_APP_DATA_DIR,
)


def _create_target_root_agent() -> TelemetryAntigravityAgent:
    """Builds the ADK root agent for either root `antigravity` or a specific custom agent."""
    target_id = os.environ.get("ANTIGRAVITY_TARGET_AGENT_ID", "antigravity").strip()
    if not target_id or target_id.lower() in ROOT_AGENT_ALIASES:
        return TelemetryAntigravityAgent(
            name="gemini_antigravity_demo",
            description=(
                "Autonomous AI agent powered by the Google Antigravity SDK harness inside "
                "ADK — equipped with sandboxed workspace file tools, shell command execution, "
                "web search, URL reading, sub-agent delegation, image generation, Veo 3.1 "
                "video generation, interactive BRD agent design, and dynamic tool creation."
            ),
            config=sdk_config,
        )

    target_cfg = build_local_agent_config(target_id)
    catalog_entry = next(
        (a for a in list_agents_catalog() if a.get("agent_id") == target_id),
        {},
    )
    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", target_id).strip("_") or "custom_agent"
    if not safe_name[0].isalpha():
        safe_name = f"agent_{safe_name}"
    desc = str(
        catalog_entry.get("description")
        or f"Custom Antigravity DAG agent ({target_id})."
    )
    return TelemetryAntigravityAgent(
        name=safe_name,
        description=desc,
        config=target_cfg,
    )


# 2. Wrap the Antigravity SDK config as a standalone ADK root agent with telemetry.
root_agent = _create_target_root_agent()

app = App(
    root_agent=root_agent,
    name="app",
)
