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

"""Telemetry, token accounting, and GE App conversation alignment for AntigravityAgent.

Ensures:
1. 1-to-1 alignment between a Gemini Enterprise (GE) App conversation and the
   underlying Antigravity SDK `conversation_id` across all turns.
2. Durable trajectory persistence in GCS so conversation history and cumulative
   token counts survive container restarts or instance scaling.
3. Per-request (turn) and per-conversation (cumulative) token usage tracking
   exported to:
   - ADK Event (`usage_metadata` and `custom_metadata`)
   - OpenTelemetry / Cloud Trace spans (`gen_ai.usage.*` & `antigravity.*`)
   - Cloud Logging structured JSON logs (`event_type="ANTIGRAVITY_TOKEN_USAGE"`)
   - BigQuery (`<project>.antigravity_telemetry.token_usage`)
"""

from __future__ import annotations

import contextvars
import dataclasses
import datetime
import json
import logging
import os
import uuid
from typing import Any

from google.genai import types as genai_types
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("gemini_antigravity_demo.telemetry")

# Context variable populated by reasoning_engine_adapter.py when Gemini Enterprise
# sends a session_id in `streaming_agent_run_with_events` or `async_stream_query`.
incoming_ge_session_id_var: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("incoming_ge_session_id", default=None)
)

GE_CONVERSATION_ID_STATE_KEY = "ge_conversation_id"
ANTIGRAVITY_CONVERSATION_ID_STATE_KEY = (
    "_antigravity_conversation_id_gemini_antigravity_demo"
)


@dataclasses.dataclass(frozen=True)
class TokenCounts:
    """Normalized token counts for a single turn or cumulative conversation."""

    prompt_tokens: int = 0
    cached_tokens: int = 0
    candidates_tokens: int = 0
    thoughts_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_sdk_usage(cls, usage: Any | None) -> TokenCounts:
        if usage is None:
            return cls()
        return cls(
            prompt_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            cached_tokens=int(getattr(usage, "cached_content_token_count", 0) or 0),
            candidates_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            thoughts_tokens=int(getattr(usage, "thoughts_token_count", 0) or 0),
            total_tokens=int(getattr(usage, "total_token_count", 0) or 0),
        )

    def to_dict(self) -> dict[str, int]:
        return dataclasses.asdict(self)

    def to_genai_usage_metadata(
        self,
    ) -> genai_types.GenerateContentResponseUsageMetadata:
        return genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=self.prompt_tokens,
            cached_content_token_count=self.cached_tokens,
            candidates_token_count=self.candidates_tokens,
            thoughts_token_count=self.thoughts_tokens,
            total_token_count=self.total_tokens,
        )


def derive_antigravity_conversation_id(ge_conversation_id: str) -> str:
    """Derives a deterministic 32-char hex Antigravity conversation_id from a GE App session ID.

    `LocalAgentConfig` requires `conversation_id` to be >= 32 characters (`uuid.hex`).
    Using UUIDv5 guarantees a deterministic 1-to-1 bijection between a Gemini
    Enterprise App conversation (`ge_conversation_id`) and the Antigravity harness
    trajectory (`<antigravity_conversation_id>.db`).
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"ge-conversation:{ge_conversation_id}").hex


def resolve_conversation_ids(ctx: Any) -> tuple[str, str]:
    """Resolves `(ge_conversation_id, antigravity_conversation_id)` for the active turn.

    Checks in priority order:
    1. `ctx.session.state` (`ge_conversation_id` / `_antigravity_conversation_id_...`)
    2. Prior events in `ctx.session.events` (`custom_metadata` or `actions.state_delta`)
    3. `incoming_ge_session_id_var` captured at the HTTP adapter boundary from GE
    4. `ctx.session.id`
    """
    ge_conv_id: str | None = None
    ag_conv_id: str | None = None

    state = getattr(ctx.session, "state", None) or {}
    if isinstance(state, dict):
        ge_conv_id = state.get(GE_CONVERSATION_ID_STATE_KEY)
        ag_conv_id = state.get(ANTIGRAVITY_CONVERSATION_ID_STATE_KEY)

    # Check prior session events if state was reconstructed from event history
    if not ge_conv_id or not ag_conv_id:
        for ev in getattr(ctx.session, "events", None) or []:
            custom_meta = getattr(ev, "custom_metadata", None) or {}
            if isinstance(custom_meta, dict):
                ge_conv_id = ge_conv_id or custom_meta.get("ge_conversation_id")
                ag_conv_id = ag_conv_id or custom_meta.get(
                    "antigravity_conversation_id"
                )
            actions = getattr(ev, "actions", None)
            state_delta = getattr(actions, "state_delta", None) if actions else None
            if isinstance(state_delta, dict):
                ge_conv_id = ge_conv_id or state_delta.get(
                    GE_CONVERSATION_ID_STATE_KEY
                )
                ag_conv_id = ag_conv_id or state_delta.get(
                    ANTIGRAVITY_CONVERSATION_ID_STATE_KEY
                )
            if ge_conv_id and ag_conv_id:
                break

    if not ge_conv_id:
        ge_conv_id = incoming_ge_session_id_var.get() or str(ctx.session.id)

    if not ag_conv_id:
        ag_conv_id = derive_antigravity_conversation_id(ge_conv_id)

    return str(ge_conv_id), str(ag_conv_id)


def _get_trajectory_gcs_bucket() -> str | None:
    return os.environ.get("ANTIGRAVITY_TELEMETRY_BUCKET") or os.environ.get(
        "LOGS_BUCKET_NAME"
    )


def restore_trajectory_from_gcs(
    antigravity_conversation_id: str, save_dir: str
) -> bool:
    """Downloads `<antigravity_conversation_id>.db` from GCS if not present on local disk."""
    local_db = os.path.join(save_dir, f"{antigravity_conversation_id}.db")
    if os.path.exists(local_db) and os.path.getsize(local_db) > 0:
        return True

    bucket_name = _get_trajectory_gcs_bucket()
    if not bucket_name:
        return False

    try:
        from google.cloud import storage

        client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"trajectories/{antigravity_conversation_id}.db")
        if blob.exists():
            os.makedirs(save_dir, exist_ok=True)
            blob.download_to_filename(local_db)
            logger.info(
                "Restored trajectory %s.db from gs://%s/trajectories/",
                antigravity_conversation_id,
                bucket_name,
            )
            return True
    except Exception as exc:
        logger.warning(
            "Could not restore trajectory %s from GCS: %s",
            antigravity_conversation_id,
            exc,
        )
    return False


def backup_trajectory_to_gcs(
    antigravity_conversation_id: str, save_dir: str
) -> bool:
    """Uploads `<antigravity_conversation_id>.db` to GCS after a turn completes."""
    local_db = os.path.join(save_dir, f"{antigravity_conversation_id}.db")
    if not os.path.exists(local_db):
        return False

    bucket_name = _get_trajectory_gcs_bucket()
    if not bucket_name:
        return False

    try:
        from google.cloud import storage

        client = storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"trajectories/{antigravity_conversation_id}.db")
        blob.upload_from_filename(local_db)
        return True
    except Exception as exc:
        logger.warning(
            "Could not back up trajectory %s to GCS: %s",
            antigravity_conversation_id,
            exc,
        )
        return False


def _write_to_bigquery(record: dict[str, Any]) -> None:
    """Streams a token usage telemetry row into BigQuery (`antigravity_telemetry.token_usage`)."""
    if os.environ.get("DISABLE_BQ_TELEMETRY", "").lower() in ("true", "1"):
        return

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb")
    dataset_id = os.environ.get(
        "ANTIGRAVITY_BQ_DATASET", "antigravity_telemetry"
    )
    table_id = os.environ.get("ANTIGRAVITY_BQ_TABLE", "token_usage")
    full_table_id = f"{project_id}.{dataset_id}.{table_id}"

    row = {
        "timestamp": record["timestamp"],
        "ge_conversation_id": record["ge_conversation_id"],
        "antigravity_conversation_id": record["antigravity_conversation_id"],
        "request_invocation_id": record["request_invocation_id"],
        "user_id": record["user_id"],
        "turn_number": record["turn_number"],
        "model": record["model"],
        "prompt_preview": (record.get("prompt_preview") or "")[:500],
        "request_prompt_tokens": record["request_tokens"]["prompt_tokens"],
        "request_cached_tokens": record["request_tokens"]["cached_tokens"],
        "request_candidates_tokens": record["request_tokens"]["candidates_tokens"],
        "request_thoughts_tokens": record["request_tokens"]["thoughts_tokens"],
        "request_total_tokens": record["request_tokens"]["total_tokens"],
        "conversation_prompt_tokens": record["conversation_cumulative_tokens"][
            "prompt_tokens"
        ],
        "conversation_cached_tokens": record["conversation_cumulative_tokens"][
            "cached_tokens"
        ],
        "conversation_candidates_tokens": record["conversation_cumulative_tokens"][
            "candidates_tokens"
        ],
        "conversation_thoughts_tokens": record["conversation_cumulative_tokens"][
            "thoughts_tokens"
        ],
        "conversation_total_tokens": record["conversation_cumulative_tokens"][
            "total_tokens"
        ],
        "subagent_usage_json": json.dumps(record.get("trajectory_tokens", {})),
        "latency_ms": record.get("latency_ms", 0.0),
    }

    try:
        from google.cloud import bigquery

        bq_client = bigquery.Client(project=project_id)
        errors = bq_client.insert_rows_json(full_table_id, [row])
        if errors:
            logger.warning("BigQuery telemetry insert errors: %s", errors)
    except Exception as exc:
        logger.debug("BigQuery telemetry write skipped/failed: %s", exc)


def record_turn_telemetry(
    *,
    ge_conversation_id: str,
    antigravity_conversation_id: str,
    request_invocation_id: str,
    user_id: str,
    model: str,
    prompt_text: str,
    turn_number: int,
    request_counts: TokenCounts,
    conversation_counts: TokenCounts,
    trajectory_usages: dict[str, Any] | None = None,
    latency_ms: float = 0.0,
) -> dict[str, Any]:
    """Emits per-request and per-conversation token telemetry to OTel, Cloud Logging, and BigQuery."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    traj_dict: dict[str, dict[str, int]] = {}
    for traj_id, u in (trajectory_usages or {}).items():
        traj_dict[traj_id] = TokenCounts.from_sdk_usage(u).to_dict()

    telemetry_record: dict[str, Any] = {
        "event_type": "ANTIGRAVITY_TOKEN_USAGE",
        "timestamp": now_iso,
        "ge_conversation_id": ge_conversation_id,
        "antigravity_conversation_id": antigravity_conversation_id,
        "request_invocation_id": request_invocation_id,
        "user_id": user_id,
        "turn_number": turn_number,
        "model": model,
        "prompt_preview": prompt_text[:500],
        "request_tokens": request_counts.to_dict(),
        "conversation_cumulative_tokens": conversation_counts.to_dict(),
        "trajectory_tokens": traj_dict,
        "latency_ms": round(latency_ms, 2),
    }

    # 1. OpenTelemetry Span Attributes (Cloud Trace)
    span_attrs: dict[str, Any] = {
        "gen_ai.system": "google_antigravity",
        "gen_ai.request.model": model,
        "gen_ai.conversation.id": ge_conversation_id,
        "antigravity.conversation.id": antigravity_conversation_id,
        "gen_ai.request.id": request_invocation_id,
        "antigravity.user_id": user_id,
        "antigravity.conversation.turn_number": turn_number,
        "gen_ai.usage.input_tokens": request_counts.prompt_tokens,
        "gen_ai.usage.output_tokens": request_counts.candidates_tokens,
        "gen_ai.usage.thoughts_tokens": request_counts.thoughts_tokens,
        "gen_ai.usage.cached_tokens": request_counts.cached_tokens,
        "gen_ai.usage.total_tokens": request_counts.total_tokens,
        "antigravity.conversation.cumulative_prompt_tokens": (
            conversation_counts.prompt_tokens
        ),
        "antigravity.conversation.cumulative_candidates_tokens": (
            conversation_counts.candidates_tokens
        ),
        "antigravity.conversation.cumulative_thoughts_tokens": (
            conversation_counts.thoughts_tokens
        ),
        "antigravity.conversation.cumulative_cached_tokens": (
            conversation_counts.cached_tokens
        ),
        "antigravity.conversation.cumulative_total_tokens": (
            conversation_counts.total_tokens
        ),
        "antigravity.latency_ms": round(latency_ms, 2),
    }

    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        for k, v in span_attrs.items():
            current_span.set_attribute(k, v)

    with tracer.start_as_current_span("antigravity.turn_telemetry") as child_span:
        for k, v in span_attrs.items():
            child_span.set_attribute(k, v)

    # 2. Structured JSON Log (automatically parsed into jsonPayload by Cloud Logging)
    print(json.dumps(telemetry_record), flush=True)
    logger.info("ANTIGRAVITY_TOKEN_USAGE %s", json.dumps(telemetry_record))

    # 3. Stream to BigQuery (`antigravity_telemetry.token_usage`)
    _write_to_bigquery(telemetry_record)

    return telemetry_record
