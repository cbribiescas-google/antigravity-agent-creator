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

"""Unit tests for the Single API Gateway (`app/gateway.py`) and FastAPI mounts."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.antigravity import LocalAgentConfig
from google.antigravity import types as sdk_types
from google.antigravity.hooks import policy

from app import gateway
from app.gateway import (
    GatewayLedger,
    compute_turn_and_conversation_tokens,
    derive_gateway_antigravity_conversation_id,
    gateway_router,
)


def _make_test_config(tmp_base: str) -> LocalAgentConfig:
    ws = os.path.join(tmp_base, "sandbox")
    traj = os.path.join(tmp_base, "trajectories")
    app_data = os.path.join(tmp_base, "app_data")
    os.makedirs(ws, exist_ok=True)
    os.makedirs(traj, exist_ok=True)
    os.makedirs(app_data, exist_ok=True)
    return LocalAgentConfig(
        model="gemini-3.7-flash",
        vertex=True,
        project="gemini-enterprise-demo-cb",
        location="global",
        workspaces=[ws],
        save_dir=traj,
        app_data_dir=app_data,
        policies=[policy.allow_all()],
    )


class _FakeConversation:
    """Simulates `google.antigravity.conversation.Conversation` for deterministic Gateway tests."""

    def __init__(
        self,
        *,
        conversation_id: str,
        prior_history: list[Any],
        steps_to_yield: list[Any],
        hook_calls: list[Any],
        hooks: list[Any],
        pre_total_usage: sdk_types.UsageMetadata,
        post_total_usage: sdk_types.UsageMetadata,
        last_turn_usage: sdk_types.UsageMetadata,
        pre_traj_usages: dict[str, sdk_types.UsageMetadata],
        post_traj_usages: dict[str, sdk_types.UsageMetadata],
        on_send_side_effect: Any = None,
    ) -> None:
        self.conversation_id = conversation_id
        self._history = list(prior_history)
        self._steps_to_yield = list(steps_to_yield)
        self._hook_calls = list(hook_calls)
        self._hooks = list(hooks)
        self._current_total = pre_total_usage
        self._post_total = post_total_usage
        self._last_turn = last_turn_usage
        self._current_traj = dict(pre_traj_usages)
        self._post_traj = dict(post_traj_usages)
        self._on_send_side_effect = on_send_side_effect
        self.sent_prompts: list[Any] = []

    @property
    def history(self) -> list[Any]:
        return list(self._history)

    @property
    def total_usage(self) -> sdk_types.UsageMetadata:
        return self._current_total

    @property
    def last_turn_usage(self) -> sdk_types.UsageMetadata:
        return self._last_turn

    @property
    def trajectory_usages(self) -> dict[str, sdk_types.UsageMetadata]:
        return dict(self._current_traj)

    @property
    def last_response(self) -> str:
        for st in reversed(self._history):
            if getattr(st, "is_complete_response", False):
                return str(getattr(st, "content", ""))
        return ""

    async def send(self, prompt: Any) -> None:
        self.sent_prompts.append(prompt)
        if self._on_send_side_effect:
            self._on_send_side_effect()

    async def receive_steps(self):
        hook_map = {id(s): h for s, h in self._hook_calls}
        for st in self._steps_to_yield:
            self._history.append(st)
            yield st
            if id(st) in hook_map:
                tool_res = hook_map[id(st)]
                for hk in self._hooks:
                    if isinstance(hk, gateway._GatewayPostToolHook):
                        await hk.run(None, tool_res)
        self._current_total = self._post_total
        self._current_traj = dict(self._post_traj)


class _FakeAgent:
    def __init__(self, config: LocalAgentConfig, fake_conv: _FakeConversation) -> None:
        self.config = config
        self._conv = fake_conv

    async def __aenter__(self) -> _FakeAgent:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    @property
    def conversation(self) -> _FakeConversation:
        return self._conv

    @property
    def conversation_id(self) -> str:
        return self._conv.conversation_id


def test_deterministic_conversation_alignment() -> None:
    """Verify `(user_id, agent_id, conversation_id)` maps deterministically to 32-char UUID5 hex."""
    c1 = derive_gateway_antigravity_conversation_id("cbribiescas", "antigravity", "conv-123")
    c2 = derive_gateway_antigravity_conversation_id("cbribiescas", "antigravity", "conv-123")
    expected = uuid.uuid5(uuid.NAMESPACE_DNS, "gw:cbribiescas:antigravity:conv-123").hex

    assert c1 == c2 == expected
    assert len(c1) == 32
    assert all(ch in "0123456789abcdef" for ch in c1)

    # Different user, agent, or conversation yields distinct trajectory IDs
    assert c1 != derive_gateway_antigravity_conversation_id("other-user", "antigravity", "conv-123")
    assert c1 != derive_gateway_antigravity_conversation_id("cbribiescas", "shark-tank-panel", "conv-123")
    assert c1 != derive_gateway_antigravity_conversation_id("cbribiescas", "antigravity", "conv-456")


def test_subagent_token_accounting_no_double_counting() -> None:
    """Verify `trajectory_usages` subagent sum excludes main trajectory and avoids double-counting."""
    main_id = "a" * 32
    main_u = sdk_types.UsageMetadata(
        prompt_token_count=1000,
        cached_content_token_count=200,
        candidates_token_count=150,
        thoughts_token_count=50,
        total_token_count=1200,
    )
    shark1_u = sdk_types.UsageMetadata(
        prompt_token_count=400,
        cached_content_token_count=0,
        candidates_token_count=100,
        thoughts_token_count=25,
        total_token_count=525,
    )
    shark2_u = sdk_types.UsageMetadata(
        prompt_token_count=450,
        cached_content_token_count=50,
        candidates_token_count=120,
        thoughts_token_count=30,
        total_token_count=600,
    )
    # In LocalHarness, total_usage equals main + shark1 + shark2
    combined_u = main_u + shark1_u + shark2_u
    post_trajs = {
        main_id: main_u,
        "subagent_shark_1": shark1_u,
        "subagent_shark_2": shark2_u,
    }

    req_tok, conv_tok, req_tc, conv_tc, traj_dict = compute_turn_and_conversation_tokens(
        last_turn_usage=combined_u,
        total_usage=combined_u,
        pre_total_usage=sdk_types.UsageMetadata(),
        pre_trajectory_usages={},
        post_trajectory_usages=post_trajs,
        main_trajectory_ids={main_id, "main"},
        prior_ledger_conv=None,
    )

    assert req_tok["subagent_tokens"] == 525 + 600
    assert req_tok["main_tokens"] == 1200
    assert req_tok["total_tokens"] == 1200 + 525 + 600
    assert req_tok["prompt_tokens"] == 1850
    assert req_tok["cached_tokens"] == 250
    assert req_tok["candidates_tokens"] == 370
    assert req_tok["thoughts_tokens"] == 105
    assert conv_tok == req_tok
    assert req_tc.total_tokens == 2325
    assert conv_tc.total_tokens == 2325
    assert set(traj_dict.keys()) == {main_id, "subagent_shark_1", "subagent_shark_2"}


def test_fast_api_app_mounts_gateway_ui_and_preserves_existing_routes() -> None:
    """Verify `app.fast_api_app.app` exposes `/api/gateway/*`, `/ui`, `/studio`, and ADK/RE routes."""
    from app.fast_api_app import app as main_app

    openapi_paths = set(main_app.openapi().get("paths", {}).keys())
    assert "/api/gateway/health" in openapi_paths
    assert "/api/gateway/agents" in openapi_paths
    assert "/api/gateway/tools" in openapi_paths
    assert "/api/gateway/chat" in openapi_paths
    assert "/api/gateway/chat/stream" in openapi_paths
    assert "/api/gateway/conversations" in openapi_paths
    assert "/api/gateway/conversations/{conversation_id}" in openapi_paths
    assert "/api/gateway/usage/users" in openapi_paths
    assert "/api/gateway/usage/users/{user_id}" in openapi_paths
    assert "/api/gateway/usage/summary" in openapi_paths
    assert "/api/gateway/media/{filepath}" in openapi_paths

    # Existing ADK & ReasoningEngine routes remain intact
    assert "/run" in openapi_paths
    assert "/run_sse" in openapi_paths
    assert "/api/reasoning_engine" in openapi_paths
    assert "/api/stream_reasoning_engine" in openapi_paths

    mount_paths = {getattr(r, "path", "") for r in main_app.routes}
    assert "/studio" in mount_paths
    assert "/ui" in mount_paths

    client = TestClient(main_app)
    redir = client.get("/studio", follow_redirects=False)
    assert redir.status_code in (302, 307)
    assert redir.headers["location"] == "/ui/index.html"

    health = client.get("/api/gateway/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    agents_res = client.get("/api/gateway/agents")
    assert agents_res.status_code == 200
    agents_payload = agents_res.json()
    assert agents_payload["count"] >= 1
    assert any(a["agent_id"] == "antigravity" for a in agents_payload["agents"])

    tools_res = client.get("/api/gateway/tools")
    assert tools_res.status_code == 200
    tools_payload = tools_res.json()
    assert "builtin_tools" in tools_payload
    assert "scenario_tools" in tools_payload

    missing_agent = client.post(
        "/api/gateway/chat",
        json={"user_id": "cbribiescas", "agent_id": "nonexistent-agent-xyz", "message": "hi"},
    )
    assert missing_agent.status_code == 404


def test_gateway_multi_turn_chat_sqlite_ledger_and_media(tmp_path, monkeypatch) -> None:
    """Verify multi-turn `/chat`, SQLite `conversations` & `turns` schemas, and artifact serving."""
    base_dir = str(tmp_path / "harness")
    db_path = str(tmp_path / "harness" / "gateway_usage.db")
    monkeypatch.setenv("ANTIGRAVITY_BASE_DIR", base_dir)
    monkeypatch.setenv("ANTIGRAVITY_GATEWAY_DB", db_path)
    monkeypatch.setenv("DISABLE_BQ_TELEMETRY", "true")

    test_ledger = GatewayLedger(db_path=db_path)
    monkeypatch.setattr(gateway, "ledger", test_ledger)

    cfg = _make_test_config(base_dir)
    monkeypatch.setattr(gateway, "_resolve_agent_config", lambda agent_id: cfg)

    captured_configs: list[LocalAgentConfig] = []
    turn_counter = {"n": 0}

    def _fake_create_agent(config: LocalAgentConfig) -> _FakeAgent:
        captured_configs.append(config)
        turn_counter["n"] += 1
        ag_id = config.conversation_id or "default"

        if turn_counter["n"] == 1:
            tc_step = SimpleNamespace(
                trajectory_id=ag_id,
                step_index=1,
                depth=0,
                type=sdk_types.StepType.TOOL_CALL,
                source=sdk_types.StepSource.MODEL,
                target=sdk_types.StepTarget.ENVIRONMENT,
                status=sdk_types.StepStatus.ACTIVE,
                thinking_delta="Planning HTML5 Kopi Dodge game...",
                thinking="Planning HTML5 Kopi Dodge game...",
                content="",
                content_delta="",
                is_complete_response=False,
                tool_calls=[
                    sdk_types.ToolCall(
                        id="call-dag-1",
                        name="emit_dag_step",
                        args={
                            "node_id": "generator",
                            "node_label": "Game Generator",
                            "status": "completed",
                            "summary": "Generated kopi_dodge.html",
                        },
                    )
                ],
            )
            hook_res = sdk_types.ToolResult(
                id="call-dag-1",
                name="emit_dag_step",
                result={
                    "event_type": "dag_step",
                    "node_id": "generator",
                    "node_label": "Game Generator",
                    "status": "completed",
                    "summary": "Generated kopi_dodge.html",
                },
            )
            final_step = SimpleNamespace(
                trajectory_id=ag_id,
                step_index=2,
                depth=0,
                type=sdk_types.StepType.TEXT_RESPONSE,
                source=sdk_types.StepSource.MODEL,
                target=sdk_types.StepTarget.USER,
                status=sdk_types.StepStatus.DONE,
                thinking="",
                thinking_delta="",
                content="Built Kopi Dodge HTML5 arcade game!",
                content_delta="Built Kopi Dodge HTML5 arcade game!",
                is_complete_response=True,
                tool_calls=[],
            )
            u1 = sdk_types.UsageMetadata(
                prompt_token_count=800,
                cached_content_token_count=100,
                candidates_token_count=200,
                thoughts_token_count=60,
                total_token_count=1060,
            )

            def _create_sandbox_files() -> None:
                html_file = os.path.join(base_dir, "sandbox", "kopi_dodge.html")
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write("<!DOCTYPE html><html><body><canvas id='c'></canvas></body></html>")
                ics_file = os.path.join(base_dir, "sandbox", "crawl.ics")
                with open(ics_file, "w", encoding="utf-8") as f:
                    f.write("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n")

            conv = _FakeConversation(
                conversation_id=ag_id,
                prior_history=[],
                steps_to_yield=[tc_step, final_step],
                hook_calls=[(tc_step, hook_res)],
                hooks=list(config.hooks or []),
                pre_total_usage=sdk_types.UsageMetadata(),
                post_total_usage=u1,
                last_turn_usage=u1,
                pre_traj_usages={},
                post_traj_usages={ag_id: u1},
                on_send_side_effect=_create_sandbox_files,
            )
            return _FakeAgent(config, conv)

        # Turn 2: Resumes same conversation
        prior_step = SimpleNamespace(
            trajectory_id=ag_id,
            step_index=2,
            depth=0,
            is_complete_response=True,
            content="Built Kopi Dodge HTML5 arcade game!",
        )
        t2_step = SimpleNamespace(
            trajectory_id=ag_id,
            step_index=4,
            depth=0,
            type=sdk_types.StepType.TEXT_RESPONSE,
            source=sdk_types.StepSource.MODEL,
            target=sdk_types.StepTarget.USER,
            status=sdk_types.StepStatus.DONE,
            thinking="Adding high-score multiplier...",
            thinking_delta="Adding high-score multiplier...",
            content="Added 2x Teh Tarik combo multiplier!",
            content_delta="Added 2x Teh Tarik combo multiplier!",
            is_complete_response=True,
            tool_calls=[],
        )
        u1 = sdk_types.UsageMetadata(
            prompt_token_count=800,
            cached_content_token_count=100,
            candidates_token_count=200,
            thoughts_token_count=60,
            total_token_count=1060,
        )
        u2_delta = sdk_types.UsageMetadata(
            prompt_token_count=1100,
            cached_content_token_count=500,
            candidates_token_count=150,
            thoughts_token_count=40,
            total_token_count=1290,
        )
        u2_cum = u1 + u2_delta
        conv2 = _FakeConversation(
            conversation_id=ag_id,
            prior_history=[prior_step],
            steps_to_yield=[t2_step],
            hook_calls=[],
            hooks=list(config.hooks or []),
            pre_total_usage=u1,
            post_total_usage=u2_cum,
            last_turn_usage=u2_delta,
            pre_traj_usages={ag_id: u1},
            post_traj_usages={ag_id: u2_cum},
        )
        return _FakeAgent(config, conv2)

    monkeypatch.setattr(gateway, "_create_sdk_agent", _fake_create_agent)

    test_app = FastAPI()
    test_app.include_router(gateway_router)
    client = TestClient(test_app)

    # Health check
    h_resp = client.get("/api/gateway/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "ok"

    # Turn 1 (no conversation_id supplied -> Gateway mints UUID)
    r1 = client.post(
        "/api/gateway/chat",
        json={
            "user_id": "cbribiescas",
            "agent_id": "arcade-builder",
            "message": "Build Kopi Dodge HTML5 game",
        },
    )
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    conv_id = d1["conversation_id"]
    assert conv_id
    expected_ag_id = derive_gateway_antigravity_conversation_id(
        "cbribiescas", "arcade-builder", conv_id
    )
    assert d1["antigravity_conversation_id"] == expected_ag_id
    assert d1["turn_number"] == 1
    assert d1["response_text"] == "Built Kopi Dodge HTML5 arcade game!"
    assert d1["request_tokens"]["total_tokens"] == 1060
    assert d1["conversation_tokens"]["total_tokens"] == 1060
    assert d1["user_tokens"]["total_tokens"] == 1060

    event_types_1 = [e["type"] for e in d1["events"]]
    assert "thought" in event_types_1
    assert "tool_call" in event_types_1
    assert "tool_result" in event_types_1
    assert "dag_step" in event_types_1
    assert "media" in event_types_1

    media_kinds = {m["filename"]: m["kind"] for m in d1["media"]}
    assert media_kinds["kopi_dodge.html"] == "html"
    assert media_kinds["crawl.ics"] == "calendar"

    # Verify serving generated HTML & ICS via /api/gateway/media/{filepath:path}
    html_serve = client.get("/api/gateway/media/sandbox/kopi_dodge.html")
    assert html_serve.status_code == 200
    assert "text/html" in html_serve.headers["content-type"]
    assert "<canvas" in html_serve.text

    ics_serve = client.get("/api/gateway/media/sandbox/crawl.ics")
    assert ics_serve.status_code == 200
    assert "text/calendar" in ics_serve.headers["content-type"]

    # Turn 2 (reuse conversation_id -> resumes identical antigravity_conversation_id)
    r2 = client.post(
        "/api/gateway/chat",
        json={
            "user_id": "cbribiescas",
            "conversation_id": conv_id,
            "agent_id": "arcade-builder",
            "message": "Add a 2x Teh Tarik combo multiplier",
        },
    )
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["conversation_id"] == conv_id
    assert d2["antigravity_conversation_id"] == expected_ag_id
    assert d2["turn_number"] == 2
    assert d2["request_tokens"]["total_tokens"] == 1290
    assert d2["conversation_tokens"]["total_tokens"] == 2350
    assert d2["user_tokens"]["total_tokens"] == 2350

    assert len(captured_configs) == 2
    assert captured_configs[0].conversation_id == expected_ag_id
    assert captured_configs[1].conversation_id == expected_ag_id
    assert (
        captured_configs[1].session_continuation_mode
        == sdk_types.SessionContinuationMode.CREATE_OR_RESUME
    )

    # Verify SQLite schema & rows directly
    with sqlite3.connect(db_path) as conn:
        conv_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
        }
        assert {
            "conversation_id",
            "antigravity_conversation_id",
            "user_id",
            "agent_id",
            "title",
            "turn_count",
            "prompt_tokens",
            "cached_tokens",
            "candidates_tokens",
            "thoughts_tokens",
            "subagent_tokens",
            "total_tokens",
            "created_at",
            "updated_at",
        }.issubset(conv_cols)

        turn_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()
        }
        assert {
            "id",
            "conversation_id",
            "user_id",
            "agent_id",
            "turn_number",
            "message_preview",
            "response_preview",
            "prompt_tokens",
            "cached_tokens",
            "candidates_tokens",
            "thoughts_tokens",
            "subagent_tokens",
            "total_tokens",
            "tool_calls_json",
            "media_json",
            "latency_ms",
            "timestamp",
        }.issubset(turn_cols)

    # Verify conversation & usage REST endpoints
    conv_detail = client.get(f"/api/gateway/conversations/{conv_id}").json()
    assert conv_detail["conversation"]["turn_count"] == 2
    assert conv_detail["conversation"]["total_tokens"] == 2350
    assert len(conv_detail["turns"]) == 2
    assert conv_detail["turns"][0]["total_tokens"] == 1060
    assert conv_detail["turns"][1]["total_tokens"] == 1290

    user_usage = client.get("/api/gateway/usage/users/cbribiescas").json()
    assert user_usage["conversation_count"] == 1
    assert user_usage["turn_count"] == 2
    assert user_usage["total_tokens"] == 2350
    assert user_usage["by_agent"][0]["agent_id"] == "arcade-builder"

    # Brand-new user returns clean zeroed structure
    zero_user = client.get("/api/gateway/usage/users/new-exec").json()
    assert zero_user["conversation_count"] == 0
    assert zero_user["total_tokens"] == 0


def test_gateway_sse_stream_and_subagent_summary(tmp_path, monkeypatch) -> None:
    """Verify `POST /api/gateway/chat/stream` emits live SSE events and records subagent tokens."""
    base_dir = str(tmp_path / "sse_harness")
    db_path = str(tmp_path / "sse_harness" / "gateway_usage.db")
    monkeypatch.setenv("ANTIGRAVITY_BASE_DIR", base_dir)
    monkeypatch.setenv("ANTIGRAVITY_GATEWAY_DB", db_path)
    monkeypatch.setenv("DISABLE_BQ_TELEMETRY", "true")

    test_ledger = GatewayLedger(db_path=db_path)
    monkeypatch.setattr(gateway, "ledger", test_ledger)

    cfg = _make_test_config(base_dir)
    monkeypatch.setattr(gateway, "_resolve_agent_config", lambda agent_id: cfg)

    def _fake_shark_agent(config: LocalAgentConfig) -> _FakeAgent:
        ag_id = config.conversation_id or "shark-main"
        s_call = SimpleNamespace(
            trajectory_id=ag_id,
            step_index=1,
            depth=0,
            type=sdk_types.StepType.TOOL_CALL,
            source=sdk_types.StepSource.MODEL,
            target=sdk_types.StepTarget.ENVIRONMENT,
            status=sdk_types.StepStatus.DONE,
            thinking_delta="Fanning out to 3 Shark subagents...",
            thinking="Fanning out to 3 Shark subagents...",
            content="Subagent finished roast.",
            content_delta="",
            is_complete_response=False,
            tool_calls=[
                sdk_types.ToolCall(
                    id="sub-call-1",
                    name="start_subagent",
                    args={"agent_name": "vc_shark", "prompt": "Roast Rent-a-Retriever"},
                )
            ],
        )
        s_text_1 = SimpleNamespace(
            trajectory_id=ag_id,
            step_index=2,
            depth=0,
            type=sdk_types.StepType.TEXT_RESPONSE,
            source=sdk_types.StepSource.MODEL,
            target=sdk_types.StepTarget.USER,
            status=sdk_types.StepStatus.ACTIVE,
            thinking="",
            thinking_delta="",
            content="Term Sheet: ",
            content_delta="Term Sheet: ",
            is_complete_response=False,
            tool_calls=[],
        )
        s_text_2 = SimpleNamespace(
            trajectory_id=ag_id,
            step_index=2,
            depth=0,
            type=sdk_types.StepType.TEXT_RESPONSE,
            source=sdk_types.StepSource.MODEL,
            target=sdk_types.StepTarget.USER,
            status=sdk_types.StepStatus.DONE,
            thinking="",
            thinking_delta="",
            content="Term Sheet: $50k for 40% puppy equity.",
            content_delta="$50k for 40% puppy equity.",
            is_complete_response=True,
            tool_calls=[],
        )
        main_u = sdk_types.UsageMetadata(
            prompt_token_count=600,
            candidates_token_count=120,
            thoughts_token_count=80,
            total_token_count=800,
        )
        sub_u = sdk_types.UsageMetadata(
            prompt_token_count=900,
            candidates_token_count=300,
            thoughts_token_count=100,
            total_token_count=1300,
        )
        tot_u = main_u + sub_u
        conv = _FakeConversation(
            conversation_id=ag_id,
            prior_history=[],
            steps_to_yield=[s_call, s_text_1, s_text_2],
            hook_calls=[],
            hooks=list(config.hooks or []),
            pre_total_usage=sdk_types.UsageMetadata(),
            post_total_usage=tot_u,
            last_turn_usage=tot_u,
            pre_traj_usages={},
            post_traj_usages={ag_id: main_u, "shark_sub_1": sub_u},
        )
        return _FakeAgent(config, conv)

    monkeypatch.setattr(gateway, "_create_sdk_agent", _fake_shark_agent)

    test_app = FastAPI()
    test_app.include_router(gateway_router)
    client = TestClient(test_app)

    sse_events: list[dict[str, Any]] = []
    with client.stream(
        "POST",
        "/api/gateway/chat/stream",
        json={
            "user_id": "cbribiescas",
            "agent_id": "shark-tank-panel",
            "message": "Pitch Rent-a-Retriever!",
        },
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        for line in resp.iter_lines():
            if line.startswith("data: "):
                sse_events.append(json.loads(line[6:]))

    sse_types = [e["type"] for e in sse_events]
    assert sse_types[0] == "turn_start"
    assert "thought" in sse_types
    assert "tool_call" in sse_types
    assert "dag_step" in sse_types
    assert "tool_result" in sse_types
    assert "text_delta" in sse_types
    assert "usage" in sse_types
    assert sse_types[-1] == "turn_complete"

    complete_ev = sse_events[-1]
    assert complete_ev["response_text"] == "Term Sheet: $50k for 40% puppy equity."
    assert complete_ev["request_tokens"]["subagent_tokens"] == 1300
    assert complete_ev["request_tokens"]["main_tokens"] == 800
    assert complete_ev["request_tokens"]["total_tokens"] == 2100

    summary = client.get("/api/gateway/usage/summary").json()
    assert summary["global"]["total_tokens"] == 2100
    assert summary["global"]["subagent_tokens"] == 1300
    assert summary["by_agent"][0]["agent_id"] == "shark-tank-panel"
    assert summary["by_user"][0]["user_id"] == "cbribiescas"


def test_gateway_media_blocks_path_traversal(tmp_path, monkeypatch) -> None:
    """Verify `/api/gateway/media` strictly blocks symlink or `..` escapes outside base_dir."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    secret_file = tmp_path / "outside_secret.txt"
    secret_file.write_text("top-secret", encoding="utf-8")

    # Symlink inside base_dir pointing outside base_dir
    escape_link = base_dir / "escape.png"
    escape_link.symlink_to(secret_file)

    monkeypatch.setenv("ANTIGRAVITY_BASE_DIR", str(base_dir))

    test_app = FastAPI()
    test_app.include_router(gateway_router)
    client = TestClient(test_app)

    r_symlink = client.get("/api/gateway/media/escape.png")
    assert r_symlink.status_code == 403

    r_missing = client.get("/api/gateway/media/sandbox/nonexistent.png")
    assert r_missing.status_code == 404
