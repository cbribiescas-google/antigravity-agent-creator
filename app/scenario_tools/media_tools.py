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

"""Media generation and multimodal vision critique tools for Agentic DAG scenarios.

Provides Vertex AI Veo 3.1 video clip generation (`generate_video_clip`) with
model fallback and inline attachment support, plus structured draft image critique
logging (`log_vision_critique`) for iterative visual refinement loops (Scenario #1
Trailer Director and Scenario #6 Perfectionist Art Director).
"""

import json
import logging
import os
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from typing import Any

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

VEO_MODELS: tuple[str, ...] = (
    "veo-3.1-lite-generate-001",
    "veo-3.1-fast-generate-001",
    "veo-3.1-generate-001",
)


def _resolve_videos_dir() -> str:
    """Resolves and creates the output directory for generated MP4 video clips."""
    base_dir = os.environ.get("ANTIGRAVITY_BASE_DIR") or "/tmp/antigravity_harness"
    app_data_dir = os.environ.get("ANTIGRAVITY_APP_DATA_DIR") or os.path.join(
        base_dir, "app_data"
    )
    videos_dir = os.path.abspath(
        os.environ.get("ANTIGRAVITY_VIDEOS_DIR")
        or os.path.join(app_data_dir, "videos")
    )
    os.makedirs(videos_dir, exist_ok=True)
    return videos_dir


def _resolve_sandbox_dir() -> str:
    """Resolves and creates the Antigravity sandbox workspace directory."""
    base_dir = os.environ.get("ANTIGRAVITY_BASE_DIR") or "/tmp/antigravity_harness"
    sandbox_dir = os.path.abspath(
        os.environ.get("ANTIGRAVITY_WORKSPACE_DIR")
        or os.path.join(base_dir, "sandbox")
    )
    os.makedirs(sandbox_dir, exist_ok=True)
    return sandbox_dir


def _normalize_snake_case(raw_name: str, default: str = "trailer_clip") -> str:
    """Normalizes an arbitrary clip name into a filesystem-safe snake_case identifier."""
    candidate = (raw_name or "").strip()
    if not candidate:
        return default
    candidate = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", candidate)
    normalized = re.sub(r"[^a-z0-9_]+", "_", candidate.lower()).strip("_")
    return normalized or default


def generate_video_clip(
    prompt: str,
    clip_name: str = "trailer_clip",
    aspect_ratio: str = "16:9",
    duration_seconds: int = 4,
) -> dict[str, Any]:
    """Generates an MP4 video clip from a visual prompt using Vertex AI Veo 3.1.

    Attempts fast generation first with `veo-3.1-lite-generate-001`, falling back
    automatically to `veo-3.1-fast-generate-001` and `veo-3.1-generate-001` if
    unavailable or rate-limited. Saves the resulting MP4 into the Antigravity
    videos directory and registers the path for inline UI rendering.

    Args:
        prompt: Detailed visual prompt describing subject, camera motion, lighting,
            atmosphere, and action for the video clip.
        clip_name: Short snake_case base name for the saved MP4 file (e.g.,
            "opening_neon_skyline" or "trailer_clip").
        aspect_ratio: Target video aspect ratio, either "16:9" (landscape, default)
            or "9:16" (portrait). Invalid values normalize to "16:9".
        duration_seconds: Clip duration in seconds (4, 6, or 8; default 4). Other
            integers are normalized to the nearest supported duration bucket.

    Returns:
        A dictionary containing generation metadata and file details:
            - status: "generated" when the MP4 file has been written.
            - clip_name: Normalized snake_case clip identifier.
            - video_name: Normalized snake_case clip identifier (alias for compatibility).
            - model: The Veo 3.1 model ID that produced the video.
            - aspect_ratio: Normalized aspect ratio ("16:9" or "9:16").
            - duration_seconds: Normalized duration in seconds (4, 6, or 8).
            - mime_type: "video/mp4".
            - output_path: Absolute path to the saved MP4 file on disk.
            - byte_size: Size of the written MP4 file in bytes.
    """
    if not prompt or not str(prompt).strip():
        raise ValueError("prompt must be a non-empty string.")

    safe_name = _normalize_snake_case(clip_name, default="trailer_clip")
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

    videos_dir = _resolve_videos_dir()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or "gemini-enterprise-demo-cb"
    veo_location = os.environ.get("VEO_LOCATION") or "us-central1"
    client = genai.Client(vertexai=True, project=project, location=veo_location)

    last_error: Any = None
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
            while not getattr(operation, "done", False) and time.monotonic() < deadline:
                time.sleep(2.0)
                operation = client.operations.get(operation)

            if not getattr(operation, "done", False):
                last_error = f"Video generation timed out on model {veo_model}"
                continue
            if getattr(operation, "error", None):
                last_error = str(operation.error)
                continue

            op_result = getattr(operation, "result", None) or getattr(
                operation, "response", None
            )
            generated_videos = (
                getattr(op_result, "generated_videos", None) if op_result else None
            )
            if not generated_videos:
                last_error = f"No video returned by {veo_model}"
                continue

            video_obj = getattr(generated_videos[0], "video", None)
            video_bytes = (
                getattr(video_obj, "video_bytes", None)
                if video_obj is not None
                else None
            )
            if not video_bytes:
                last_error = f"Empty video_bytes returned by {veo_model}"
                continue

            os.makedirs(videos_dir, exist_ok=True)
            filename = f"{safe_name}_{int(time.time() * 1000)}.mp4"
            output_path = os.path.join(videos_dir, filename)
            with open(output_path, "wb") as f:
                f.write(video_bytes)

            agent_mod = sys.modules.get("app.agent")
            if agent_mod is not None:
                pending_paths = getattr(
                    agent_mod, "_pending_generated_video_paths", None
                )
                if isinstance(pending_paths, list):
                    pending_paths.append(output_path)

            return {
                "status": "generated",
                "clip_name": safe_name,
                "video_name": safe_name,
                "model": veo_model,
                "aspect_ratio": valid_aspect,
                "duration_seconds": valid_duration,
                "mime_type": "video/mp4",
                "output_path": output_path,
                "byte_size": len(video_bytes),
            }
        except Exception as exc:
            logger.warning("Veo model %s failed: %s", veo_model, exc)
            last_error = exc

    raise RuntimeError(f"Video generation failed: {last_error}")


def log_vision_critique(
    draft_image_path: str,
    composition_score: int,
    lighting_score: int,
    flaws_found: str,
    upgraded_prompt: str,
) -> dict[str, Any]:
    """Logs a structured multimodal vision critique of a draft image and computes revision status.

    Used in Scenario #1 (Trailer Director) and Scenario #6 (Perfectionist Art
    Director) after inspecting a generated draft image. Clamps composition and
    lighting scores to `[0, 10]`, flags `needs_revision=True` whenever either score
    is strictly below 8, and persists the critique record to
    `<sandbox_dir>/vision_critiques.json`.

    Args:
        draft_image_path: Absolute path or sandbox-relative path to the inspected
            draft image file.
        composition_score: Integer composition quality rating on a 0-10 scale
            (clamped to `[0, 10]`).
        lighting_score: Integer lighting and color grading rating on a 0-10 scale
            (clamped to `[0, 10]`).
        flaws_found: Concise description of visual, anatomical, framing, or
            lighting flaws observed in the draft image (or "none" if clean).
        upgraded_prompt: Improved image/video generation prompt incorporating fixes
            for the identified flaws.

    Returns:
        A dictionary containing the normalized critique record and revision verdict:
            - status: "logged".
            - draft_image_path: Resolved absolute path to the draft image.
            - file_exists: Whether the draft image currently exists on disk.
            - byte_size: File size in bytes (0 if the file does not exist).
            - composition_score: Clamped integer composition score in `[0, 10]`.
            - lighting_score: Clamped integer lighting score in `[0, 10]`.
            - average_score: Mean of composition and lighting scores rounded to 2 decimals.
            - needs_revision: True if `composition_score < 8` or `lighting_score < 8`.
            - flaws_found: Recorded flaws description string.
            - upgraded_prompt: Recorded upgraded prompt string.
            - critique_log_path: Absolute path to `<sandbox_dir>/vision_critiques.json`.
            - timestamp: ISO-8601 UTC timestamp of the critique entry.
    """
    sandbox_dir = _resolve_sandbox_dir()

    cleaned_path = (draft_image_path or "").strip()
    if cleaned_path.startswith("file://"):
        cleaned_path = cleaned_path[len("file://") :]

    if not cleaned_path:
        resolved_path = os.path.join(sandbox_dir, "unspecified_draft_image")
    elif os.path.isabs(cleaned_path):
        resolved_path = os.path.abspath(cleaned_path)
    else:
        resolved_path = os.path.abspath(os.path.join(sandbox_dir, cleaned_path))

    exists = os.path.isfile(resolved_path)
    byte_size = 0
    if exists:
        try:
            byte_size = os.path.getsize(resolved_path)
        except OSError:
            exists = False
            byte_size = 0

    try:
        raw_comp = round(float(composition_score))
    except (TypeError, ValueError):
        raw_comp = 0
    try:
        raw_light = round(float(lighting_score))
    except (TypeError, ValueError):
        raw_light = 0

    comp = max(0, min(10, raw_comp))
    light = max(0, min(10, raw_light))
    average_score = round((comp + light) / 2.0, 2)
    needs_revision = bool(comp < 8 or light < 8)

    critique_log_path = os.path.join(sandbox_dir, "vision_critiques.json")
    iso_ts = datetime.now(UTC).isoformat()

    record: dict[str, Any] = {
        "status": "logged",
        "draft_image_path": resolved_path,
        "file_exists": exists,
        "byte_size": byte_size,
        "composition_score": comp,
        "lighting_score": light,
        "average_score": average_score,
        "needs_revision": needs_revision,
        "flaws_found": "" if flaws_found is None else str(flaws_found),
        "upgraded_prompt": "" if upgraded_prompt is None else str(upgraded_prompt),
        "critique_log_path": critique_log_path,
        "timestamp": iso_ts,
    }

    critiques: list[dict[str, Any]] = []
    if os.path.isfile(critique_log_path):
        try:
            with open(critique_log_path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                critiques = loaded
        except (OSError, json.JSONDecodeError):
            critiques = []

    critiques.append(record)

    fd, tmp_path = tempfile.mkstemp(
        prefix=".vision_critiques_", suffix=".json", dir=sandbox_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(critiques, tmp_file, indent=2)
        os.replace(tmp_path, critique_log_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    return dict(record)
