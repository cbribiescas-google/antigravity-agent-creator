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

"""Live DAG orchestration and branch-pruning telemetry tools.

Provides structured JSONL telemetry markers consumed in real time by the API
Gateway and Live Studio UI across Scenario #3 (Shark Tank), Scenario #4
(Supreme Court Debate), Scenario #8 (Six Degrees Dynamic Tree Search & Prune),
and all other multi-step agentic DAG scenarios.
"""

import json
import os
import re
from datetime import UTC, datetime
from typing import Any


def _resolve_sandbox_dir() -> str:
    """Resolves and creates the active Antigravity sandbox workspace directory."""
    raw_dir = os.environ.get("ANTIGRAVITY_WORKSPACE_DIR") or os.path.join(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness"),
        "sandbox",
    )
    sandbox_dir = os.path.abspath(raw_dir)
    os.makedirs(sandbox_dir, exist_ok=True)
    return sandbox_dir


def _append_jsonl(file_path: str, payload: dict[str, Any]) -> None:
    """Appends a single UTF-8 JSON line to the target telemetry file."""
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def emit_dag_step(
    node_id: str,
    node_label: str,
    status: str = "completed",
    summary: str = "",
) -> dict[str, Any]:
    """Emits a structured live DAG node telemetry marker for real-time visualization.

    Call this tool as each stage, persona, debate round, or graph node in an
    agentic workflow starts, loops, completes, or fails (e.g., Scenario #3
    Shark Tank panel pitches, Scenario #4 Supreme Court Debate arguments,
    Scenario #8 Six Degrees Tree Search hops, and general DAG execution).

    Args:
        node_id: Unique identifier for the DAG node or stage (e.g.,
            "shark_fintech", "justice_rebuttal_1", "hop_2_candidate_a").
        node_label: Human-readable display label rendered on the Live Studio
            DAG node (e.g., "Fintech Shark Evaluation").
        status: Execution status of the node, normalized to lowercase (such as
            "started", "running", "completed", "pruned", "skipped", "looping",
            or "failed"). Custom non-empty status strings are preserved;
            defaults to "completed".
        summary: Concise summary of the node's action, intermediate finding, or
            output decision.

    Returns:
        A dictionary containing the recorded DAG step telemetry event with keys
        ``event_type``, ``node_id``, ``node_label``, ``status``, ``summary``,
        ``timestamp``, and ``log_path``.
    """
    clean_node_id = (node_id or "").strip() or "step"
    clean_node_label = (node_label or "").strip() or clean_node_id
    norm_status = (status or "").strip().lower() or "completed"
    summary_text = "" if summary is None else str(summary)
    iso_ts = datetime.now(UTC).isoformat()

    sandbox_dir = _resolve_sandbox_dir()
    log_path = os.path.join(sandbox_dir, "dag_events.jsonl")

    event: dict[str, Any] = {
        "event_type": "dag_step",
        "node_id": clean_node_id,
        "node_label": clean_node_label,
        "status": norm_status,
        "summary": summary_text,
        "timestamp": iso_ts,
        "log_path": log_path,
    }
    _append_jsonl(log_path, event)
    return event


def record_pruned_branch(branch_name: str, reason: str) -> dict[str, Any]:
    """Records a pruned candidate branch during dynamic tree search workflows.

    Use this tool in Scenario #8 (Dynamic Tree Search & Prune DAG) whenever an
    explored hop or candidate path hits a dead end, forms a cycle, or exceeds
    the remaining hop budget. Logs the pruned branch to both
    ``pruned_branches.jsonl`` and ``dag_events.jsonl`` with status ``"pruned"``.

    Args:
        branch_name: Name or path description of the pruned candidate branch
            (e.g., "Hop 2: Ada Lovelace -> Charles Babbage -> Dead End").
        reason: Explanation for why this branch was pruned (e.g., "Dead end: no
            verified collaborative link toward target within hop budget").

    Returns:
        A dictionary describing the pruned branch event with keys
        ``event_type``, ``branch_name``, ``reason``, ``status``, ``timestamp``,
        and ``log_path``.
    """
    clean_branch = (branch_name or "").strip()
    clean_reason = (reason or "").strip()
    iso_ts = datetime.now(UTC).isoformat()

    sandbox_dir = _resolve_sandbox_dir()
    pruned_log_path = os.path.join(sandbox_dir, "pruned_branches.jsonl")
    dag_log_path = os.path.join(sandbox_dir, "dag_events.jsonl")

    pruned_event: dict[str, Any] = {
        "event_type": "pruned_branch",
        "branch_name": clean_branch,
        "reason": clean_reason,
        "status": "pruned",
        "timestamp": iso_ts,
        "log_path": pruned_log_path,
    }
    _append_jsonl(pruned_log_path, pruned_event)

    step_node_id = (
        re.sub(r"[^a-z0-9_-]+", "_", clean_branch.lower()).strip("_")
        or "pruned_branch"
    )
    dag_step_event: dict[str, Any] = {
        "event_type": "dag_step",
        "node_id": step_node_id,
        "node_label": clean_branch or "pruned_branch",
        "status": "pruned",
        "summary": clean_reason,
        "timestamp": iso_ts,
        "log_path": dag_log_path,
    }
    _append_jsonl(dag_log_path, dag_step_event)

    return pruned_event
