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

"""Single API Gateway for Gemini Antigravity Root & Custom DAG Agents.

Provides unified REST and real-time Server-Sent Events (SSE) execution across
both the `antigravity` root builder agent and all dynamically built custom DAG
agents, enforcing:
1. Stateful 1-to-1 conversation alignment (`gw:{user_id}:{agent_id}:{conversation_id}` -> 32-char UUIDv5 hex).
2. Durable SQLite per-turn, per-conversation, per-agent, and per-user token usage ledger
   including accurate subagent trajectory token accounting (`trajectory_usages`).
3. Unified OTel / Cloud Logging / BigQuery telemetry via `app.telemetry.record_turn_telemetry`.
4. Live SSE streaming (`turn_start`, `thought`, `tool_call`, `tool_result`,
   `dag_step`, `text_delta`, `media`, `usage`, `turn_complete`, `error`) and
   sandboxed media/HTML5/ICS artifact serving.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity import types as sdk_types
from google.antigravity.hooks import hooks as sdk_hooks
from pydantic import BaseModel, Field

from app.agent import (
    MODEL,
    _detect_image_mime_type,
    _drain_pending_generated_video_paths,
    _extract_generated_image_paths_from_steps,
)
from app.telemetry import (
    TokenCounts,
    backup_trajectory_to_gcs,
    record_turn_telemetry,
    restore_trajectory_from_gcs,
)

logger = logging.getLogger(__name__)

# Ensure standard artifact MIME types are registered consistently across OSes
mimetypes.add_type("text/calendar", ".ics")
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")

_ARTIFACT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".svg",
        ".mp4",
        ".webm",
        ".mov",
        ".html",
        ".htm",
        ".ics",
    }
)

_PATH_CANDIDATE_KEYS: tuple[str, ...] = (
    "output_path",
    "file_path",
    "path",
    "TargetFile",
    "ics_path",
    "html_path",
    "video_path",
    "image_path",
    "draft_image_path",
)

_BUILTIN_OUTPUT_KEYS: dict[str, tuple[str, ...]] = {
    "run_command": ("combined_output", "exit_code"),
    "find_file": ("output",),
    "list_directory": ("results",),
    "list_dir": ("results",),
    "search_directory": ("num_results",),
    "search_dir": ("num_results",),
    "search_web": ("summary",),
    "read_url_content": ("title", "summary", "content_path"),
    "generate_image": ("image_name", "aspect_ratio", "output_path"),
    "edit_file": ("diff_block",),
}

_LOCAL_TMP_MARKDOWN_IMAGE_RE = re.compile(
    r"!?\[[^\]]*\]\((?:file://)?/tmp/[^)]+\)\s*"
)


# ---------------------------------------------------------------------------
# Dynamic path helpers (honors runtime / test env overrides)
# ---------------------------------------------------------------------------


def _get_base_dir() -> str:
    return os.path.abspath(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness")
    )


def _get_gateway_db_path() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_GATEWAY_DB",
            os.path.join(_get_base_dir(), "gateway_usage.db"),
        )
    )


def _get_workspace_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_WORKSPACE_DIR",
            os.path.join(_get_base_dir(), "sandbox"),
        )
    )


def _get_trajectories_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_TRAJECTORIES_DIR",
            os.path.join(_get_base_dir(), "trajectories"),
        )
    )


def _get_app_data_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_APP_DATA_DIR",
            os.path.join(_get_base_dir(), "app_data"),
        )
    )


def _ensure_harness_dirs() -> str:
    base = _get_base_dir()
    for d in (
        base,
        _get_workspace_dir(),
        _get_trajectories_dir(),
        _get_app_data_dir(),
        os.path.join(_get_app_data_dir(), "videos"),
        os.path.join(_get_app_data_dir(), "media"),
    ):
        os.makedirs(d, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# Deterministic Conversation Alignment
# ---------------------------------------------------------------------------


def derive_gateway_antigravity_conversation_id(
    user_id: str, agent_id: str, conversation_id: str
) -> str:
    """Derives a deterministic 32-char hex Antigravity conversation ID.

    Maps `(user_id, agent_id, conversation_id)` bijectively to the underlying
    `<ag_conv_id>.db` SQLite trajectory so multi-turn conversations resume exact
    history and token state.
    """
    return uuid.uuid5(
        uuid.NAMESPACE_DNS, f"gw:{user_id}:{agent_id}:{conversation_id}"
    ).hex


# Per-conversation async locks so concurrent turns on the same trajectory serialize cleanly
_conv_locks: dict[str, asyncio.Lock] = {}
_conv_locks_guard = threading.Lock()


def _get_conversation_lock(ag_conv_id: str) -> asyncio.Lock:
    with _conv_locks_guard:
        lock = _conv_locks.get(ag_conv_id)
        if lock is None:
            lock = asyncio.Lock()
            _conv_locks[ag_conv_id] = lock
        return lock


# ---------------------------------------------------------------------------
# Token Accounting & Subagent Trajectory Math
# ---------------------------------------------------------------------------


def make_token_dict(
    *,
    prompt_tokens: int = 0,
    cached_tokens: int = 0,
    candidates_tokens: int = 0,
    thoughts_tokens: int = 0,
    subagent_tokens: int = 0,
    total_tokens: int = 0,
) -> dict[str, int]:
    """Builds a canonical Gateway token dictionary including subagent & main breakdown."""
    p = max(0, int(prompt_tokens or 0))
    c = max(0, int(cached_tokens or 0))
    cand = max(0, int(candidates_tokens or 0))
    th = max(0, int(thoughts_tokens or 0))
    sub = max(0, int(subagent_tokens or 0))
    tot = max(0, int(total_tokens or 0))
    if tot == 0 and (p or cand or th):
        tot = p + cand + th
    if sub > tot:
        tot = sub
    return {
        "prompt_tokens": p,
        "cached_tokens": c,
        "candidates_tokens": cand,
        "thoughts_tokens": th,
        "subagent_tokens": sub,
        "main_tokens": max(0, tot - sub),
        "total_tokens": tot,
    }


def compute_turn_and_conversation_tokens(
    *,
    last_turn_usage: Any | None,
    total_usage: Any | None,
    pre_total_usage: Any | None,
    pre_trajectory_usages: dict[str, Any] | None,
    post_trajectory_usages: dict[str, Any] | None,
    main_trajectory_ids: set[str],
    prior_ledger_conv: dict[str, Any] | None = None,
) -> tuple[dict[str, int], dict[str, int], TokenCounts, TokenCounts, dict[str, dict[str, int]]]:
    """Computes accurate per-turn and cumulative conversation token counts with subagent breakdown.

    In `google.antigravity`, `total_usage` (`cumulative_usage`) and `last_turn_usage`
    already sum main + subagent trajectories, while `trajectory_usages` maps each
    individual trajectory ID (main + each subagent) to its cumulative `UsageMetadata`.
    We exclude `main_trajectory_ids` when summing `subagent_tokens` and reconcile
    against `all_trajectories` so subagent tokens are never double-counted nor lost.
    """
    clean_main_ids = {tid for tid in main_trajectory_ids if tid}
    pre_traj = {
        tid: TokenCounts.from_sdk_usage(u)
        for tid, u in (pre_trajectory_usages or {}).items()
    }
    post_traj = {
        tid: TokenCounts.from_sdk_usage(u)
        for tid, u in (post_trajectory_usages or {}).items()
    }
    traj_serialized = {tid: tc.to_dict() for tid, tc in post_traj.items()}

    # Identify subagent trajectories (every trajectory ID not matching main)
    subagent_tids = [tid for tid in post_traj if tid not in clean_main_ids]
    has_main_in_traj = any(tid in post_traj for tid in clean_main_ids)

    conv_subagent_tokens = sum(post_traj[tid].total_tokens for tid in subagent_tids)
    pre_subagent_tokens = sum(
        tc.total_tokens for tid, tc in pre_traj.items() if tid not in clean_main_ids
    )
    turn_subagent_tokens = max(0, conv_subagent_tokens - pre_subagent_tokens)

    # Sum across all trajectories in post_traj and pre_traj
    all_post_prompt = sum(tc.prompt_tokens for tc in post_traj.values())
    all_post_cached = sum(tc.cached_tokens for tc in post_traj.values())
    all_post_cand = sum(tc.candidates_tokens for tc in post_traj.values())
    all_post_thoughts = sum(tc.thoughts_tokens for tc in post_traj.values())
    all_post_total = sum(tc.total_tokens for tc in post_traj.values())

    all_pre_prompt = sum(tc.prompt_tokens for tc in pre_traj.values())
    all_pre_cached = sum(tc.cached_tokens for tc in pre_traj.values())
    all_pre_cand = sum(tc.candidates_tokens for tc in pre_traj.values())
    all_pre_thoughts = sum(tc.thoughts_tokens for tc in pre_traj.values())
    all_pre_total = sum(tc.total_tokens for tc in pre_traj.values())

    sdk_conv = TokenCounts.from_sdk_usage(total_usage)
    sdk_pre = TokenCounts.from_sdk_usage(pre_total_usage)

    if last_turn_usage is not None:
        sdk_turn = TokenCounts.from_sdk_usage(last_turn_usage)
    elif total_usage is not None and pre_total_usage is not None:
        sdk_turn = TokenCounts(
            prompt_tokens=max(0, sdk_conv.prompt_tokens - sdk_pre.prompt_tokens),
            cached_tokens=max(0, sdk_conv.cached_tokens - sdk_pre.cached_tokens),
            candidates_tokens=max(
                0, sdk_conv.candidates_tokens - sdk_pre.candidates_tokens
            ),
            thoughts_tokens=max(
                0, sdk_conv.thoughts_tokens - sdk_pre.thoughts_tokens
            ),
            total_tokens=max(0, sdk_conv.total_tokens - sdk_pre.total_tokens),
        )
    else:
        sdk_turn = sdk_conv

    # If a synthetic mock provided ONLY subagent entries in trajectory_usages (no main key)
    # and total_usage only reflects main tokens (< main + subagent), add subagent deltas cleanly;
    # otherwise (standard LocalHarness where main_traj IS in trajectory_usages and total_usage == sum),
    # max(sdk_*, all_traj_*) preserves exact counts with zero double-counting.
    if subagent_tids and not has_main_in_traj and sdk_conv.total_tokens < (
        sdk_conv.total_tokens + conv_subagent_tokens
    ):
        # Check whether sdk_conv already equals all_post_total (if only subagents ran) or is separate main usage
        if sdk_conv.total_tokens > 0 and sdk_conv.total_tokens != all_post_total:
            conv_prompt = sdk_conv.prompt_tokens + all_post_prompt
            conv_cached = sdk_conv.cached_tokens + all_post_cached
            conv_cand = sdk_conv.candidates_tokens + all_post_cand
            conv_thoughts = sdk_conv.thoughts_tokens + all_post_thoughts
            conv_total = sdk_conv.total_tokens + all_post_total

            turn_prompt = sdk_turn.prompt_tokens + max(0, all_post_prompt - all_pre_prompt)
            turn_cached = sdk_turn.cached_tokens + max(0, all_post_cached - all_pre_cached)
            turn_cand = sdk_turn.candidates_tokens + max(0, all_post_cand - all_pre_cand)
            turn_thoughts = sdk_turn.thoughts_tokens + max(
                0, all_post_thoughts - all_pre_thoughts
            )
            turn_total = sdk_turn.total_tokens + max(0, all_post_total - all_pre_total)
        else:
            conv_prompt = max(sdk_conv.prompt_tokens, all_post_prompt)
            conv_cached = max(sdk_conv.cached_tokens, all_post_cached)
            conv_cand = max(sdk_conv.candidates_tokens, all_post_cand)
            conv_thoughts = max(sdk_conv.thoughts_tokens, all_post_thoughts)
            conv_total = max(sdk_conv.total_tokens, all_post_total)

            turn_prompt = max(sdk_turn.prompt_tokens, all_post_prompt - all_pre_prompt)
            turn_cached = max(sdk_turn.cached_tokens, all_post_cached - all_pre_cached)
            turn_cand = max(sdk_turn.candidates_tokens, all_post_cand - all_pre_cand)
            turn_thoughts = max(
                sdk_turn.thoughts_tokens, all_post_thoughts - all_pre_thoughts
            )
            turn_total = max(sdk_turn.total_tokens, all_post_total - all_pre_total)
    else:
        conv_prompt = max(sdk_conv.prompt_tokens, all_post_prompt)
        conv_cached = max(sdk_conv.cached_tokens, all_post_cached)
        conv_cand = max(sdk_conv.candidates_tokens, all_post_cand)
        conv_thoughts = max(sdk_conv.thoughts_tokens, all_post_thoughts)
        conv_total = max(sdk_conv.total_tokens, all_post_total)

        turn_prompt = max(sdk_turn.prompt_tokens, all_post_prompt - all_pre_prompt)
        turn_cached = max(sdk_turn.cached_tokens, all_post_cached - all_pre_cached)
        turn_cand = max(sdk_turn.candidates_tokens, all_post_cand - all_pre_cand)
        turn_thoughts = max(
            sdk_turn.thoughts_tokens, all_post_thoughts - all_pre_thoughts
        )
        turn_total = max(sdk_turn.total_tokens, all_post_total - all_pre_total)

    req_dict = make_token_dict(
        prompt_tokens=turn_prompt,
        cached_tokens=turn_cached,
        candidates_tokens=turn_cand,
        thoughts_tokens=turn_thoughts,
        subagent_tokens=turn_subagent_tokens,
        total_tokens=turn_total,
    )

    # Reconcile cumulative conversation tokens with prior SQLite ledger row so multi-turn
    # continuity holds even if an underlying mock or container restarted fresh.
    if prior_ledger_conv:
        conv_prompt = max(
            conv_prompt,
            int(prior_ledger_conv.get("prompt_tokens", 0) or 0)
            + req_dict["prompt_tokens"],
        )
        conv_cached = max(
            conv_cached,
            int(prior_ledger_conv.get("cached_tokens", 0) or 0)
            + req_dict["cached_tokens"],
        )
        conv_cand = max(
            conv_cand,
            int(prior_ledger_conv.get("candidates_tokens", 0) or 0)
            + req_dict["candidates_tokens"],
        )
        conv_thoughts = max(
            conv_thoughts,
            int(prior_ledger_conv.get("thoughts_tokens", 0) or 0)
            + req_dict["thoughts_tokens"],
        )
        conv_subagent_tokens = max(
            conv_subagent_tokens,
            int(prior_ledger_conv.get("subagent_tokens", 0) or 0)
            + req_dict["subagent_tokens"],
        )
        conv_total = max(
            conv_total,
            int(prior_ledger_conv.get("total_tokens", 0) or 0)
            + req_dict["total_tokens"],
        )

    conv_dict = make_token_dict(
        prompt_tokens=conv_prompt,
        cached_tokens=conv_cached,
        candidates_tokens=conv_cand,
        thoughts_tokens=conv_thoughts,
        subagent_tokens=conv_subagent_tokens,
        total_tokens=conv_total,
    )

    req_tc = TokenCounts(
        prompt_tokens=req_dict["prompt_tokens"],
        cached_tokens=req_dict["cached_tokens"],
        candidates_tokens=req_dict["candidates_tokens"],
        thoughts_tokens=req_dict["thoughts_tokens"],
        total_tokens=req_dict["total_tokens"],
    )
    conv_tc = TokenCounts(
        prompt_tokens=conv_dict["prompt_tokens"],
        cached_tokens=conv_dict["cached_tokens"],
        candidates_tokens=conv_dict["candidates_tokens"],
        thoughts_tokens=conv_dict["thoughts_tokens"],
        total_tokens=conv_dict["total_tokens"],
    )
    return req_dict, conv_dict, req_tc, conv_tc, traj_serialized


# ---------------------------------------------------------------------------
# Durable SQLite Usage & Conversation Ledger
# ---------------------------------------------------------------------------


class GatewayLedger:
    """Thread-safe durable SQLite ledger for conversations, turns, and token rollups."""

    def __init__(self, db_path: str | None = None) -> None:
        self._explicit_db_path = db_path
        self._lock = threading.Lock()
        self._initialized_paths: set[str] = set()

    @property
    def db_path(self) -> str:
        return self._explicit_db_path or _get_gateway_db_path()

    def _connect(self) -> sqlite3.Connection:
        path = self.db_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        if path not in self._initialized_paths:
            self._init_schema(conn)
            self._initialized_paths.add(path)
        return conn

    @staticmethod
    def _init_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                antigravity_conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                title TEXT NOT NULL,
                turn_count INTEGER NOT NULL DEFAULT 0,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                cached_tokens INTEGER NOT NULL DEFAULT 0,
                candidates_tokens INTEGER NOT NULL DEFAULT 0,
                thoughts_tokens INTEGER NOT NULL DEFAULT 0,
                subagent_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                message_preview TEXT NOT NULL,
                response_preview TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                cached_tokens INTEGER NOT NULL DEFAULT 0,
                candidates_tokens INTEGER NOT NULL DEFAULT 0,
                thoughts_tokens INTEGER NOT NULL DEFAULT 0,
                subagent_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                tool_calls_json TEXT NOT NULL DEFAULT '[]',
                media_json TEXT NOT NULL DEFAULT '[]',
                latency_ms REAL NOT NULL DEFAULT 0.0,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_user
                ON conversations(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_conversations_agent
                ON conversations(agent_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_turns_conversation
                ON turns(conversation_id, turn_number ASC);
            CREATE INDEX IF NOT EXISTS idx_turns_user
                ON turns(user_id);
            CREATE INDEX IF NOT EXISTS idx_turns_agent
                ON turns(agent_id);
            """
        )
        conn.commit()

    def ensure_initialized(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.close()

    @staticmethod
    def _format_conversation_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["tokens"] = make_token_dict(
            prompt_tokens=d["prompt_tokens"],
            cached_tokens=d["cached_tokens"],
            candidates_tokens=d["candidates_tokens"],
            thoughts_tokens=d["thoughts_tokens"],
            subagent_tokens=d["subagent_tokens"],
            total_tokens=d["total_tokens"],
        )
        return d

    @staticmethod
    def _format_turn_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        try:
            d["tool_calls"] = json.loads(d.get("tool_calls_json") or "[]")
        except ValueError:
            d["tool_calls"] = []
        try:
            d["media"] = json.loads(d.get("media_json") or "[]")
        except ValueError:
            d["media"] = []
        d["tokens"] = make_token_dict(
            prompt_tokens=d["prompt_tokens"],
            cached_tokens=d["cached_tokens"],
            candidates_tokens=d["candidates_tokens"],
            thoughts_tokens=d["thoughts_tokens"],
            subagent_tokens=d["subagent_tokens"],
            total_tokens=d["total_tokens"],
        )
        return d

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                )
                row = cur.fetchone()
                return self._format_conversation_row(row) if row else None
            finally:
                conn.close()

    def record_turn(
        self,
        *,
        conversation_id: str,
        antigravity_conversation_id: str,
        user_id: str,
        agent_id: str,
        turn_number: int,
        message_text: str,
        response_text: str,
        request_tokens: dict[str, int],
        conversation_tokens: dict[str, int],
        tool_calls: list[dict[str, Any]],
        media: list[dict[str, Any]],
        latency_ms: float,
        timestamp: str,
    ) -> dict[str, int]:
        """Persists a completed turn and updates cumulative conversation & user totals."""
        title_candidate = re.sub(r"\s+", " ", message_text.strip())[:80] or "New Conversation"
        msg_preview = message_text[:500]
        resp_preview = response_text[:1000]
        tool_calls_str = json.dumps(tool_calls, default=str)
        media_str = json.dumps(media, default=str)

        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT turn_count, title, created_at FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()

                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO conversations (
                            conversation_id, antigravity_conversation_id, user_id, agent_id,
                            title, turn_count, prompt_tokens, cached_tokens, candidates_tokens,
                            thoughts_tokens, subagent_tokens, total_tokens, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            conversation_id,
                            antigravity_conversation_id,
                            user_id,
                            agent_id,
                            title_candidate,
                            turn_number,
                            conversation_tokens["prompt_tokens"],
                            conversation_tokens["cached_tokens"],
                            conversation_tokens["candidates_tokens"],
                            conversation_tokens["thoughts_tokens"],
                            conversation_tokens["subagent_tokens"],
                            conversation_tokens["total_tokens"],
                            timestamp,
                            timestamp,
                        ),
                    )
                else:
                    new_turn_count = max(int(existing["turn_count"]) + 1, turn_number)
                    conn.execute(
                        """
                        UPDATE conversations
                        SET antigravity_conversation_id = ?,
                            user_id = ?,
                            agent_id = ?,
                            turn_count = ?,
                            prompt_tokens = ?,
                            cached_tokens = ?,
                            candidates_tokens = ?,
                            thoughts_tokens = ?,
                            subagent_tokens = ?,
                            total_tokens = ?,
                            updated_at = ?
                        WHERE conversation_id = ?
                        """,
                        (
                            antigravity_conversation_id,
                            user_id,
                            agent_id,
                            new_turn_count,
                            conversation_tokens["prompt_tokens"],
                            conversation_tokens["cached_tokens"],
                            conversation_tokens["candidates_tokens"],
                            conversation_tokens["thoughts_tokens"],
                            conversation_tokens["subagent_tokens"],
                            conversation_tokens["total_tokens"],
                            timestamp,
                            conversation_id,
                        ),
                    )

                conn.execute(
                    """
                    INSERT INTO turns (
                        conversation_id, user_id, agent_id, turn_number,
                        message_preview, response_preview,
                        prompt_tokens, cached_tokens, candidates_tokens,
                        thoughts_tokens, subagent_tokens, total_tokens,
                        tool_calls_json, media_json, latency_ms, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        user_id,
                        agent_id,
                        turn_number,
                        msg_preview,
                        resp_preview,
                        request_tokens["prompt_tokens"],
                        request_tokens["cached_tokens"],
                        request_tokens["candidates_tokens"],
                        request_tokens["thoughts_tokens"],
                        request_tokens["subagent_tokens"],
                        request_tokens["total_tokens"],
                        tool_calls_str,
                        media_str,
                        round(latency_ms, 2),
                        timestamp,
                    ),
                )
                conn.commit()

                user_row = conn.execute(
                    """
                    SELECT
                        COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                        COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                        COALESCE(SUM(candidates_tokens), 0) AS candidates_tokens,
                        COALESCE(SUM(thoughts_tokens), 0) AS thoughts_tokens,
                        COALESCE(SUM(subagent_tokens), 0) AS subagent_tokens,
                        COALESCE(SUM(total_tokens), 0) AS total_tokens
                    FROM conversations
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
                return make_token_dict(
                    prompt_tokens=user_row["prompt_tokens"],
                    cached_tokens=user_row["cached_tokens"],
                    candidates_tokens=user_row["candidates_tokens"],
                    thoughts_tokens=user_row["thoughts_tokens"],
                    subagent_tokens=user_row["subagent_tokens"],
                    total_tokens=user_row["total_tokens"],
                )
            finally:
                conn.close()

    def list_conversations(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))

        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"""
                    SELECT * FROM conversations
                    {where_sql}
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    tuple(params),
                ).fetchall()
                return [self._format_conversation_row(r) for r in rows]
            finally:
                conn.close()

    def get_conversation_detail(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                conv_row = conn.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()
                if conv_row is None:
                    return None
                turn_rows = conn.execute(
                    "SELECT * FROM turns WHERE conversation_id = ? ORDER BY turn_number ASC, id ASC",
                    (conversation_id,),
                ).fetchall()
                return {
                    "conversation": self._format_conversation_row(conv_row),
                    "turns": [self._format_turn_row(r) for r in turn_rows],
                }
            finally:
                conn.close()

    def list_users_usage(self) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT
                        user_id,
                        COUNT(*) AS conversation_count,
                        COALESCE(SUM(turn_count), 0) AS turn_count,
                        COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                        COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                        COALESCE(SUM(candidates_tokens), 0) AS candidates_tokens,
                        COALESCE(SUM(thoughts_tokens), 0) AS thoughts_tokens,
                        COALESCE(SUM(subagent_tokens), 0) AS subagent_tokens,
                        COALESCE(SUM(total_tokens), 0) AS total_tokens,
                        MAX(updated_at) AS last_active_at
                    FROM conversations
                    GROUP BY user_id
                    ORDER BY total_tokens DESC, user_id ASC
                    """
                ).fetchall()
                result: list[dict[str, Any]] = []
                for r in rows:
                    tok = make_token_dict(
                        prompt_tokens=r["prompt_tokens"],
                        cached_tokens=r["cached_tokens"],
                        candidates_tokens=r["candidates_tokens"],
                        thoughts_tokens=r["thoughts_tokens"],
                        subagent_tokens=r["subagent_tokens"],
                        total_tokens=r["total_tokens"],
                    )
                    result.append(
                        {
                            "user_id": r["user_id"],
                            "conversation_count": int(r["conversation_count"]),
                            "turn_count": int(r["turn_count"]),
                            "last_active_at": r["last_active_at"],
                            "tokens": tok,
                            **tok,
                        }
                    )
                return result
            finally:
                conn.close()

    def get_user_usage(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                agg = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS conversation_count,
                        COALESCE(SUM(turn_count), 0) AS turn_count,
                        COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                        COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                        COALESCE(SUM(candidates_tokens), 0) AS candidates_tokens,
                        COALESCE(SUM(thoughts_tokens), 0) AS thoughts_tokens,
                        COALESCE(SUM(subagent_tokens), 0) AS subagent_tokens,
                        COALESCE(SUM(total_tokens), 0) AS total_tokens,
                        MAX(updated_at) AS last_active_at
                    FROM conversations
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()

                agent_rows = conn.execute(
                    """
                    SELECT
                        agent_id,
                        COUNT(*) AS conversation_count,
                        COALESCE(SUM(turn_count), 0) AS turn_count,
                        COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                        COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                        COALESCE(SUM(candidates_tokens), 0) AS candidates_tokens,
                        COALESCE(SUM(thoughts_tokens), 0) AS thoughts_tokens,
                        COALESCE(SUM(subagent_tokens), 0) AS subagent_tokens,
                        COALESCE(SUM(total_tokens), 0) AS total_tokens,
                        MAX(updated_at) AS last_active_at
                    FROM conversations
                    WHERE user_id = ?
                    GROUP BY agent_id
                    ORDER BY total_tokens DESC, agent_id ASC
                    """,
                    (user_id,),
                ).fetchall()

                recent_convs = conn.execute(
                    """
                    SELECT * FROM conversations
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 25
                    """,
                    (user_id,),
                ).fetchall()

                user_tok = make_token_dict(
                    prompt_tokens=agg["prompt_tokens"],
                    cached_tokens=agg["cached_tokens"],
                    candidates_tokens=agg["candidates_tokens"],
                    thoughts_tokens=agg["thoughts_tokens"],
                    subagent_tokens=agg["subagent_tokens"],
                    total_tokens=agg["total_tokens"],
                )

                by_agent = []
                for ar in agent_rows:
                    atok = make_token_dict(
                        prompt_tokens=ar["prompt_tokens"],
                        cached_tokens=ar["cached_tokens"],
                        candidates_tokens=ar["candidates_tokens"],
                        thoughts_tokens=ar["thoughts_tokens"],
                        subagent_tokens=ar["subagent_tokens"],
                        total_tokens=ar["total_tokens"],
                    )
                    by_agent.append(
                        {
                            "agent_id": ar["agent_id"],
                            "conversation_count": int(ar["conversation_count"]),
                            "turn_count": int(ar["turn_count"]),
                            "last_active_at": ar["last_active_at"],
                            "tokens": atok,
                            **atok,
                        }
                    )

                return {
                    "user_id": user_id,
                    "conversation_count": int(agg["conversation_count"]),
                    "turn_count": int(agg["turn_count"]),
                    "last_active_at": agg["last_active_at"],
                    "tokens": user_tok,
                    **user_tok,
                    "by_agent": by_agent,
                    "recent_conversations": [
                        self._format_conversation_row(c) for c in recent_convs
                    ],
                }
            finally:
                conn.close()

    def get_usage_summary(self) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                g = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS conversation_count,
                        COALESCE(SUM(turn_count), 0) AS turn_count,
                        COUNT(DISTINCT user_id) AS user_count,
                        COUNT(DISTINCT agent_id) AS agent_count,
                        COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                        COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                        COALESCE(SUM(candidates_tokens), 0) AS candidates_tokens,
                        COALESCE(SUM(thoughts_tokens), 0) AS thoughts_tokens,
                        COALESCE(SUM(subagent_tokens), 0) AS subagent_tokens,
                        COALESCE(SUM(total_tokens), 0) AS total_tokens
                    FROM conversations
                    """
                ).fetchone()
                avg_lat_row = conn.execute(
                    "SELECT COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms FROM turns"
                ).fetchone()

                agent_rows = conn.execute(
                    """
                    SELECT
                        agent_id,
                        COUNT(*) AS conversation_count,
                        COALESCE(SUM(turn_count), 0) AS turn_count,
                        COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                        COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                        COALESCE(SUM(candidates_tokens), 0) AS candidates_tokens,
                        COALESCE(SUM(thoughts_tokens), 0) AS thoughts_tokens,
                        COALESCE(SUM(subagent_tokens), 0) AS subagent_tokens,
                        COALESCE(SUM(total_tokens), 0) AS total_tokens,
                        MAX(updated_at) AS last_active_at
                    FROM conversations
                    GROUP BY agent_id
                    ORDER BY total_tokens DESC, agent_id ASC
                    """
                ).fetchall()

                conv_rows = conn.execute(
                    """
                    SELECT * FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT 100
                    """
                ).fetchall()
            finally:
                conn.close()

        by_user = self.list_users_usage()
        global_tok = make_token_dict(
            prompt_tokens=g["prompt_tokens"],
            cached_tokens=g["cached_tokens"],
            candidates_tokens=g["candidates_tokens"],
            thoughts_tokens=g["thoughts_tokens"],
            subagent_tokens=g["subagent_tokens"],
            total_tokens=g["total_tokens"],
        )
        by_agent = []
        for ar in agent_rows:
            atok = make_token_dict(
                prompt_tokens=ar["prompt_tokens"],
                cached_tokens=ar["cached_tokens"],
                candidates_tokens=ar["candidates_tokens"],
                thoughts_tokens=ar["thoughts_tokens"],
                subagent_tokens=ar["subagent_tokens"],
                total_tokens=ar["total_tokens"],
            )
            by_agent.append(
                {
                    "agent_id": ar["agent_id"],
                    "conversation_count": int(ar["conversation_count"]),
                    "turn_count": int(ar["turn_count"]),
                    "last_active_at": ar["last_active_at"],
                    "tokens": atok,
                    **atok,
                }
            )

        return {
            "global": {
                "conversation_count": int(g["conversation_count"]),
                "turn_count": int(g["turn_count"]),
                "user_count": int(g["user_count"]),
                "agent_count": int(g["agent_count"]),
                "avg_latency_ms": round(float(avg_lat_row["avg_latency_ms"] or 0.0), 2),
                "tokens": global_tok,
                **global_tok,
            },
            "by_agent": by_agent,
            "by_user": by_user,
            "by_conversation": [self._format_conversation_row(c) for c in conv_rows],
        }


ledger = GatewayLedger()


# ---------------------------------------------------------------------------
# Real-Time Hook Capture for Custom & Built-in Tool Outcomes
# ---------------------------------------------------------------------------


class _GatewayPostToolHook(sdk_hooks.PostToolCallHook):  # type: ignore[misc]
    """Streams live post-tool-call results into the active turn's event queue."""

    def __init__(self, queue: asyncio.Queue[tuple[str, Any]]) -> None:
        super().__init__()
        self._queue = queue

    async def run(self, context: object, data: Any) -> None:
        del context
        await self._queue.put(("hook_result", data))


class _GatewayToolErrorHook(sdk_hooks.OnToolErrorHook):  # type: ignore[misc]
    """Streams live tool failures into the active turn's event queue."""

    def __init__(self, queue: asyncio.Queue[tuple[str, Any]]) -> None:
        super().__init__()
        self._queue = queue

    async def run(self, context: object, data: Exception) -> None:
        del context
        await self._queue.put(("hook_error", data))


def _unwrap_tool_result_payload(raw_value: Any, error_str: str | None = None) -> tuple[dict[str, Any], bool]:
    """Normalizes a tool execution outcome into `(payload_dict, is_error)`."""
    if error_str:
        return {"error": str(error_str)}, True

    val = raw_value
    if hasattr(val, "model_dump"):
        val = val.model_dump(mode="json")
    elif hasattr(val, "dict"):
        val = val.dict()

    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            val = parsed
        except ValueError:
            pass

    if isinstance(val, dict):
        is_err = bool(val.get("error")) and "passed" not in val
        return val, is_err

    return {"result": "success" if val is None else val}, False


def _extract_builtin_step_result(step: Any, call: Any) -> tuple[dict[str, Any], bool]:
    status_name = getattr(getattr(step, "status", None), "name", str(getattr(step, "status", "")))
    if status_name == "ERROR" or getattr(step, "error", ""):
        err = getattr(step, "error", "") or f"Tool execution failed ({status_name})"
        return {"error": err}, True

    tool_name = str(getattr(call, "name", ""))
    args = getattr(call, "args", None)
    output_keys = _BUILTIN_OUTPUT_KEYS.get(tool_name, ())
    if output_keys and isinstance(args, dict):
        extracted = {k: args[k] for k in output_keys if k in args}
        if extracted:
            return extracted, False
    return {"result": getattr(step, "content", "") or "success"}, False


# ---------------------------------------------------------------------------
# DAG Step & Media / Artifact Discovery
# ---------------------------------------------------------------------------


def _synthesize_dag_step_from_tool(
    tool_name: str,
    args: dict[str, Any],
    result: dict[str, Any] | None,
    phase: str,
) -> dict[str, Any] | None:
    """Produces a live `dag_step` event when DAG-relevant tools start or finish."""
    if phase == "start":
        if tool_name in ("start_subagent", "invoke_subagent"):
            sub_name = (
                args.get("agent_name")
                or args.get("subagent_name")
                or args.get("name")
                or "subagent"
            )
            task_preview = str(
                args.get("prompt") or args.get("task") or args.get("request") or ""
            )[:160]
            return {
                "type": "dag_step",
                "node_id": str(sub_name),
                "node_label": str(sub_name),
                "status": "running",
                "summary": task_preview,
                "source_tool": tool_name,
            }
        return None

    res = result or {}
    if tool_name == "emit_dag_step":
        node_id = str(res.get("node_id") or args.get("node_id") or "step")
        node_label = str(res.get("node_label") or args.get("node_label") or node_id)
        status = str(res.get("status") or args.get("status") or "completed")
        summary = str(res.get("summary") or args.get("summary") or "")
        return {
            "type": "dag_step",
            "node_id": node_id,
            "node_label": node_label,
            "status": status,
            "summary": summary,
            "source_tool": tool_name,
        }

    if tool_name == "record_pruned_branch":
        branch = str(res.get("branch_name") or args.get("branch_name") or "pruned_branch")
        reason = str(res.get("reason") or args.get("reason") or "")
        return {
            "type": "dag_step",
            "node_id": branch,
            "node_label": branch,
            "status": "pruned",
            "summary": reason,
            "source_tool": tool_name,
        }

    if tool_name == "verify_claim_math":
        branch = str(res.get("route_branch") or "router_decision")
        confirmed = res.get("confirmed")
        comp_val = res.get("computed_value")
        return {
            "type": "dag_step",
            "node_id": branch,
            "node_label": branch,
            "status": "routed",
            "confirmed": confirmed,
            "computed_value": comp_val,
            "summary": f"confirmed={confirmed}, computed_value={comp_val}",
            "source_tool": tool_name,
        }

    if tool_name == "validate_html5_game":
        passed = bool(res.get("passed", False))
        errs = res.get("errors") or []
        return {
            "type": "dag_step",
            "node_id": "validate_html5_game",
            "node_label": "HTML5 Game Validator",
            "status": "completed" if passed else "retry",
            "passed": passed,
            "summary": "HTML5 validation passed"
            if passed
            else f"Needs self-healing ({len(errs)} error(s))",
            "source_tool": tool_name,
        }

    if tool_name == "log_vision_critique":
        needs_rev = bool(res.get("needs_revision", False))
        avg = res.get("average_score")
        return {
            "type": "dag_step",
            "node_id": "vision_critic",
            "node_label": "Vision Critic",
            "status": "retry" if needs_rev else "completed",
            "summary": f"avg_score={avg}, needs_revision={needs_rev}",
            "source_tool": tool_name,
        }

    if tool_name in ("start_subagent", "invoke_subagent"):
        sub_name = (
            args.get("agent_name")
            or args.get("subagent_name")
            or args.get("name")
            or "subagent"
        )
        return {
            "type": "dag_step",
            "node_id": str(sub_name),
            "node_label": str(sub_name),
            "status": "completed",
            "summary": "Subagent completed",
            "source_tool": tool_name,
        }

    if tool_name in (
        "create_custom_tool",
        "build_custom_agent",
        "run_bot_tournament",
        "solve_crawl_constraints",
        "export_ics_calendar",
        "roll_crypto_d20",
        "manage_hero_state",
        "generate_video",
        "generate_video_clip",
        "generate_image",
    ):
        label_map = {
            "create_custom_tool": f"Synthesize Tool ({args.get('tool_name', '')})",
            "build_custom_agent": f"Build Agent ({args.get('agent_id', '')})",
            "run_bot_tournament": "Gladiator Tournament Arena",
            "solve_crawl_constraints": "Constraint Solver",
            "export_ics_calendar": "Export iCalendar (.ics)",
            "roll_crypto_d20": "Crypto d20 Roll",
            "manage_hero_state": "Hero State Machine",
            "generate_video": "Veo 3.1 Video Generator",
            "generate_video_clip": "Veo 3.1 Trailer Clip",
            "generate_image": "Image Generator",
        }
        return {
            "type": "dag_step",
            "node_id": tool_name,
            "node_label": label_map.get(tool_name, tool_name),
            "status": "error" if res.get("error") else "completed",
            "summary": str(res.get("status") or "completed"),
            "source_tool": tool_name,
        }

    return None


def _detect_artifact_mime_and_kind(abs_path: str) -> tuple[str, str]:
    ext = os.path.splitext(abs_path)[1].lower()
    if ext in (".html", ".htm"):
        return "text/html", "html"
    if ext == ".ics":
        return "text/calendar", "calendar"
    if ext == ".svg":
        return "image/svg+xml", "image"
    try:
        with open(abs_path, "rb") as f:
            header = f.read(64)
    except OSError:
        header = b""

    if ext in (".mp4", ".webm", ".mov", ".png", ".jpg", ".jpeg", ".webp", ".gif"):
        mime = _detect_image_mime_type(abs_path, header)
        kind = "video" if mime.startswith("video/") else "image"
        return mime, kind

    guessed, _ = mimetypes.guess_type(abs_path)
    mime = guessed or "application/octet-stream"
    if mime.startswith("image/"):
        return mime, "image"
    if mime.startswith("video/"):
        return mime, "video"
    return mime, "file"


def _build_media_artifact(raw_path: str, base_dir: str) -> dict[str, Any] | None:
    """Validates an artifact file on disk and maps it to `/api/gateway/media/<rel_path>`."""
    if not raw_path or not isinstance(raw_path, str):
        return None
    candidate = raw_path.strip()
    if candidate.startswith("file://"):
        candidate = candidate[7:]
    if not os.path.isabs(candidate):
        candidate = os.path.join(_get_workspace_dir(), candidate)
    abs_path = os.path.realpath(candidate)
    if not os.path.isfile(abs_path):
        return None

    ext = os.path.splitext(abs_path)[1].lower()
    if ext not in _ARTIFACT_EXTENSIONS:
        return None

    size_bytes = os.path.getsize(abs_path)
    if size_bytes <= 0:
        return None

    real_base = os.path.realpath(base_dir)
    if not (abs_path == real_base or abs_path.startswith(real_base + os.sep)):
        # Copy external /tmp generated media into base_dir/app_data/media so /api/gateway/media serves it safely
        dest_dir = os.path.join(real_base, "app_data", "media")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, os.path.basename(abs_path))
        try:
            shutil.copy2(abs_path, dest_path)
            abs_path = os.path.realpath(dest_path)
        except OSError:
            return None

    rel_path = os.path.relpath(abs_path, real_base).replace(os.sep, "/")
    mime_type, kind = _detect_artifact_mime_and_kind(abs_path)
    return {
        "type": "media",
        "url": f"/api/gateway/media/{rel_path}",
        "rel_path": rel_path,
        "path": abs_path,
        "filename": os.path.basename(abs_path),
        "mime_type": mime_type,
        "kind": kind,
        "size_bytes": size_bytes,
    }


def _snapshot_artifact_mtimes(base_dir: str) -> dict[str, int]:
    """Snapshots `(realpath -> mtime_ns)` for artifact files in sandbox & app_data."""
    snap: dict[str, int] = {}
    for sub in ("sandbox", "app_data"):
        scan_root = os.path.join(base_dir, sub)
        if not os.path.isdir(scan_root):
            continue
        for root, _, files in os.walk(scan_root):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in _ARTIFACT_EXTENSIONS:
                    continue
                fpath = os.path.realpath(os.path.join(root, fname))
                try:
                    snap[fpath] = os.stat(fpath).st_mtime_ns
                except OSError:
                    continue
    return snap


def _discover_new_or_modified_artifacts(
    base_dir: str, pre_snapshot: dict[str, int]
) -> list[str]:
    """Finds artifact files created or modified during the active turn."""
    discovered: list[tuple[int, str]] = []
    for sub in ("sandbox", "app_data"):
        scan_root = os.path.join(base_dir, sub)
        if not os.path.isdir(scan_root):
            continue
        for root, _, files in os.walk(scan_root):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in _ARTIFACT_EXTENSIONS:
                    continue
                fpath = os.path.realpath(os.path.join(root, fname))
                try:
                    mtime_ns = os.stat(fpath).st_mtime_ns
                except OSError:
                    continue
                if fpath not in pre_snapshot or mtime_ns > pre_snapshot[fpath]:
                    discovered.append((mtime_ns, fpath))
    discovered.sort(key=lambda pair: pair[0])
    return [p for _, p in discovered]


def _extract_candidate_paths_from_dict(d: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(d, dict):
        return paths
    for key in _PATH_CANDIDATE_KEYS:
        val = d.get(key)
        if isinstance(val, str) and val.strip():
            paths.append(val.strip())
    return paths


# ---------------------------------------------------------------------------
# Agent Builder Integration & SDK Agent Factory
# ---------------------------------------------------------------------------


def _get_agents_catalog() -> list[dict[str, Any]]:
    try:
        from app import agent_builder  # type: ignore[attr-defined]

        return list(agent_builder.list_agents_catalog())
    except ImportError:
        return [
            {
                "agent_id": "antigravity",
                "display_name": "Gemini Antigravity (Builder & Orchestrator)",
                "description": (
                    "Autonomous root builder agent capable of synthesizing custom Python tools "
                    "and building custom multi-agent DAG configurations."
                ),
                "dag_topology": "builder-loop",
                "dag_nodes": [],
                "dag_edges": [],
                "tool_names": ["generate_video"],
                "enable_subagents": True,
            }
        ]


def _get_registered_tools_and_agents() -> dict[str, Any]:
    try:
        from app import agent_builder  # type: ignore[attr-defined]

        return dict(agent_builder.list_registered_agents_and_tools())
    except ImportError:
        from app.agent import sdk_config

        builtin = [b.value for b in sdk_types.BuiltinTools]
        custom = [getattr(t, "__name__", str(t)) for t in sdk_config.tools]
        return {
            "builtin_tools": builtin,
            "scenario_tools": [],
            "dynamic_tools": [],
            "custom_tools": custom,
            "registered_agents": _get_agents_catalog(),
        }


def _resolve_agent_config(agent_id: str) -> LocalAgentConfig:
    norm_id = (agent_id or "antigravity").strip() or "antigravity"
    try:
        from app import agent_builder  # type: ignore[attr-defined]

        return agent_builder.build_local_agent_config(norm_id)
    except ImportError as exc:
        if norm_id in ("antigravity", "gemini_antigravity_demo"):
            from app.agent import sdk_config

            return sdk_config
        raise HTTPException(
            status_code=404,
            detail=f"Custom agent '{norm_id}' not found (agent_builder unavailable).",
        ) from exc
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{norm_id}' not found: {exc}",
        ) from exc


def _create_sdk_agent(config: LocalAgentConfig) -> Agent:
    """Instantiates `google.antigravity.Agent` (seam for fast deterministic unit testing)."""
    return Agent(config)


def _clean_response_markdown(text: str) -> str:
    if not text:
        return ""
    if "/tmp/" in text:
        return _LOCAL_TMP_MARKDOWN_IMAGE_RE.sub("", text).strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Request / Response Models & Core Turn Streaming Engine
# ---------------------------------------------------------------------------


class GatewayChatRequest(BaseModel):
    """Request payload for `POST /api/gateway/chat` and `POST /api/gateway/chat/stream`."""

    user_id: str = Field(default="cbribiescas", description="Caller user identifier")
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation ID; minted automatically if omitted.",
    )
    agent_id: str = Field(
        default="antigravity",
        description="Target agent ID ('antigravity' or any custom agent ID).",
    )
    message: str = Field(..., description="Non-empty user prompt to execute.")


def _format_sse(event_type: str, data: dict[str, Any]) -> str:
    payload = {"type": event_type, **data}
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


async def execute_gateway_turn_events(
    req: GatewayChatRequest,
    base_config: LocalAgentConfig,
) -> AsyncGenerator[dict[str, Any], None]:
    """Executes one stateful turn on the target Antigravity agent and yields live structured events."""
    user_id = (req.user_id or "").strip() or "cbribiescas"
    agent_id = (req.agent_id or "").strip() or "antigravity"
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must be a non-empty string.")

    conversation_id = (req.conversation_id or "").strip() or str(uuid.uuid4())
    ag_conv_id = derive_gateway_antigravity_conversation_id(
        user_id, agent_id, conversation_id
    )

    conv_lock = _get_conversation_lock(ag_conv_id)
    async with conv_lock:
        start_t = time.perf_counter()
        base_dir = _ensure_harness_dirs()
        save_dir = getattr(base_config, "save_dir", None) or _get_trajectories_dir()
        os.makedirs(save_dir, exist_ok=True)

        restore_trajectory_from_gcs(ag_conv_id, save_dir)
        _drain_pending_generated_video_paths()
        pre_files_snapshot = _snapshot_artifact_mtimes(base_dir)

        prior_conv_row = ledger.get_conversation(conversation_id)
        estimated_turn = (int(prior_conv_row["turn_count"]) + 1) if prior_conv_row else 1
        started_iso = datetime.datetime.now(datetime.UTC).isoformat()

        yield {
            "type": "turn_start",
            "user_id": user_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "antigravity_conversation_id": ag_conv_id,
            "turn_number": estimated_turn,
            "timestamp": started_iso,
        }

        event_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        config_copy = base_config.model_copy(deep=True)
        config_copy.conversation_id = ag_conv_id
        config_copy.session_continuation_mode = (
            sdk_types.SessionContinuationMode.CREATE_OR_RESUME
        )
        config_copy.save_dir = save_dir
        if not config_copy.env:
            try:
                from app import agent_builder  # type: ignore[attr-defined]

                if hasattr(agent_builder, "ensure_localharness_env"):
                    config_copy.env = agent_builder.ensure_localharness_env()
            except ImportError:
                pass
        config_copy.hooks = [
            *(config_copy.hooks or []),
            _GatewayPostToolHook(event_queue),
            _GatewayToolErrorHook(event_queue),
        ]

        events_trace: list[dict[str, Any]] = []
        thought_accum_by_step: dict[tuple[str, int], dict[str, Any]] = {}
        emitted_thinking_len: dict[tuple[str, int], int] = {}
        emitted_text_len: dict[tuple[str, int], int] = {}
        main_text_chunks: list[str] = []
        last_complete_main_text: str = ""

        seen_tool_calls: dict[str, dict[str, Any]] = {}
        seen_tool_results: set[str] = set()
        pending_hook_results: dict[str, tuple[str, dict[str, Any], bool]] = {}
        tool_calls_summary: dict[str, dict[str, Any]] = {}

        emitted_media_paths: set[str] = set()
        media_artifacts: list[dict[str, Any]] = []
        turn_steps: list[Any] = []
        main_step_traj_id: str = ""

        def _register_media_candidates(paths: list[str]) -> list[dict[str, Any]]:
            newly_added: list[dict[str, Any]] = []
            for p in paths:
                art = _build_media_artifact(p, base_dir)
                if art and art["path"] not in emitted_media_paths:
                    emitted_media_paths.add(art["path"])
                    media_artifacts.append(art)
                    events_trace.append(art)
                    newly_added.append(art)
            return newly_added

        def _emit_paired_tool_result(
            call_id: str,
            tool_name: str,
            res_dict: dict[str, Any],
            is_err: bool,
            step_index: int = 0,
            depth: int = 0,
        ) -> list[dict[str, Any]]:
            out_events: list[dict[str, Any]] = []
            if call_id in seen_tool_results:
                return out_events
            seen_tool_results.add(call_id)

            call_meta = seen_tool_calls.get(call_id, {})
            resolved_name = tool_name or call_meta.get("tool_name", "tool")
            call_args = call_meta.get("args", {})
            s_idx = call_meta.get("step_index", step_index)
            s_depth = call_meta.get("depth", depth)

            tr_ev = {
                "type": "tool_result",
                "call_id": call_id,
                "tool_name": resolved_name,
                "result": res_dict,
                "is_error": is_err,
                "step_index": s_idx,
                "depth": s_depth,
                "is_subagent": bool(s_depth > 0),
            }
            events_trace.append(tr_ev)
            out_events.append(tr_ev)

            if call_id in tool_calls_summary:
                tool_calls_summary[call_id]["result"] = res_dict
                tool_calls_summary[call_id]["is_error"] = is_err
            else:
                tool_calls_summary[call_id] = {
                    "call_id": call_id,
                    "tool_name": resolved_name,
                    "args": call_args,
                    "result": res_dict,
                    "is_error": is_err,
                }

            dag_ev = _synthesize_dag_step_from_tool(
                resolved_name, call_args, res_dict, phase="end"
            )
            if dag_ev is not None:
                events_trace.append(dag_ev)
                out_events.append(dag_ev)

            cand_paths = _extract_candidate_paths_from_dict(
                res_dict
            ) + _extract_candidate_paths_from_dict(call_args)
            out_events.extend(_register_media_candidates(cand_paths))
            return out_events

        try:
            sdk_agent = _create_sdk_agent(config_copy)
            async with sdk_agent:
                conv = sdk_agent.conversation
                prior_history = list(conv.history or [])
                prior_model_turns = sum(
                    1
                    for s in prior_history
                    if getattr(s, "is_complete_response", False)
                    and getattr(s, "depth", 0) == 0
                )
                turn_number = max(estimated_turn, prior_model_turns + 1)

                pre_total_usage = conv.total_usage
                pre_traj_usages = dict(conv.trajectory_usages or {})

                await conv.send(message)

                async def _pump_steps() -> None:
                    try:
                        async for st in conv.receive_steps():
                            await event_queue.put(("step", st))
                    except Exception as pump_exc:
                        await event_queue.put(("step_error", pump_exc))
                    finally:
                        await event_queue.put(("done", None))

                pump_task = asyncio.create_task(_pump_steps())
                stream_finished = False

                try:
                    while not stream_finished:
                        try:
                            kind, item = await asyncio.wait_for(
                                event_queue.get(), timeout=15.0
                            )
                        except TimeoutError:
                            yield {"type": "keepalive"}
                            continue

                        if kind == "done":
                            stream_finished = True
                            # Drain any remaining items already queued before exit
                            while not event_queue.empty():
                                rem_kind, rem_item = event_queue.get_nowait()
                                if rem_kind == "step_error":
                                    raise rem_item
                                if rem_kind in ("hook_result", "hook_error"):
                                    for ev in _handle_hook_item(
                                        rem_kind,
                                        rem_item,
                                        seen_tool_calls,
                                        seen_tool_results,
                                        pending_hook_results,
                                        _emit_paired_tool_result,
                                    ):
                                        yield ev
                            break

                        if kind == "step_error":
                            raise item

                        if kind in ("hook_result", "hook_error"):
                            for ev in _handle_hook_item(
                                kind,
                                item,
                                seen_tool_calls,
                                seen_tool_results,
                                pending_hook_results,
                                _emit_paired_tool_result,
                            ):
                                yield ev
                            continue

                        if kind == "step":
                            step = item
                            turn_steps.append(step)
                            s_traj = str(getattr(step, "trajectory_id", "") or "")
                            s_depth = int(getattr(step, "depth", 0) or 0)
                            s_idx = int(getattr(step, "step_index", 0) or 0)
                            is_sub = s_depth > 0
                            if not main_step_traj_id and s_depth == 0 and s_traj:
                                main_step_traj_id = s_traj

                            step_key = (s_traj, s_idx)
                            source_val = getattr(
                                getattr(step, "source", None),
                                "value",
                                str(getattr(step, "source", "")),
                            )
                            is_model = source_val in ("MODEL", "SOURCE_MODEL")

                            # 1. Live thoughts (delta or full fallback)
                            t_delta = str(getattr(step, "thinking_delta", "") or "")
                            t_full = str(getattr(step, "thinking", "") or "")
                            prev_t_len = emitted_thinking_len.get(step_key, 0)
                            emit_t = ""
                            if t_delta:
                                emit_t = t_delta
                                emitted_thinking_len[step_key] = max(
                                    prev_t_len + len(t_delta), len(t_full)
                                )
                            elif is_model and len(t_full) > prev_t_len:
                                emit_t = t_full[prev_t_len:]
                                emitted_thinking_len[step_key] = len(t_full)

                            if emit_t:
                                th_live = {
                                    "type": "thought",
                                    "text": emit_t,
                                    "step_index": s_idx,
                                    "depth": s_depth,
                                    "is_subagent": is_sub,
                                    "trajectory_id": s_traj,
                                }
                                if step_key in thought_accum_by_step:
                                    thought_accum_by_step[step_key]["text"] += emit_t
                                else:
                                    trace_th = dict(th_live)
                                    thought_accum_by_step[step_key] = trace_th
                                    events_trace.append(trace_th)
                                yield th_live

                            # 2. Tool calls & built-in tool completions
                            step_calls = getattr(step, "tool_calls", None) or []
                            for call in step_calls:
                                c_name = str(
                                    getattr(
                                        getattr(call, "name", None),
                                        "value",
                                        getattr(call, "name", ""),
                                    )
                                )
                                c_args = getattr(call, "args", None)
                                if not isinstance(c_args, dict):
                                    c_args = {}
                                raw_cid = getattr(call, "id", None)
                                cid = str(raw_cid or f"{s_traj}:{s_idx}-{c_name}")

                                if cid not in seen_tool_calls:
                                    tc_ev = {
                                        "type": "tool_call",
                                        "call_id": cid,
                                        "tool_name": c_name,
                                        "args": c_args,
                                        "step_index": s_idx,
                                        "depth": s_depth,
                                        "is_subagent": is_sub,
                                        "trajectory_id": s_traj,
                                    }
                                    seen_tool_calls[cid] = tc_ev
                                    events_trace.append(tc_ev)
                                    tool_calls_summary[cid] = {
                                        "call_id": cid,
                                        "tool_name": c_name,
                                        "args": c_args,
                                        "result": None,
                                        "is_error": False,
                                    }
                                    yield tc_ev

                                    start_dag = _synthesize_dag_step_from_tool(
                                        c_name, c_args, None, phase="start"
                                    )
                                    if start_dag is not None:
                                        events_trace.append(start_dag)
                                        yield start_dag

                                    if cid in pending_hook_results:
                                        p_name, p_res, p_err = pending_hook_results.pop(
                                            cid
                                        )
                                        for ev in _emit_paired_tool_result(
                                            cid, p_name, p_res, p_err, s_idx, s_depth
                                        ):
                                            yield ev

                            step_type_val = getattr(
                                getattr(step, "type", None),
                                "value",
                                str(getattr(step, "type", "")),
                            )
                            step_status_val = getattr(
                                getattr(step, "status", None),
                                "value",
                                str(getattr(step, "status", "")),
                            )
                            if step_type_val == "TOOL_CALL" and step_status_val in (
                                "DONE",
                                "ERROR",
                            ):
                                for call in step_calls:
                                    c_name = str(
                                        getattr(
                                            getattr(call, "name", None),
                                            "value",
                                            getattr(call, "name", ""),
                                        )
                                    )
                                    raw_cid = getattr(call, "id", None)
                                    cid = str(raw_cid or f"{s_traj}:{s_idx}-{c_name}")
                                    if cid not in seen_tool_results:
                                        b_res, b_err = _extract_builtin_step_result(
                                            step, call
                                        )
                                        for ev in _emit_paired_tool_result(
                                            cid, c_name, b_res, b_err, s_idx, s_depth
                                        ):
                                            yield ev

                            # 3. Live text deltas & final complete model response
                            c_delta = str(getattr(step, "content_delta", "") or "")
                            c_full = str(getattr(step, "content", "") or "")
                            is_comp = bool(getattr(step, "is_complete_response", False))
                            target_val = getattr(
                                getattr(step, "target", None),
                                "value",
                                str(getattr(step, "target", "TARGET_USER")),
                            )
                            is_user_target = target_val in ("TARGET_USER", "USER", "")

                            if is_model and is_user_target:
                                prev_c_len = emitted_text_len.get(step_key, 0)
                                emit_c = ""
                                if c_delta:
                                    emit_c = c_delta
                                    emitted_text_len[step_key] = max(
                                        prev_c_len + len(c_delta), len(c_full)
                                    )
                                elif is_comp and len(c_full) > prev_c_len:
                                    emit_c = c_full[prev_c_len:]
                                    emitted_text_len[step_key] = len(c_full)

                                if emit_c:
                                    if not is_sub:
                                        main_text_chunks.append(emit_c)
                                    yield {
                                        "type": "text_delta",
                                        "text": emit_c,
                                        "step_index": s_idx,
                                        "depth": s_depth,
                                        "is_subagent": is_sub,
                                        "trajectory_id": s_traj,
                                    }

                                if is_comp and not is_sub and c_full:
                                    last_complete_main_text = c_full
                finally:
                    if not pump_task.done():
                        pump_task.cancel()
                        await asyncio.gather(pump_task, return_exceptions=True)

                # Flush any unpaired hook results captured right at turn boundary
                for cid, (p_name, p_res, p_err) in list(pending_hook_results.items()):
                    if cid not in seen_tool_calls:
                        tc_ev = {
                            "type": "tool_call",
                            "call_id": cid,
                            "tool_name": p_name,
                            "args": {},
                            "step_index": 0,
                            "depth": 0,
                            "is_subagent": False,
                            "trajectory_id": main_step_traj_id,
                        }
                        seen_tool_calls[cid] = tc_ev
                        events_trace.append(tc_ev)
                        yield tc_ev
                    for ev in _emit_paired_tool_result(cid, p_name, p_res, p_err):
                        yield ev
                pending_hook_results.clear()

                # Discover all media / HTML5 / ICS files produced during this turn
                extra_paths: list[str] = []
                extra_paths.extend(_extract_generated_image_paths_from_steps(turn_steps))
                extra_paths.extend(_drain_pending_generated_video_paths())
                extra_paths.extend(
                    _discover_new_or_modified_artifacts(base_dir, pre_files_snapshot)
                )
                for med_ev in _register_media_candidates(extra_paths):
                    yield med_ev

                # Resolve final response text
                raw_response = (
                    last_complete_main_text
                    or "".join(main_text_chunks)
                    or str(getattr(conv, "last_response", "") or "")
                )
                if not raw_response:
                    struct_out = (
                        conv.get_last_structured_output()
                        if hasattr(conv, "get_last_structured_output")
                        else None
                    )
                    if struct_out is not None:
                        raw_response = json.dumps(struct_out, indent=2, default=str)
                response_text = _clean_response_markdown(raw_response)

                # Token accounting (including subagent trajectories)
                elapsed_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
                actual_ag_conv_id = sdk_agent.conversation_id or ag_conv_id
                main_ids = {actual_ag_conv_id, ag_conv_id, main_step_traj_id, "main"}

                post_traj_usages = dict(conv.trajectory_usages or {})
                (
                    request_tokens,
                    conversation_tokens,
                    req_tc,
                    conv_tc,
                    traj_tokens_dict,
                ) = compute_turn_and_conversation_tokens(
                    last_turn_usage=conv.last_turn_usage,
                    total_usage=conv.total_usage,
                    pre_total_usage=pre_total_usage,
                    pre_trajectory_usages=pre_traj_usages,
                    post_trajectory_usages=post_traj_usages,
                    main_trajectory_ids=main_ids,
                    prior_ledger_conv=prior_conv_row,
                )

                completed_iso = datetime.datetime.now(datetime.UTC).isoformat()
                model_name = str(getattr(base_config, "model", None) or MODEL)
                tool_calls_list = list(tool_calls_summary.values())

                # Persist to SQLite Gateway Ledger
                user_tokens = ledger.record_turn(
                    conversation_id=conversation_id,
                    antigravity_conversation_id=actual_ag_conv_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    turn_number=turn_number,
                    message_text=message,
                    response_text=response_text,
                    request_tokens=request_tokens,
                    conversation_tokens=conversation_tokens,
                    tool_calls=tool_calls_list,
                    media=media_artifacts,
                    latency_ms=elapsed_ms,
                    timestamp=completed_iso,
                )

                # Emit unified OTel / Cloud Logging / BigQuery telemetry
                record_turn_telemetry(
                    ge_conversation_id=conversation_id,
                    antigravity_conversation_id=actual_ag_conv_id,
                    request_invocation_id=f"gw-{uuid.uuid4().hex[:16]}",
                    user_id=user_id,
                    model=model_name,
                    prompt_text=message,
                    turn_number=turn_number,
                    request_counts=req_tc,
                    conversation_counts=conv_tc,
                    trajectory_usages=post_traj_usages,
                    latency_ms=elapsed_ms,
                )

                yield {
                    "type": "usage",
                    "turn_number": turn_number,
                    "request_tokens": request_tokens,
                    "conversation_tokens": conversation_tokens,
                    "user_tokens": user_tokens,
                    "trajectory_tokens": traj_tokens_dict,
                    "latency_ms": elapsed_ms,
                }

                yield {
                    "type": "turn_complete",
                    "status": "ok",
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "conversation_id": conversation_id,
                    "antigravity_conversation_id": actual_ag_conv_id,
                    "turn_number": turn_number,
                    "model": model_name,
                    "response_text": response_text,
                    "events": events_trace,
                    "tool_calls": tool_calls_list,
                    "media": media_artifacts,
                    "request_tokens": request_tokens,
                    "conversation_tokens": conversation_tokens,
                    "user_tokens": user_tokens,
                    "trajectory_tokens": traj_tokens_dict,
                    "latency_ms": elapsed_ms,
                    "timestamp": completed_iso,
                }
        except Exception as exc:
            logger.exception(
                "Gateway turn failed (user=%s, agent=%s, conv=%s)",
                user_id,
                agent_id,
                conversation_id,
            )
            yield {
                "type": "error",
                "error": str(exc),
                "user_id": user_id,
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "antigravity_conversation_id": ag_conv_id,
            }
        finally:
            backup_trajectory_to_gcs(ag_conv_id, save_dir)


def _handle_hook_item(
    kind: str,
    item: Any,
    seen_tool_calls: dict[str, dict[str, Any]],
    seen_tool_results: set[str],
    pending_hook_results: dict[str, tuple[str, dict[str, Any], bool]],
    emit_paired_fn: Any,
) -> list[dict[str, Any]]:
    """Pairs an incoming `PostToolCallHook` or `OnToolErrorHook` item with its `tool_call`."""
    if kind == "hook_result":
        t_name = str(
            getattr(
                getattr(item, "name", None), "value", getattr(item, "name", "")
            )
        )
        raw_id = getattr(item, "id", None)
        res_dict, is_err = _unwrap_tool_result_payload(
            getattr(item, "result", None), getattr(item, "error", None)
        )
    else:
        t_name = str(getattr(item, "tool_name", "") or "tool")
        raw_id = getattr(item, "call_id", None)
        res_dict, is_err = {"error": str(item) or "Tool execution failed"}, True

    call_id: str | None = str(raw_id) if raw_id else None
    if call_id is None:
        # Built-in tools may omit call_id in PostToolArgs; match most recent unanswered call of same tool
        for cid in reversed(list(seen_tool_calls.keys())):
            if (
                cid not in seen_tool_results
                and seen_tool_calls[cid].get("tool_name") == t_name
            ):
                call_id = cid
                break

    if call_id and call_id in seen_tool_calls:
        return emit_paired_fn(call_id, t_name, res_dict, is_err)

    if call_id:
        pending_hook_results[call_id] = (t_name, res_dict, is_err)
    return []


# ---------------------------------------------------------------------------
# FastAPI Router (`/api/gateway/*`)
# ---------------------------------------------------------------------------

gateway_router = APIRouter(prefix="/api/gateway", tags=["gateway"])


@gateway_router.get("/health")
async def gateway_health() -> dict[str, Any]:
    """Health check & active paths for the Single API Gateway."""
    base_dir = _ensure_harness_dirs()
    ledger.ensure_initialized()
    return {
        "status": "ok",
        "service": "antigravity-single-gateway",
        "model": MODEL,
        "base_dir": base_dir,
        "gateway_db": ledger.db_path,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }


@gateway_router.get("/agents")
async def gateway_list_agents() -> dict[str, Any]:
    """Lists the root `antigravity` builder agent and all registered custom DAG agents."""
    agents = _get_agents_catalog()
    return {"agents": agents, "count": len(agents)}


@gateway_router.get("/tools")
async def gateway_list_tools() -> dict[str, Any]:
    """Lists all built-in tools, scenario tools, dynamically synthesized tools, and registered agents."""
    return _get_registered_tools_and_agents()


@gateway_router.post("/chat")
async def gateway_chat(req: GatewayChatRequest) -> dict[str, Any]:
    """Executes a synchronous stateful turn through the Single API Gateway."""
    if not (req.message or "").strip():
        raise HTTPException(status_code=400, detail="message must be a non-empty string.")
    base_config = _resolve_agent_config(req.agent_id)

    final_payload: dict[str, Any] | None = None
    error_detail: str | None = None
    async for ev in execute_gateway_turn_events(req, base_config):
        if ev.get("type") == "turn_complete":
            final_payload = dict(ev)
            final_payload.pop("type", None)
        elif ev.get("type") == "error":
            error_detail = str(ev.get("error") or "Unknown gateway execution error")

    if error_detail and final_payload is None:
        raise HTTPException(status_code=500, detail=error_detail)
    if final_payload is None:
        raise HTTPException(
            status_code=500, detail="Turn ended without producing a final response."
        )
    return final_payload


@gateway_router.post("/chat/stream")
async def gateway_chat_stream(req: GatewayChatRequest) -> StreamingResponse:
    """Streams live Antigravity execution events (`text/event-stream` SSE)."""
    if not (req.message or "").strip():
        raise HTTPException(status_code=400, detail="message must be a non-empty string.")
    base_config = _resolve_agent_config(req.agent_id)

    async def _sse_generator() -> AsyncGenerator[str, None]:
        async for ev in execute_gateway_turn_events(req, base_config):
            ev_type = str(ev.get("type") or "message")
            if ev_type == "keepalive":
                yield ": keepalive\n\n"
                continue
            yield _format_sse(ev_type, ev)

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@gateway_router.get("/conversations")
async def gateway_list_conversations(
    user_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Lists conversations and their cumulative token totals, optionally filtered by user/agent."""
    convs = ledger.list_conversations(user_id=user_id, agent_id=agent_id, limit=limit)
    return {"conversations": convs, "count": len(convs)}


@gateway_router.get("/conversations/{conversation_id}")
async def gateway_get_conversation(conversation_id: str) -> dict[str, Any]:
    """Returns a single conversation and its full turn-by-turn token & artifact ledger."""
    detail = ledger.get_conversation_detail(conversation_id)
    if detail is None:
        raise HTTPException(
            status_code=404, detail=f"Conversation '{conversation_id}' not found."
        )
    return detail


@gateway_router.get("/usage/users")
async def gateway_usage_users() -> dict[str, Any]:
    """Returns per-user token usage totals and conversation counts."""
    users = ledger.list_users_usage()
    return {"users": users, "count": len(users)}


@gateway_router.get("/usage/users/{user_id}")
async def gateway_usage_single_user(user_id: str) -> dict[str, Any]:
    """Returns cumulative token usage, per-agent breakdown, and recent conversations for `user_id`."""
    return ledger.get_user_usage(user_id)


@gateway_router.get("/usage/summary")
async def gateway_usage_summary() -> dict[str, Any]:
    """Returns global, per-agent, per-user, and per-conversation token usage rollups."""
    return ledger.get_usage_summary()


@gateway_router.get("/media/{filepath:path}")
async def gateway_serve_media(filepath: str) -> FileResponse:
    """Safely serves generated media, HTML5 games/cards, and `.ics` files from `ANTIGRAVITY_BASE_DIR`."""
    base_dir = os.path.realpath(_get_base_dir())
    normalized_rel = filepath.lstrip("/")
    if not normalized_rel:
        raise HTTPException(status_code=404, detail="Empty media path.")

    target_path = os.path.realpath(os.path.join(base_dir, normalized_rel))
    if not (target_path == base_dir or target_path.startswith(base_dir + os.sep)):
        raise HTTPException(
            status_code=403, detail="Access outside sandbox base directory is forbidden."
        )
    if not os.path.isfile(target_path):
        raise HTTPException(
            status_code=404, detail=f"Artifact '{normalized_rel}' not found."
        )

    mime_type, _ = _detect_artifact_mime_and_kind(target_path)
    return FileResponse(
        path=target_path,
        media_type=mime_type,
        filename=os.path.basename(target_path),
    )
