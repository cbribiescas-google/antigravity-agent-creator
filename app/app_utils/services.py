# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Process-wide ADK session/artifact services shared by every serving surface.

Registered under ``shared://`` so the ADK web routes, the A2A path, and the
reasoning_engine adapter share one instance: a session created on any surface
is visible to the others.
"""

from __future__ import annotations

import functools
import os

from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.adk.cli.service_registry import get_service_registry
from google.adk.cli.utils.service_factory import create_session_service_from_options
from google.adk.events.event import Event
from google.genai import types as genai_types

SESSION_SERVICE_URI = "shared://session"
ARTIFACT_SERVICE_URI = "shared://artifact"

_MAX_INLINE_DATA_SESSION_BYTES = 256 * 1024

_AGENT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def strip_large_inline_data_for_session_store(event: Event) -> Event:
    """Returns a copy of `event` with large `inline_data` blobs replaced for VertexAiSessionService.

    `VertexAiSessionService.append_event` duplicates `event.content` into both
    `config['content']` and `config['raw_event']` and enforces a 10MB HTTP request
    payload limit (`10,486,784` bytes). Stripping large `inline_data` (such as
    multi-megabyte Veo MP4 videos) on the copy persisted to VertexAiSessionService
    leaves the original `output_event` intact for the SSE response stream to
    Gemini Enterprise.
    """
    if not event.content or not event.content.parts:
        return event
    has_large_blob = any(
        part.inline_data
        and part.inline_data.data
        and len(part.inline_data.data) > _MAX_INLINE_DATA_SESSION_BYTES
        for part in event.content.parts
    )
    if not has_large_blob:
        return event

    lightweight_parts: list[genai_types.Part] = []
    for part in event.content.parts:
        if (
            part.inline_data
            and part.inline_data.data
            and len(part.inline_data.data) > _MAX_INLINE_DATA_SESSION_BYTES
        ):
            name = part.inline_data.display_name or "media"
            mime = part.inline_data.mime_type or "application/octet-stream"
            lightweight_parts.append(
                genai_types.Part.from_text(
                    text=f"[Attached media: {name} ({mime}, {len(part.inline_data.data)} bytes)]"
                )
            )
        else:
            lightweight_parts.append(part)

    event_copy = event.model_copy(deep=False)
    event_copy.content = genai_types.Content(
        role=event.content.role,
        parts=lightweight_parts,
    )
    return event_copy


@functools.cache
def get_session_service():
    """Process-wide session service shared across every serving surface."""
    if uri := os.environ.get("SESSION_SERVICE_URI"):
        return create_session_service_from_options(
            base_dir=_AGENT_DIR, session_service_uri=uri
        )
    if agent_engine_id := os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID"):
        from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

        class LargeMediaSafeVertexAiSessionService(VertexAiSessionService):
            """Prevents 10MB payload errors when appending events with video/image inline_data."""

            async def append_event(self, session, event: Event) -> Event:
                safe_event = strip_large_inline_data_for_session_store(event)
                return await super().append_event(session=session, event=safe_event)

        return LargeMediaSafeVertexAiSessionService(
            project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            # Runtime-injected agent-engine region, not GOOGLE_CLOUD_LOCATION
            # (which agent.py pins to "global").
            location=os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION")
            or os.environ.get("GOOGLE_CLOUD_LOCATION"),
            agent_engine_id=agent_engine_id,
        )
    from google.adk.sessions.in_memory_session_service import InMemorySessionService

    return InMemorySessionService()


@functools.cache
def get_artifact_service():
    """Process-wide artifact service: GCS when a bucket is set, else in-memory."""
    if bucket := os.environ.get("LOGS_BUCKET_NAME"):
        return GcsArtifactService(bucket_name=bucket)
    return InMemoryArtifactService()


_registry = get_service_registry()
_registry.register_session_service("shared", lambda uri, **kw: get_session_service())
_registry.register_artifact_service("shared", lambda uri, **kw: get_artifact_service())
