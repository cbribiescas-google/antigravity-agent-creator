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
"""Unit tests for the Gemini Antigravity ADK Agent and Token Telemetry."""

import os
from types import SimpleNamespace

import pytest
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.labs.antigravity import AntigravityAgent
from google.antigravity import LocalAgentConfig
from google.genai import types as genai_types

from app.agent import (
    MODEL,
    TelemetryAntigravityAgent,
    _detect_image_mime_type,
    _extract_generated_image_paths_from_event,
    _extract_generated_image_paths_from_steps,
    _load_generated_image_parts,
    _strip_local_tmp_image_markdown,
    app,
    root_agent,
    sdk_config,
)
from app.telemetry import (
    TokenCounts,
    derive_antigravity_conversation_id,
    resolve_conversation_ids,
)


def test_root_agent_is_telemetry_antigravity_agent() -> None:
    """Verify root_agent is a TelemetryAntigravityAgent wrapping LocalAgentConfig."""
    assert isinstance(root_agent, AntigravityAgent)
    assert isinstance(root_agent, TelemetryAntigravityAgent)
    assert root_agent.name == "gemini_antigravity_demo"
    assert root_agent.mode is None
    assert isinstance(root_agent.config, LocalAgentConfig)


def test_sdk_config_persistence_and_sandbox() -> None:
    """Verify LocalAgentConfig has save_dir, app_data_dir, and workspace configured."""
    assert sdk_config.model == MODEL
    assert sdk_config.save_dir is not None
    assert os.path.isabs(sdk_config.save_dir)
    assert os.path.isdir(sdk_config.save_dir)
    assert sdk_config.app_data_dir is not None
    assert os.path.isabs(sdk_config.app_data_dir)
    assert os.path.isdir(sdk_config.app_data_dir)
    assert len(sdk_config.workspaces) >= 1
    assert all(os.path.isabs(ws) and os.path.isdir(ws) for ws in sdk_config.workspaces)


def test_adk_app_wraps_root_agent() -> None:
    """Verify the ADK App object is properly configured for Agent Runtime."""
    assert isinstance(app, App)
    assert app.name == "app"
    assert app.root_agent is root_agent


def test_conversation_id_alignment_is_deterministic() -> None:
    """Verify a GE App conversation ID maps deterministically 1-to-1 to a 32-char Antigravity ID."""
    ge_id = "ge-session-123456789"
    ag_id_1 = derive_antigravity_conversation_id(ge_id)
    ag_id_2 = derive_antigravity_conversation_id(ge_id)
    assert ag_id_1 == ag_id_2
    assert len(ag_id_1) == 32

    ctx = SimpleNamespace(
        session=SimpleNamespace(id=ge_id, state={}, events=[]),
    )
    resolved_ge, resolved_ag = resolve_conversation_ids(ctx)
    assert resolved_ge == ge_id
    assert resolved_ag == ag_id_1


def test_token_counts_conversion() -> None:
    """Verify SDK UsageMetadata converts cleanly to TokenCounts and GenAI UsageMetadata."""
    fake_sdk_usage = SimpleNamespace(
        prompt_token_count=1000,
        cached_content_token_count=200,
        candidates_token_count=150,
        thoughts_token_count=50,
        total_token_count=1200,
    )
    counts = TokenCounts.from_sdk_usage(fake_sdk_usage)
    assert counts.prompt_tokens == 1000
    assert counts.cached_tokens == 200
    assert counts.candidates_tokens == 150
    assert counts.thoughts_tokens == 50
    assert counts.total_tokens == 1200

    genai_meta = counts.to_genai_usage_metadata()
    assert genai_meta.prompt_token_count == 1000
    assert genai_meta.cached_content_token_count == 200
    assert genai_meta.candidates_token_count == 150
    assert genai_meta.thoughts_token_count == 50
    assert genai_meta.total_token_count == 1200


@pytest.mark.asyncio
async def test_a2a_agent_card_builds_for_antigravity_agent() -> None:
    """Verify AgentCardBuilder can build a valid A2A card from TelemetryAntigravityAgent."""
    from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder

    card = await AgentCardBuilder(
        agent=root_agent,
        rpc_url="http://localhost:8000/a2a/app",
        agent_version="0.1.0",
    ).build()
    assert card.name == "gemini_antigravity_demo"
    assert "Antigravity" in card.description
    assert len(card.skills) >= 1


def test_generated_image_extraction_and_inline_part_loading(tmp_path) -> None:
    """Verify generated image files from generate_image are loaded as inline_data Parts."""
    img_file = tmp_path / "happy_dog_123.jpg"
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01test_dog_image"
    img_file.write_bytes(jpeg_bytes)

    assert _detect_image_mime_type(str(img_file), jpeg_bytes) == "image/jpeg"

    fn_resp_event = Event(
        invocation_id="inv-dog",
        author="generate_image",
        content=genai_types.Content(
            role="user",
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name="generate_image",
                        id="call-1",
                        response={
                            "image_name": "happy_dog",
                            "aspect_ratio": "1:1",
                            "output_path": str(img_file),
                        },
                    )
                )
            ],
        ),
    )
    paths_from_event = _extract_generated_image_paths_from_event(fn_resp_event)
    assert paths_from_event == [str(img_file)]

    fake_step = SimpleNamespace(
        tool_calls=[
            SimpleNamespace(
                name="generate_image",
                args={"output_path": str(img_file)},
                canonical_path=str(img_file),
            )
        ]
    )
    paths_from_steps = _extract_generated_image_paths_from_steps([fake_step])
    assert str(img_file) in paths_from_steps

    parts = _load_generated_image_parts(paths_from_event + paths_from_steps)
    assert len(parts) == 1
    assert parts[0].inline_data is not None
    assert parts[0].inline_data.mime_type == "image/jpeg"
    assert parts[0].inline_data.data == jpeg_bytes
    assert parts[0].inline_data.display_name == "happy_dog_123.jpg"


def test_strip_local_tmp_image_markdown() -> None:
    """Verify local /tmp/... markdown image tags are stripped so GE does not redact them to 'IMG'."""
    ev = Event(
        invocation_id="inv-1",
        author="gemini_antigravity_demo",
        content=genai_types.Content(
            role="model",
            parts=[
                genai_types.Part.from_text(
                    text="Here is a happy dog!\n\n![happy_dog](/tmp/antigravity_harness/app_data/brain/123/dog.jpg)"
                )
            ],
        ),
    )
    _strip_local_tmp_image_markdown(ev)
    assert ev.content.parts[0].text == "Here is a happy dog!"


def test_generated_video_extraction_and_inline_part_loading(tmp_path) -> None:
    """Verify generated MP4 video files from generate_video are loaded as video/mp4 inline_data Parts."""
    vid_file = tmp_path / "running_dog_456.mp4"
    mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomtest_video"
    vid_file.write_bytes(mp4_bytes)

    assert _detect_image_mime_type(str(vid_file), mp4_bytes) == "video/mp4"

    fn_resp_event = Event(
        invocation_id="inv-vid",
        author="generate_video",
        content=genai_types.Content(
            role="user",
            parts=[
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name="generate_video",
                        id="call-v1",
                        response={
                            "video_name": "running_dog",
                            "aspect_ratio": "16:9",
                            "duration_seconds": 4,
                            "mime_type": "video/mp4",
                            "output_path": str(vid_file),
                        },
                    )
                )
            ],
        ),
    )
    paths = _extract_generated_image_paths_from_event(fn_resp_event)
    assert paths == [str(vid_file)]

    parts = _load_generated_image_parts(paths)
    assert len(parts) == 1
    assert parts[0].inline_data is not None
    assert parts[0].inline_data.mime_type == "video/mp4"
    assert parts[0].inline_data.data == mp4_bytes
    assert parts[0].inline_data.display_name == "running_dog_456.mp4"
    tool_names = [getattr(t, "__name__", str(t)) for t in sdk_config.tools]
    assert "generate_video" in tool_names


def test_strip_large_inline_data_for_session_store_preserves_original_event() -> None:
    """Verify multi-MB video inline_data is stripped only on the session-store copy."""
    from app.app_utils.services import strip_large_inline_data_for_session_store

    big_mp4 = b"\x00\x00\x00\x18ftypmp42" + (b"x" * (512 * 1024))
    original_event = Event(
        invocation_id="inv-big-vid",
        author="gemini_antigravity_demo",
        content=genai_types.Content(
            role="model",
            parts=[
                genai_types.Part.from_text(text="Here is your video!"),
                genai_types.Part(
                    inline_data=genai_types.Blob(
                        data=big_mp4,
                        mime_type="video/mp4",
                        display_name="chicken_walk.mp4",
                    )
                ),
            ],
        ),
    )
    safe_event = strip_large_inline_data_for_session_store(original_event)
    # Original event still carries the full inline_data blob for SSE streaming to GE:
    assert original_event.content.parts[1].inline_data is not None
    assert len(original_event.content.parts[1].inline_data.data) == len(big_mp4)
    # Safe copy for VertexAiSessionService has inline_data replaced with text summary:
    assert safe_event.content.parts[1].inline_data is None
    assert "chicken_walk.mp4" in safe_event.content.parts[1].text
