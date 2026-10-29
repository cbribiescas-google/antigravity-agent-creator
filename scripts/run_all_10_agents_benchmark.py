#!/usr/bin/env python3
"""End-to-End 10-DAG Custom Agent Creation & Execution Benchmark via Single API Gateway.

Executes all 10 distinct Agentic DAG scenarios end-to-end through the live FastAPI
Single API Gateway (`/api/gateway/*`):
  - Pre-flight verification of `/api/gateway/health`, `/ui/index.html`, `/studio`,
    `/api/gateway/agents`, `/api/gateway/tools`, and `/api/gateway/usage/summary`.
  - Step A (Creation): Calls `POST /api/gateway/chat` (`agent_id="antigravity"`,
    `user_id="cbribiescas"`) instructing the Antigravity Builder Agent to construct
    each custom DAG agent via `build_custom_agent` (and dynamically synthesize a brand-new
    Python tool via `create_custom_tool` in Scenario #7). Verifies `.md` and `.json`
    agent artifacts on disk.
  - Step B (Execution): Calls `POST /api/gateway/chat/stream` (`agent_id="<agent-id>"`,
    `user_id="cbribiescas"`) streaming live SSE events (`thought`, `tool_call`,
    `tool_result`, `dag_step`, `media`, `usage`, `turn_complete`) to run each agent's
    Fun Mission and verify generated media/HTML/ICS/sandbox deliverables.
  - Step C (Multi-Turn Continuity): Sends a Turn-2 follow-up on Scenario #7's
    `conversation_id` to verify SQLite trajectory resumption and cumulative token
    accounting across turns.
  - Writes verified token tables and artifact summaries to:
      * `gemini-antigravity-demo/reports/ten_agents_token_report.json`
      * `gemini-antigravity-demo/reports/TEN_AGENTS_TOKEN_REPORT.md`
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import datetime
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

DEMO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = DEMO_ROOT / "reports"
AGENTS_DIR = DEMO_ROOT / "agents"
REGISTRY_DIR = AGENTS_DIR / "registry"
DYNAMIC_TOOLS_DIR = DEMO_ROOT / "app" / "dynamic_tools"
DEFAULT_JSON_REPORT = REPORTS_DIR / "ten_agents_token_report.json"
DEFAULT_MD_REPORT = REPORTS_DIR / "TEN_AGENTS_TOKEN_REPORT.md"

DEFAULT_PROJECT = "gemini-enterprise-demo-cb"
DEFAULT_USER_ID = "cbribiescas"
DEFAULT_ADMIN_KEY_PATH = os.path.expanduser(
    "~/.config/gcloud/gemini-enterprise-admin-key.json"
)
SANDBOX_DIR = Path(
    os.environ.get("ANTIGRAVITY_WORKSPACE_DIR", "/tmp/antigravity_harness/sandbox")
)


TOKEN_KEYS = (
    "prompt_tokens",
    "cached_tokens",
    "thoughts_tokens",
    "candidates_tokens",
    "subagent_tokens",
    "main_tokens",
    "total_tokens",
)


def normalize_tokens(raw: dict[str, Any] | None) -> dict[str, int]:
    """Normalizes a Gateway TokenUsage dict with guaranteed integer keys."""
    data = raw or {}
    prompt = int(data.get("prompt_tokens", 0) or 0)
    cached = int(data.get("cached_tokens", 0) or 0)
    thoughts = int(data.get("thoughts_tokens", 0) or 0)
    candidates = int(data.get("candidates_tokens", 0) or 0)
    subagent = int(data.get("subagent_tokens", 0) or 0)
    total = int(data.get("total_tokens", 0) or 0)
    main = int(data.get("main_tokens", max(0, total - subagent)) or 0)
    return {
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "thoughts_tokens": thoughts,
        "candidates_tokens": candidates,
        "subagent_tokens": subagent,
        "main_tokens": main,
        "total_tokens": total,
    }


def sum_token_dicts(items: list[dict[str, int]]) -> dict[str, int]:
    """Sums a list of normalized token dictionaries."""
    totals = dict.fromkeys(TOKEN_KEYS, 0)
    for item in items:
        norm = normalize_tokens(item)
        for k in TOKEN_KEYS:
            totals[k] += norm[k]
    return totals


def ensure_gcp_auth() -> dict[str, Any]:
    """Ensures GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_CLOUD_PROJECT are active and valid."""
    os.environ["TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK"] = "true"
    os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get(
        "GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT
    )
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "global"
    )
    if os.path.exists(DEFAULT_ADMIN_KEY_PATH):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = DEFAULT_ADMIN_KEY_PATH

    cred_path = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_ADMIN_KEY_PATH
    )
    synced_rapt = False

    # Sync fresh rapt_token from gcloud sqlite stores if impersonated SA needs refresh
    gcloud_dir = Path(os.path.expanduser("~/.config/gcloud"))
    cred_db = gcloud_dir / "credentials.db"
    tok_db = gcloud_dir / "access_tokens.db"
    if os.path.exists(cred_path) and cred_db.exists() and tok_db.exists():
        try:
            key_data = json.loads(Path(cred_path).read_text(encoding="utf-8"))
            if key_data.get("type") == "impersonated_service_account":
                import google.auth
                from google.auth.transport.requests import Request

                try:
                    creds, _ = google.auth.load_credentials_from_file(
                        cred_path,
                        scopes=["https://www.googleapis.com/auth/cloud-platform"],
                    )
                    creds.refresh(Request())
                except Exception:
                    # Pull active account + rapt_token from gcloud sqlite db
                    c_conn = sqlite3.connect(str(cred_db))
                    a_conn = sqlite3.connect(str(tok_db))
                    row_a = a_conn.execute(
                        "SELECT account_id, rapt_token FROM access_tokens "
                        "WHERE rapt_token IS NOT NULL ORDER BY token_expiry DESC LIMIT 1"
                    ).fetchone()
                    if row_a:
                        acct_id, rapt_tok = row_a
                        row_c = c_conn.execute(
                            "SELECT value FROM credentials WHERE account_id=?",
                            (acct_id,),
                        ).fetchone()
                        if row_c:
                            val = json.loads(row_c[0])
                            key_data["source_credentials"] = {
                                "client_id": val["client_id"],
                                "client_secret": val["client_secret"],
                                "refresh_token": val["refresh_token"],
                                "rapt_token": rapt_tok,
                                "type": "authorized_user",
                            }
                            Path(cred_path).write_text(
                                json.dumps(key_data, indent=2), encoding="utf-8"
                            )
                            os.chmod(cred_path, 0o600)
                            adc_default = gcloud_dir / "application_default_credentials.json"
                            shutil.copyfile(cred_path, adc_default)
                            os.chmod(adc_default, 0o600)
                            synced_rapt = True
                    c_conn.close()
                    a_conn.close()
        except Exception as exc:
            print(f"[auth] Warning checking rapt_token sync: {exc}", flush=True)

    import google.auth
    from google.auth.transport.requests import Request

    creds, proj = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    sa_email = getattr(creds, "service_account_email", None) or getattr(
        creds, "_service_account_email", "default"
    )
    return {
        "project": os.environ["GOOGLE_CLOUD_PROJECT"],
        "detected_project": proj,
        "credentials_path": cred_path,
        "credentials_type": type(creds).__name__,
        "service_account_email": sa_email,
        "synced_rapt_from_gcloud": synced_rapt,
        "token_valid": bool(creds.valid),
    }


@dataclasses.dataclass(frozen=True)
class ScenarioSpec:
    """Specification for one of the 10 distinct DAG Custom Agents & its Fun Mission."""

    index: int
    agent_id: str
    display_name: str
    dag_topology: str
    dag_pattern_title: str
    description: str
    tool_names: list[str]
    dag_nodes: list[dict[str, str]]
    dag_edges: list[dict[str, str]]
    system_instructions: str
    mission_prompt: str
    enable_subagents: bool = False
    subagent_specs: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    dynamic_tool_spec: dict[str, str] | None = None
    expected_sandbox_files: list[str] = dataclasses.field(default_factory=list)
    multi_turn_followup_prompt: str | None = None

    def build_creation_prompt(self) -> str:
        """Builds a crisp natural-language + structured prompt for the Antigravity Builder Agent."""
        nodes_json = json.dumps(self.dag_nodes)
        edges_json = json.dumps(self.dag_edges)
        subagents_json = json.dumps(self.subagent_specs)
        tools_json = json.dumps(self.tool_names)

        dynamic_tool_block = ""
        if self.dynamic_tool_spec:
            dt = self.dynamic_tool_spec
            dynamic_tool_block = (
                f"STEP 1 (DYNAMIC TOOL SYNTHESIS — REQUIRED FIRST): "
                f"Call `create_custom_tool` to create a brand-new Python tool with:\n"
                f"- `tool_name`: `{dt['tool_name']}`\n"
                f"- `description`: {json.dumps(dt['description'])}\n"
                f"- `python_code`:\n```python\n{dt['python_code']}\n```\n\n"
                f"STEP 2 (BUILD CUSTOM AGENT): Immediately after `create_custom_tool` succeeds, "
                f"call `build_custom_agent` with the exact specification below:\n"
            )
        else:
            dynamic_tool_block = (
                "Call `build_custom_agent` right away (do NOT run shell commands or extra steps) "
                "with the exact specification below:\n"
            )

        return (
            f"Build Custom DAG Agent #{self.index}: **{self.display_name}** (`{self.agent_id}`).\n\n"
            f"{dynamic_tool_block}"
            f"- `agent_id`: `{self.agent_id}`\n"
            f"- `display_name`: {json.dumps(self.display_name)}\n"
            f"- `description`: {json.dumps(self.description)}\n"
            f"- `dag_topology`: `{self.dag_topology}`\n"
            f"- `tool_names`: `{tools_json}`\n"
            f"- `enable_subagents`: `{self.enable_subagents}`\n"
            f"- `subagent_specs_json`: `{subagents_json}`\n"
            f"- `dag_nodes_json`: `{nodes_json}`\n"
            f"- `dag_edges_json`: `{edges_json}`\n"
            f"- `system_instructions`:\n```markdown\n{self.system_instructions}\n```\n\n"
            f"Once `build_custom_agent` returns `status='created'`, reply concisely confirming "
            f"the agent ID, DAG topology, and bound tools."
        )


SCENARIOS: list[ScenarioSpec] = [
    # 1. Linear Sequential Pipeline DAG
    ScenarioSpec(
        index=1,
        agent_id="trailer-director",
        display_name="The Hollywood Trailer Director",
        dag_topology="sequential_pipeline",
        dag_pattern_title="Linear Sequential Pipeline DAG",
        description=(
            "Turns mundane everyday life moments into high-stakes IMAX blockbuster "
            "trailers via a strict 4-stage sequential pipeline (Script -> Theatrical Poster -> "
            "4s Veo 3.1 Video Clip -> Press Kit)."
        ),
        tool_names=[
            "emit_dag_step",
            "create_file",
            "generate_image",
            "generate_video_clip",
        ],
        dag_nodes=[
            {"id": "script_node", "label": "1. 3-Act Voiceover Script", "kind": "step"},
            {"id": "poster_node", "label": "2. Theatrical Poster (Imagen)", "kind": "tool"},
            {"id": "video_node", "label": "3. Climax Clip (Veo 3.1 Lite 4s)", "kind": "tool"},
            {"id": "press_kit_node", "label": "4. Final Blockbuster Pitch", "kind": "output"},
        ],
        dag_edges=[
            {"from": "script_node", "to": "poster_node", "label": "script_ready"},
            {"from": "poster_node", "to": "video_node", "label": "poster_rendered"},
            {"from": "video_node", "to": "press_kit_node", "label": "mp4_rendered"},
        ],
        system_instructions=(
            "You are **The Hollywood Trailer Director**, an Oscar-winning movie trailer auteur "
            "operating as a strict **Linear Sequential Pipeline DAG**.\n"
            "For every mundane scenario:\n"
            "1. Node `script_node`: Write a dramatic 3-act IMAX trailer voiceover script and save it "
            "to `/tmp/antigravity_harness/sandbox/trailer_script.md` via `create_file`, then call "
            "`emit_dag_step(node_id='script_node', node_label='3-Act Voiceover Script', status='completed', summary='Saved trailer_script.md')`.\n"
            "2. Node `poster_node`: Call `generate_image` once to render the official theatrical movie poster, "
            "then call `emit_dag_step(node_id='poster_node', node_label='Theatrical Poster', status='completed', summary='Generated movie poster')`.\n"
            "3. Node `video_node`: Call `generate_video_clip` (`duration_seconds=4`, `aspect_ratio='16:9'`) once "
            "to render a 4-second Veo 3.1 MP4 clip of the climax scene, then call "
            "`emit_dag_step(node_id='video_node', node_label='Climax Video Clip', status='completed', summary='Rendered 4s Veo 3.1 MP4')`.\n"
            "4. Node `press_kit_node`: Call `emit_dag_step(node_id='press_kit_node', node_label='Final Blockbuster Pitch', status='completed', summary='Delivered trailer package')` "
            "and present the dramatic script, tagline, and billing block in Markdown. Never include raw `/tmp/...` Markdown image/video links."
        ),
        mission_prompt=(
            "Turn 'Searching for the unmuted person eating crunchy kettle chips during a tense 45-person "
            "Monday morning executive video call' into a sci-fi suspense blockbuster titled **ECHOES OF CRUNCH**. "
            "Run all 4 pipeline stages in order: save `trailer_script.md`, generate the theatrical poster with "
            "`generate_image`, render a 4-second 16:9 climax trailer clip with `generate_video_clip(clip_name='echoes_of_crunch', duration_seconds=4)`, "
            "and deliver the premiere pitch!"
        ),
        expected_sandbox_files=["trailer_script.md"],
    ),
    # 2. Generator-Verifier Self-Healing Loop DAG
    ScenarioSpec(
        index=2,
        agent_id="arcade-builder",
        display_name="Self-Healing Retro Arcade Factory",
        dag_topology="generator_verifier_loop",
        dag_pattern_title="Generator-Verifier Self-Healing Loop DAG",
        description=(
            "Codes single-file HTML5 Canvas retro arcade games and runs an automated "
            "headless QA verification loop (`validate_html5_game`) until zero errors remain, "
            "finishing with 16-bit arcade cabinet box art."
        ),
        tool_names=[
            "emit_dag_step",
            "create_file",
            "edit_file",
            "view_file",
            "validate_html5_game",
            "generate_image",
        ],
        dag_nodes=[
            {"id": "game_spec", "label": "1. Arcade Spec", "kind": "step"},
            {"id": "html5_generator", "label": "2. HTML5 Canvas Generator", "kind": "step"},
            {"id": "qa_verifier", "label": "3. validate_html5_game QA", "kind": "decision"},
            {"id": "box_art", "label": "4. 16-Bit Cabinet Box Art", "kind": "output"},
        ],
        dag_edges=[
            {"from": "game_spec", "to": "html5_generator", "label": "spec"},
            {"from": "html5_generator", "to": "qa_verifier", "label": "kopi_dodge.html"},
            {"from": "qa_verifier", "to": "html5_generator", "label": "self_heal_if_errors"},
            {"from": "qa_verifier", "to": "box_art", "label": "passed == true"},
        ],
        system_instructions=(
            "You are **Self-Healing Retro Arcade Factory**, operating as a **Generator-Verifier Self-Healing Loop DAG**.\n"
            "Follow this exact loop:\n"
            "1. Node `html5_generator`: Use `create_file` to write a complete, playable single-file HTML5 Canvas game "
            "at `/tmp/antigravity_harness/sandbox/kopi_dodge.html` with `<!DOCTYPE html>`, `<canvas>`, keyboard listeners "
            "(`keydown`/`keyup`), score HUD, collision physics, and `requestAnimationFrame` loop. Emit `emit_dag_step(node_id='html5_generator', node_label='HTML5 Canvas Generator', status='completed')`.\n"
            "2. Node `qa_verifier`: Call `validate_html5_game('/tmp/antigravity_harness/sandbox/kopi_dodge.html')`. "
            "If `passed` is `False`, emit `emit_dag_step(node_id='qa_verifier', node_label='QA Verifier Self-Heal', status='looping')`, "
            "fix every reported issue with `edit_file`/`create_file`, and call `validate_html5_game` again until `passed == True`!\n"
            "3. Node `box_art`: Once `passed == True`, emit `emit_dag_step(node_id='qa_verifier', node_label='QA Verifier Passed', status='completed')`, "
            "call `generate_image` once to render vibrant 16-bit pixel-art arcade cabinet box art, emit `emit_dag_step(node_id='box_art', node_label='16-Bit Cabinet Box Art', status='completed')`, "
            "and summarize the controls, gameplay mechanics, and QA verification checks. Do not include raw `/tmp/...` links."
        ),
        mission_prompt=(
            "Build a playable single-file retro HTML5 Canvas game at `/tmp/antigravity_harness/sandbox/kopi_dodge.html` "
            "called **Kopi Dodge**: an overworked developer slides left/right with ArrowLeft/ArrowRight (or A/D) to catch "
            "falling iced kopi cups (+10 pts, caffeine combo multiplier) while dodging red 'URGENT SYNC' calendar invites (-1 life). "
            "Verify it with `validate_html5_game` (self-healing if any check fails) and generate 16-bit arcade cabinet box art!"
        ),
        expected_sandbox_files=["kopi_dodge.html"],
    ),
    # 3. Parallel Map-Reduce Fan-Out DAG
    ScenarioSpec(
        index=3,
        agent_id="shark-tank-panel",
        display_name="Shark Tank Parallel Pitch Panel",
        dag_topology="parallel_map_reduce",
        dag_pattern_title="Parallel Map-Reduce Fan-Out DAG",
        description=(
            "Fans out startup pitches across 3 specialized Shark investor subagents in parallel "
            "(Numbers Hawk, Hype Visionary, Skeptical Customer), grounds market comps via web search, "
            "and reduces their verdicts into a unified Term Sheet."
        ),
        tool_names=[
            "emit_dag_step",
            "search_web",
            "create_file",
            "start_subagent",
        ],
        enable_subagents=True,
        subagent_specs=[
            {
                "name": "numbers_hawk",
                "description": "Ruthless CFO/unit-economics Shark analyzing CAC, LTV, utilization, insurance liability, and gross margins. Returns concise critique + score /10 + offer.",
            },
            {
                "name": "hype_visionary",
                "description": "Brand & viral growth Shark evaluating category creation, enterprise stickiness, PR moat, and TAM expansion. Returns concise critique + score /10 + offer.",
            },
            {
                "name": "skeptical_customer",
                "description": "Pragmatic HR/Facilities buyer Shark questioning allergies, dog fatigue, procurement red tape, and churn. Returns concise critique + score /10 + offer.",
            },
        ],
        dag_nodes=[
            {"id": "pitch_intake", "label": "1. Pitch Intake & Comps", "kind": "step"},
            {"id": "shark_numbers", "label": "2a. Numbers Hawk Subagent", "kind": "subagent"},
            {"id": "shark_vision", "label": "2b. Hype Visionary Subagent", "kind": "subagent"},
            {"id": "shark_skeptic", "label": "2c. Skeptical Customer Subagent", "kind": "subagent"},
            {"id": "term_sheet_reducer", "label": "3. Term Sheet & 60s Pitch Reducer", "kind": "output"},
        ],
        dag_edges=[
            {"from": "pitch_intake", "to": "shark_numbers", "label": "fan_out"},
            {"from": "pitch_intake", "to": "shark_vision", "label": "fan_out"},
            {"from": "pitch_intake", "to": "shark_skeptic", "label": "fan_out"},
            {"from": "shark_numbers", "to": "term_sheet_reducer", "label": "reduce"},
            {"from": "shark_vision", "to": "term_sheet_reducer", "label": "reduce"},
            {"from": "shark_skeptic", "to": "term_sheet_reducer", "label": "reduce"},
        ],
        system_instructions=(
            "You are **Shark Tank Parallel Pitch Panel**, a **Parallel Map-Reduce Fan-Out DAG** orchestrator.\n"
            "When given a startup pitch:\n"
            "1. Node `pitch_intake`: Call `search_web` once to find 2 real-world corporate wellness / therapy dog / office perk competitors, "
            "and emit `emit_dag_step(node_id='pitch_intake', node_label='Pitch Intake & Market Comps', status='completed')`.\n"
            "2. Map Fan-Out: Invoke all 3 Shark subagents (`numbers_hawk`, `hype_visionary`, and `skeptical_customer`) via `start_subagent` "
            "(ask each subagent for a sharp 120-word roast, unit-economics/buyer verdict, score `/10`, and investment offer or 'I am OUT').\n"
            "3. Node `term_sheet_reducer`: Synthesize all 3 Shark verdicts + real competitors into `/tmp/antigravity_harness/sandbox/rent_a_retriever_term_sheet.md` "
            "via `create_file`, emit `emit_dag_step(node_id='term_sheet_reducer', node_label='Term Sheet Reducer', status='completed')`, "
            "and present the full Shark scorecard table, winning Term Sheet, and rewritten Golden 60-Second Pitch!"
        ),
        mission_prompt=(
            "Pitch: **'Rent-a-Retriever'** — an on-demand B2B SaaS marketplace dispatching certified therapy Golden Retrievers "
            "to corporate boardrooms 15 minutes before quarterly budget reviews ($299/session, asking $500k for 10% equity). "
            "Fan out to all 3 Sharks (`numbers_hawk`, `hype_visionary`, `skeptical_customer`), check real comps via `search_web`, "
            "and save + present the consolidated Term Sheet (`rent_a_retriever_term_sheet.md`)!"
        ),
        expected_sandbox_files=["rent_a_retriever_term_sheet.md"],
    ),
    # 4. Multi-Round Adversarial Cross-Exam DAG
    ScenarioSpec(
        index=4,
        agent_id="supreme-court-debate",
        display_name="Culinary Supreme Court Cross-Exam",
        dag_topology="adversarial_cross_exam",
        dag_pattern_title="Multi-Round Adversarial Cross-Exam DAG",
        description=(
            "Runs a structured multi-round adversarial legal cross-examination between "
            "Counsel PRO and Counsel CON subagents before rendering a Chief Justice Majority Opinion."
        ),
        tool_names=[
            "emit_dag_step",
            "search_web",
            "create_file",
            "start_subagent",
        ],
        enable_subagents=True,
        subagent_specs=[
            {
                "name": "counsel_pro",
                "description": "Structuralist Supreme Court advocate arguing YES: a hotdog in a hinged bun is structurally a taco (3-sided starch geometry / Cube Rule of Food).",
            },
            {
                "name": "counsel_con",
                "description": "Originalist & statutory Supreme Court advocate arguing NO: culinary history, nixtamalized corn tortilla vs leavened wheat roll, USDA & NY tax law distinguish hotdogs from tacos.",
            },
        ],
        dag_nodes=[
            {"id": "docket_open", "label": "1. Certiorari & Precedent Search", "kind": "step"},
            {"id": "counsel_pro_r1", "label": "2. Counsel PRO Opening Brief", "kind": "subagent"},
            {"id": "counsel_con_r1", "label": "3. Counsel CON Counter-Brief", "kind": "subagent"},
            {"id": "rebuttal_clash", "label": "4. Cross-Examination Rebuttal", "kind": "subagent"},
            {"id": "chief_justice_opinion", "label": "5. Chief Justice Majority Opinion", "kind": "output"},
        ],
        dag_edges=[
            {"from": "docket_open", "to": "counsel_pro_r1", "label": "open_hearing"},
            {"from": "counsel_pro_r1", "to": "counsel_con_r1", "label": "pro_arguments"},
            {"from": "counsel_con_r1", "to": "rebuttal_clash", "label": "con_arguments"},
            {"from": "rebuttal_clash", "to": "chief_justice_opinion", "label": "record_closed"},
        ],
        system_instructions=(
            "You are the **Chief Justice of the Culinary Supreme Court**, orchestrating a **Multi-Round Adversarial Cross-Exam DAG**.\n"
            "Follow this exact judicial sequence:\n"
            "1. Node `docket_open`: Call `search_web` once to gather real statutory/culinary precedent (e.g., NY State sandwich tax bulletin TB-ST-835, "
            "USDA food standards, Cube Rule of Food, Ruth Bader Ginsburg's hotdog remarks) and emit `emit_dag_step(node_id='docket_open', node_label='Certiorari & Precedent', status='completed')`.\n"
            "2. Node `counsel_pro_r1`: Invoke `counsel_pro` via `start_subagent` to deliver a punchy 130-word Opening Brief arguing YES.\n"
            "3. Node `counsel_con_r1`: Pass `counsel_pro`'s core thesis to `counsel_con` via `start_subagent` so `counsel_con` directly cross-examines and refutes it in 130 words.\n"
            "4. Node `rebuttal_clash`: Invoke `counsel_pro` once more via `start_subagent` for a sharp 80-word Closing Rebuttal addressing `counsel_con`'s strongest statutory point.\n"
            "5. Node `chief_justice_opinion`: Score both advocates on **Logic (/10)**, **Precedent (/10)**, and **Judicial Wit (/10)**, save the formal ruling to "
            "`/tmp/antigravity_harness/sandbox/hotdog_v_taco_opinion.md` via `create_file`, emit `emit_dag_step(node_id='chief_justice_opinion', node_label='Majority Opinion Issued', status='completed')`, "
            "and deliver the Majority Opinion!"
        ),
        mission_prompt=(
            "Docket No. 26-808: **'Is a hotdog legally and structurally a taco?'** "
            "Search real legal/tax/culinary precedent, run Opening + Cross-Exam + Rebuttal rounds between `counsel_pro` and `counsel_con` "
            "via `start_subagent`, score both sides (/30), and publish the Court's binding Majority Opinion (`hotdog_v_taco_opinion.md`)!"
        ),
        expected_sandbox_files=["hotdog_v_taco_opinion.md"],
    ),
    # 5. Evolutionary Tournament Bracket DAG
    ScenarioSpec(
        index=5,
        agent_id="bot-gladiator-arena",
        display_name="AI Bot Gladiator Tournament Arena",
        dag_topology="evolutionary_tournament",
        dag_pattern_title="Evolutionary Tournament Bracket DAG",
        description=(
            "Writes 3 competing Python Prisoner's Dilemma strategy bots, pits them in a "
            "deterministic 2,000-round arena (`run_bot_tournament`), evolves a counter-strategy "
            "challenger bot from match telemetry, and runs the Championship Final."
        ),
        tool_names=[
            "emit_dag_step",
            "create_file",
            "edit_file",
            "view_file",
            "run_bot_tournament",
        ],
        dag_nodes=[
            {"id": "code_gen_bots", "label": "1. Write 3 Gen-1 Bots", "kind": "step"},
            {"id": "qualifier_arena", "label": "2. Qualifier 2,000-Round Arena", "kind": "tool"},
            {"id": "evolve_challenger", "label": "3. Mutate/Evolve Challenger Bot", "kind": "step"},
            {"id": "championship_final", "label": "4. Championship 2,000-Round Final", "kind": "output"},
        ],
        dag_edges=[
            {"from": "code_gen_bots", "to": "qualifier_arena", "label": "3_bots_ready"},
            {"from": "qualifier_arena", "to": "evolve_challenger", "label": "match_matrix"},
            {"from": "evolve_challenger", "to": "championship_final", "label": "gen2_bot"},
        ],
        system_instructions=(
            "You are **AI Bot Gladiator Tournament Arena**, running an **Evolutionary Tournament Bracket DAG**.\n"
            "Every Python bot file MUST define `decide(my_history: list[str], opponent_history: list[str]) -> str` returning `'C'` or `'D'`.\n"
            "Execute these 4 stages:\n"
            "1. Node `code_gen_bots`: Use `create_file` inside `/tmp/antigravity_harness/sandbox/` to write 3 distinct Generation-1 strategy bots:\n"
            "   - `bot_tit_for_tat.py` (cooperates round 1, then mirrors opponent's last move)\n"
            "   - `bot_grim_trigger.py` (cooperates until opponent ever defects once, then defects forever)\n"
            "   - `bot_periodic_raider.py` (defects every 4th round to exploit naive cooperators, otherwise mirrors)\n"
            "   Emit `emit_dag_step(node_id='code_gen_bots', node_label='3 Gen-1 Bots Coded', status='completed')`.\n"
            "2. Node `qualifier_arena`: Call `run_bot_tournament('bot_tit_for_tat.py', 'bot_grim_trigger.py', 'bot_periodic_raider.py', rounds=2000)` and emit `emit_dag_step(node_id='qualifier_arena', node_label='Qualifier 2,000-Round Arena', status='completed')`.\n"
            "3. Node `evolve_challenger`: Analyze the Round 1 `match_matrix` and replace the lowest-scoring bot by creating `bot_omega_adaptive.py` "
            "(an evolved strategy tailored to beat the top two survivors, e.g., Tit-for-Two-Tats / handshake detector / endgame defector). Emit `emit_dag_step(node_id='evolve_challenger', node_label='Evolved Omega Bot', status='completed')`.\n"
            "4. Node `championship_final`: Call `run_bot_tournament` (`rounds=2000`) pitting the top 2 Qualifier survivors against `bot_omega_adaptive.py`, "
            "emit `emit_dag_step(node_id='championship_final', node_label='Championship Final Completed', status='completed')`, and report both leaderboards!"
        ),
        mission_prompt=(
            "Run the **AI Bot Gladiator Prisoner's Dilemma Championship**! Code the 3 Generation-1 Python bots in `/tmp/antigravity_harness/sandbox/`, "
            "execute the 2,000-round Qualifier via `run_bot_tournament`, evolve `bot_omega_adaptive.py` to replace the weakest bot based on the match matrix, "
            "run the 2,000-round Championship Final via `run_bot_tournament`, and present the exact scores and Grand Champion!"
        ),
        expected_sandbox_files=[
            "bot_tit_for_tat.py",
            "bot_grim_trigger.py",
            "bot_omega_adaptive.py",
            "tournament_results.json",
        ],
    ),
    # 6. Multimodal Producer-Vision Critic Reflection DAG
    ScenarioSpec(
        index=6,
        agent_id="perfectionist-art-director",
        display_name="Perfectionist Multimodal Art Director",
        dag_topology="multimodal_vision_critic",
        dag_pattern_title="Multimodal Producer-Vision Critic Reflection DAG",
        description=(
            "Renders a V1 comic draft with `generate_image`, visually inspects the actual pixels "
            "via `view_file`, logs structured visual flaws & prompt upgrades via `log_vision_critique`, "
            "and renders a refined V2 Masterpiece."
        ),
        tool_names=[
            "emit_dag_step",
            "create_file",
            "view_file",
            "generate_image",
            "log_vision_critique",
        ],
        dag_nodes=[
            {"id": "storyboard", "label": "1. 3-Panel Comic Script", "kind": "step"},
            {"id": "render_v1", "label": "2. Render Draft V1 (Imagen)", "kind": "tool"},
            {"id": "vision_critic", "label": "3. view_file + log_vision_critique", "kind": "decision"},
            {"id": "render_v2", "label": "4. Render Masterpiece V2", "kind": "output"},
        ],
        dag_edges=[
            {"from": "storyboard", "to": "render_v1", "label": "draft_prompt"},
            {"from": "render_v1", "to": "vision_critic", "label": "inspect_pixels"},
            {"from": "vision_critic", "to": "render_v2", "label": "upgraded_prompt"},
        ],
        system_instructions=(
            "You are **Perfectionist Multimodal Art Director**, executing a **Multimodal Producer-Vision Critic Reflection DAG**.\n"
            "Follow these exact 4 steps:\n"
            "1. Node `storyboard`: Write a witty 3-panel comic script and save it to `/tmp/antigravity_harness/sandbox/comic_storyboard.md` via `create_file`. "
            "Emit `emit_dag_step(node_id='storyboard', node_label='3-Panel Storyboard', status='completed')`.\n"
            "2. Node `render_v1`: Call `generate_image` to create Draft V1 (saving inside `/tmp/antigravity_harness/sandbox/comic_draft_v1.png` if output_path parameter exists, or note the returned path). "
            "Emit `emit_dag_step(node_id='render_v1', node_label='Draft V1 Rendered', status='completed')`.\n"
            "3. Node `vision_critic`: Call `view_file` on the actual Draft V1 image path returned by `generate_image` to visually inspect its composition, legibility, and lighting! "
            "Then call `log_vision_critique(draft_image_path=..., composition_score=..., lighting_score=..., flaws_found=..., upgraded_prompt=...)` with concrete visual observations. "
            "Emit `emit_dag_step(node_id='vision_critic', node_label='Vision Critique Logged', status='completed')`.\n"
            "4. Node `render_v2`: Call `generate_image` a second time using your `upgraded_prompt` to produce the polished Masterpiece V2! "
            "Emit `emit_dag_step(node_id='render_v2', node_label='Masterpiece V2 Rendered', status='completed')` and present a side-by-side Creative Director reflection (no raw `/tmp/` Markdown links)."
        ),
        mission_prompt=(
            "Create a 3-panel workplace comic strip about an engineer accidentally sharing their entire ultrawide screen "
            "with 47 chaotic browser tabs open ('how to exit vim', 'can kubernetes feel fear', 'best kaya toast near me') "
            "during a Q4 board presentation. Render Draft V1 with `generate_image`, visually critique the Draft V1 image using "
            "`view_file` + `log_vision_critique`, and render the upgraded Masterpiece V2 with `generate_image`!"
        ),
        expected_sandbox_files=["comic_storyboard.md", "vision_critiques.json"],
    ),
    # 7. Conditional Router Branching DAG (+ Dynamic Tool Synthesis via create_custom_tool!)
    ScenarioSpec(
        index=7,
        agent_id="mythbuster-router",
        display_name="Conditional Router MythBuster Lab",
        dag_topology="conditional_router",
        dag_pattern_title="Conditional Router Branching DAG (+ Dynamic Tool Synthesis)",
        description=(
            "Verifies viral physics/volume bar-bets using a dynamically synthesized volumetric tool "
            "(`compute_loch_ness_displacement`) plus `verify_claim_math`, then dynamically branches "
            "to EITHER `CONFIRMED_INFOGRAPHIC` (renders visual infographic) OR `BUSTED_ORIGIN_TRACE` (traces viral myth origin)."
        ),
        dynamic_tool_spec={
            "tool_name": "compute_loch_ness_displacement",
            "description": (
                "Computes total volumetric displacement and water-level rise when submerging a "
                "population inside Loch Ness (7.45 billion m^3 volume, 56.4 km^2 surface area)."
            ),
            "python_code": (
                "from typing import Any\n\n"
                "def compute_loch_ness_displacement(\n"
                "    human_count: int = 8100000000,\n"
                "    avg_human_mass_kg: float = 62.0,\n"
                "    human_density_kg_m3: float = 985.0,\n"
                "    loch_ness_volume_m3: float = 7450000000.0,\n"
                "    loch_ness_surface_area_m2: float = 56400000.0,\n"
                ") -> dict[str, Any]:\n"
                '    """Computes human volumetric displacement and water-level rise inside Loch Ness.\n\n'
                "    Args:\n"
                "        human_count: Total number of people submerged.\n"
                "        avg_human_mass_kg: Average mass per human in kilograms.\n"
                "        human_density_kg_m3: Average human body density in kg/m^3.\n"
                "        loch_ness_volume_m3: Volume of Loch Ness in cubic meters (~7.45e9 m^3).\n"
                "        loch_ness_surface_area_m2: Surface area of Loch Ness in square meters (~5.64e7 m^2).\n\n"
                "    Returns:\n"
                "        Dictionary with total human volume, % of Loch Ness filled, and water level rise in meters.\n"
                '    """\n'
                "    per_human_m3 = float(avg_human_mass_kg) / float(human_density_kg_m3)\n"
                "    total_human_m3 = float(human_count) * per_human_m3\n"
                "    pct_filled = (total_human_m3 / float(loch_ness_volume_m3)) * 100.0\n"
                "    water_rise_m = total_human_m3 / float(loch_ness_surface_area_m2)\n"
                "    return {\n"
                '        "human_count": int(human_count),\n'
                '        "per_human_volume_m3": round(per_human_m3, 6),\n'
                '        "total_human_volume_m3": round(total_human_m3, 2),\n'
                '        "loch_ness_volume_m3": float(loch_ness_volume_m3),\n'
                '        "percent_of_loch_filled": round(pct_filled, 4),\n'
                '        "water_level_rise_m": round(water_rise_m, 4),\n'
                '        "fits_entire_humanity": total_human_m3 < float(loch_ness_volume_m3),\n'
                "    }\n"
            ),
        },
        tool_names=[
            "emit_dag_step",
            "search_web",
            "compute_loch_ness_displacement",
            "verify_claim_math",
            "generate_image",
            "create_file",
        ],
        dag_nodes=[
            {"id": "claim_intake", "label": "1. Claim & Primary Data Search", "kind": "step"},
            {"id": "math_router", "label": "2. compute_loch_ness_displacement + verify_claim_math", "kind": "decision"},
            {"id": "confirmed_infographic", "label": "3a. CONFIRMED -> Scale Infographic", "kind": "tool"},
            {"id": "busted_origin_trace", "label": "3b. BUSTED -> Viral Origin Trace", "kind": "tool"},
            {"id": "verdict_receipt", "label": "4. Official MythBuster Receipt", "kind": "output"},
        ],
        dag_edges=[
            {"from": "claim_intake", "to": "math_router", "label": "primary_constants"},
            {"from": "math_router", "to": "confirmed_infographic", "label": "CONFIRMED_INFOGRAPHIC"},
            {"from": "math_router", "to": "busted_origin_trace", "label": "BUSTED_ORIGIN_TRACE"},
            {"from": "confirmed_infographic", "to": "verdict_receipt", "label": "done"},
            {"from": "busted_origin_trace", "to": "verdict_receipt", "label": "done"},
        ],
        system_instructions=(
            "You are **Conditional Router MythBuster Lab**, executing a **Conditional Router Branching DAG**.\n"
            "For any volumetric/physics bar-bet claim:\n"
            "1. Node `claim_intake`: Use `search_web` if needed to confirm primary physical constants (e.g., Loch Ness volume ~7.45 km^3 = 7.45e9 m^3, area 56.4 km^2) "
            "and emit `emit_dag_step(node_id='claim_intake', node_label='Primary Data Verified', status='completed')`.\n"
            "2. Node `math_router`: Call `compute_loch_ness_displacement(...)` AND call `verify_claim_math(...)` to obtain `route_branch` (`'CONFIRMED_INFOGRAPHIC'` or `'BUSTED_ORIGIN_TRACE'`). "
            "Emit `emit_dag_step(node_id='math_router', node_label='Math Router Evaluated', status='completed')`.\n"
            "3. **STRICT CONDITIONAL BRANCHING**:\n"
            "   - If `route_branch == 'CONFIRMED_INFOGRAPHIC'`: Execute ONLY `confirmed_infographic` — call `generate_image` once to render a scientific cross-section infographic, "
            "and emit `emit_dag_step(node_id='confirmed_infographic', node_label='Confirmed Infographic Rendered', status='completed')` (skip `busted_origin_trace`!).\n"
            "   - If `route_branch == 'BUSTED_ORIGIN_TRACE'`: Execute ONLY `busted_origin_trace` — call `search_web` to trace how the exaggerated myth spread online, "
            "and emit `emit_dag_step(node_id='busted_origin_trace', node_label='Busted Origin Traced', status='completed')` (do NOT call `generate_image`!).\n"
            "4. Node `verdict_receipt`: Save `/tmp/antigravity_harness/sandbox/mythbuster_receipt.md` via `create_file`, emit `emit_dag_step(node_id='verdict_receipt', node_label='Verdict Delivered', status='completed')`, "
            "and issue your official **CONFIRMED** or **BUSTED** verdict with exact numbers (no raw `/tmp/` links)."
        ),
        mission_prompt=(
            "Bar-bet claim: **'All 8.1 billion humans on Earth could be submerged inside Scotland's Loch Ness at the exact same time "
            "and take up LESS than 10% of Loch Ness's water volume (`total_human_volume_m3 <= 745000000.0`).'** "
            "Verify Loch Ness's dimensions via `search_web`, run BOTH `compute_loch_ness_displacement` and `verify_claim_math` "
            "(`expected_threshold=745000000.0`, `comparison='<='`), follow ONLY the matching `route_branch`, save `mythbuster_receipt.md`, and present the verdict!"
        ),
        expected_sandbox_files=["mythbuster_receipt.md"],
        multi_turn_followup_prompt=(
            "Follow-up bar-bet on our exact same Loch Ness numbers: my friend now claims submerging all 8.1 billion humans "
            "would raise Loch Ness's water level by **at least 50 meters** (`water_level_rise_m >= 50.0`). "
            "Run `verify_claim_math` (`expected_threshold=50.0`, `comparison='>='`) using our `water_level_rise_m` result and follow the `BUSTED_ORIGIN_TRACE` branch concisely!"
        ),
    ),
    # 8. Dynamic Tree Search & Prune DAG
    ScenarioSpec(
        index=8,
        agent_id="six-degrees-detective",
        display_name="Six-Degrees Tree Search & Prune Detective",
        dag_topology="tree_search_prune",
        dag_pattern_title="Dynamic Tree Search & Prune DAG",
        description=(
            "Connects two seemingly unrelated concepts in <=4 verified factual hops by expanding "
            "candidate web search branches in a beam tree and explicitly pruning dead/longer branches "
            "with `record_pruned_branch`."
        ),
        tool_names=[
            "emit_dag_step",
            "search_web",
            "read_url_content",
            "record_pruned_branch",
            "create_file",
        ],
        dag_nodes=[
            {"id": "seed_node", "label": "1. Seed: Bubble Tea", "kind": "step"},
            {"id": "branch_alpha", "label": "2a. Candidate Branch A", "kind": "step"},
            {"id": "branch_beta", "label": "2b. Candidate Branch B (Pruned)", "kind": "decision"},
            {"id": "hop_verifier", "label": "3. Verify <=4 Hops to Apollo 11", "kind": "step"},
            {"id": "evidence_dossier", "label": "4. Verified Six-Degrees Dossier", "kind": "output"},
        ],
        dag_edges=[
            {"from": "seed_node", "to": "branch_alpha", "label": "expand"},
            {"from": "seed_node", "to": "branch_beta", "label": "expand"},
            {"from": "branch_beta", "to": "hop_verifier", "label": "pruned_dead_end"},
            {"from": "branch_alpha", "to": "hop_verifier", "label": "surviving_beam"},
            {"from": "hop_verifier", "to": "evidence_dossier", "label": "verified_<=4_hops"},
        ],
        system_instructions=(
            "You are **Six-Degrees Tree Search & Prune Detective**, executing a **Dynamic Tree Search & Prune DAG**.\n"
            "To connect Concept A to Concept B in `<= 4` factual hops:\n"
            "1. Node `seed_node`: Emit `emit_dag_step(node_id='seed_node', node_label='Seed Entity Initialized', status='completed')` and use `search_web` to explore at least 2 distinct candidate hop paths from the origin.\n"
            "2. Pruning Step (`branch_beta`): Whenever a candidate path requires >4 hops, relies on vague trivia, or is weaker than your best bridge, "
            "explicitly call `record_pruned_branch(branch_name=..., reason=...)` (prune at least 1 candidate branch!).\n"
            "3. Node `hop_verifier`: Verify every hop in your winning `<= 4`-hop chain via `search_web` so every link names a specific real person, company, institution, treaty, or mission with dates. "
            "Emit `emit_dag_step(node_id='hop_verifier', node_label='All Hops Fact-Checked', status='completed')`.\n"
            "4. Node `evidence_dossier`: Save the complete hop chain and pruned-branch log summary to `/tmp/antigravity_harness/sandbox/six_degrees_chain.md` via `create_file`, "
            "emit `emit_dag_step(node_id='evidence_dossier', node_label='Six-Degrees Dossier Saved', status='completed')`, and present the numbered hop chain!"
        ),
        mission_prompt=(
            "Connect **'Bubble Tea (invented in Taiwan in the 1980s)'** to the **'Apollo 11 Moon Landing (July 1969)'** "
            "in **at most 4 verified factual hops**! Expand at least 2 candidate paths using `search_web`, prune at least 1 weaker/longer "
            "branch using `record_pruned_branch`, verify each surviving hop with real historical facts/dates, and write the final chain to "
            "`/tmp/antigravity_harness/sandbox/six_degrees_chain.md`!"
        ),
        expected_sandbox_files=["six_degrees_chain.md", "pruned_branches.jsonl"],
    ),
    # 9. Hourglass Gather-Solve-Publish DAG
    ScenarioSpec(
        index=9,
        agent_id="foodie-hourglass-solver",
        display_name="Hourglass Hawker Foodie Optimizer",
        dag_topology="hourglass_gather_solve_publish",
        dag_pattern_title="Hourglass Gather-Solve-Publish DAG",
        description=(
            "Gathers wide real-world hawker stall candidates via web search, squeezes them through a "
            "deterministic knapsack/route solver (`solve_crawl_constraints`) under budget/time/weather limits, "
            "and fans back out to publish an `.ics` calendar, an HTML route card, and a watercolor postcard."
        ),
        tool_names=[
            "emit_dag_step",
            "search_web",
            "solve_crawl_constraints",
            "export_ics_calendar",
            "create_file",
            "generate_image",
        ],
        dag_nodes=[
            {"id": "wide_gather", "label": "1. Wide Gather: Hawker Candidates", "kind": "step"},
            {"id": "narrow_solver", "label": "2. Bottleneck: solve_crawl_constraints", "kind": "decision"},
            {"id": "pub_ics", "label": "3a. Publish .ics Calendar", "kind": "tool"},
            {"id": "pub_html", "label": "3b. Publish HTML Itinerary Card", "kind": "tool"},
            {"id": "pub_postcard", "label": "3c. Publish Watercolor Postcard", "kind": "output"},
        ],
        dag_edges=[
            {"from": "wide_gather", "to": "narrow_solver", "label": "6+_stalls_json"},
            {"from": "narrow_solver", "to": "pub_ics", "label": "optimal_3_stops"},
            {"from": "narrow_solver", "to": "pub_html", "label": "optimal_3_stops"},
            {"from": "narrow_solver", "to": "pub_postcard", "label": "optimal_3_stops"},
        ],
        system_instructions=(
            "You are **Hourglass Hawker Foodie Optimizer**, operating as an **Hourglass Gather-Solve-Publish DAG**.\n"
            "Execute the 3-tier hourglass architecture:\n"
            "1. **Wide Gather (`wide_gather`)**: Use `search_web` to gather at least 6 real candidate stalls/dishes (2+ starters/snacks/drinks, "
            "2+ mains, 2+ desserts) with realistic `name`, `course` (`'starter'`, `'main'`, `'dessert'`), `price_sgd`, `minutes`, `walk_minutes`, `rating`, `sheltered` (`True`/`False`), and `location`. "
            "Emit `emit_dag_step(node_id='wide_gather', node_label='Gathered Candidate Stalls', status='completed')`.\n"
            "2. **Narrow Bottleneck (`narrow_solver`)**: Pass the JSON list of candidates to `solve_crawl_constraints(candidates_json=..., max_budget_sgd=..., max_minutes=..., weather_condition=...)` "
            "to compute the mathematically optimal 3-stop crawl! Emit `emit_dag_step(node_id='narrow_solver', node_label='Optimal Crawl Solved', status='completed')`.\n"
            "3. **Wide Publish Fan-Out**:\n"
            "   - `pub_ics`: Call `export_ics_calendar(crawl_title=..., stops_json=..., output_filename='maxwell_crawl.ics')`.\n"
            "   - `pub_html`: Call `create_file` to save a stylish self-contained HTML5 itinerary card at `/tmp/antigravity_harness/sandbox/maxwell_crawl_card.html`.\n"
            "   - `pub_postcard`: Call `generate_image` once to illustrate a warm watercolor foodie postcard featuring the 3 winning dishes.\n"
            "   Emit `emit_dag_step(node_id='pub_postcard', node_label='Published ICS + HTML + Postcard', status='completed')` and summarize the itinerary (no raw `/tmp/` links)."
        ),
        mission_prompt=(
            "Plan an optimal 3-stop Singapore hawker crawl (**Starter + Main + Dessert**) around **Maxwell Food Centre & Chinatown** "
            "under a strict **S$20.00 max budget** and **75-minute max window** during a **tropical rainstorm** (`weather_condition='rain'`). "
            "Gather 6+ real Maxwell/Chinatown stalls via `search_web`, solve via `solve_crawl_constraints`, and publish all 3 outputs: "
            "`maxwell_crawl.ics` via `export_ics_calendar`, `/tmp/antigravity_harness/sandbox/maxwell_crawl_card.html` via `create_file`, "
            "and a watercolor foodie postcard via `generate_image`!"
        ),
        expected_sandbox_files=["maxwell_crawl.ics", "maxwell_crawl_card.html"],
    ),
    # 10. Stateful HITL / Crypto RNG State Machine DAG
    ScenarioSpec(
        index=10,
        agent_id="corporate-dnd-master",
        display_name="Corporate D&D Cryptographic State Machine",
        dag_topology="stateful_hitl_rng_machine",
        dag_pattern_title="Stateful HITL / Crypto RNG State Machine DAG",
        description=(
            "Runs a persistent corporate RPG state machine backed by `hero_state.json` "
            "(`manage_hero_state`), interactive player choices (`ask_question` when in live UI), "
            "genuine OS cryptographic d20 rolls (`roll_crypto_d20`), and custom boss encounter art."
        ),
        tool_names=[
            "emit_dag_step",
            "manage_hero_state",
            "roll_crypto_d20",
            "generate_image",
            "ask_question",
            "create_file",
        ],
        dag_nodes=[
            {"id": "load_state", "label": "1. Load/Init Hero JSON", "kind": "tool"},
            {"id": "boss_encounter", "label": "2. Stage Boss Encounter", "kind": "step"},
            {"id": "player_choice", "label": "3. HITL Choice / Action", "kind": "decision"},
            {"id": "crypto_d20", "label": "4. OS CSPRNG roll_crypto_d20", "kind": "tool"},
            {"id": "persist_and_art", "label": "5. Save Hero State & Boss Art", "kind": "output"},
        ],
        dag_edges=[
            {"from": "load_state", "to": "boss_encounter", "label": "hero_state.json"},
            {"from": "boss_encounter", "to": "player_choice", "label": "options"},
            {"from": "player_choice", "to": "crypto_d20", "label": "selected_move"},
            {"from": "crypto_d20", "to": "persist_and_art", "label": "strict_rng_outcome"},
        ],
        system_instructions=(
            "You are **Corporate D&D Cryptographic State Machine**, a tabletop RPG Dungeon Master with persistent state and true cryptographic dice.\n"
            "State Machine Rules:\n"
            "1. Node `load_state`: Call `manage_hero_state` (`action='get'` or `'init'`) to load `/tmp/antigravity_harness/sandbox/hero_state.json`, "
            "and emit `emit_dag_step(node_id='load_state', node_label='Hero State Loaded', status='completed')`.\n"
            "2. Node `player_choice`: In interactive sessions where the user has NOT yet chosen an action, you may use `ask_question` to offer 3 tactical corporate moves. "
            "HOWEVER, if the user's message already specifies an action or states `AUTOMATED BENCHMARK ENCOUNTER`, do NOT call `ask_question` — proceed immediately with their stated move!\n"
            "3. Node `crypto_d20`: Call `roll_crypto_d20(modifier=..., skill_name=...)` to roll a genuine OS `secrets.randbelow(20)+1` d20 die. NEVER invent or override the roll! "
            "Emit `emit_dag_step(node_id='crypto_d20', node_label='Cryptographic d20 Rolled', status='completed')`.\n"
            "4. Node `persist_and_art`: Call `manage_hero_state(action='update', ...)` to apply signed `hp_delta` (negative on `FAILURE`/`CRITICAL_FAILURE`, `0` or `+hp` on success) "
            "and grant a hilarious corporate artifact via `item_to_add` on `PARTIAL_SUCCESS` or better. Then call `generate_image` once to render dark-fantasy corporate boss art, "
            "emit `emit_dag_step(node_id='persist_and_art', node_label='State Persisted & Art Rendered', status='completed')`, and narrate the battle with exact roll telemetry (no raw `/tmp/` links)!"
        ),
        mission_prompt=(
            "AUTOMATED BENCHMARK ENCOUNTER (do NOT call `ask_question` — execute my move directly without blocking!): "
            "Initialize my hero **'Spreadsheet Paladin'** (`manage_hero_state(action='init', hero_name='Spreadsheet Paladin')`) as I enter the Q4 War Room "
            "where the **3-Headed Hydra of Scope Creep** attacks! Execute my Turn-1 move **'Cast VLOOKUP Smite & Freeze Scope'** with "
            "`roll_crypto_d20(modifier=4, skill_name='VLOOKUP Smite')`, persist the resulting HP/loot update via `manage_hero_state(action='update', ...)`, "
            "and call `generate_image` to illustrate the epic boardroom battle!"
        ),
        expected_sandbox_files=["hero_state.json"],
    ),
]


def find_free_port() -> int:
    """Finds an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class ManagedGatewayServer:
    """Context manager that launches `uvicorn app.fast_api_app:app` if no external URL is passed."""

    def __init__(
        self,
        gateway_url: str | None = None,
        port: int | None = None,
        fresh_db: bool = False,
    ) -> None:
        self.external_url = gateway_url.rstrip("/") if gateway_url else None
        self.port = port or find_free_port()
        self.fresh_db = fresh_db
        self.process: subprocess.Popen[str] | None = None
        self.log_path = Path("/tmp/antigravity_harness/gateway_server.log")
        self._log_fh: Any = None

    @property
    def base_url(self) -> str:
        if self.external_url:
            return self.external_url
        return f"http://127.0.0.1:{self.port}"

    async def __aenter__(self) -> str:
        if self.external_url:
            await self._wait_healthy()
            return self.base_url

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        gw_db = Path(
            os.environ.get(
                "ANTIGRAVITY_GATEWAY_DB", "/tmp/antigravity_harness/gateway_usage.db"
            )
        )
        if self.fresh_db and gw_db.exists():
            gw_db.unlink()

        env = dict(os.environ)
        env["TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK"] = "true"
        env["GOOGLE_CLOUD_PROJECT"] = env.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT)
        env["GOOGLE_APPLICATION_CREDENTIALS"] = env.get(
            "GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_ADMIN_KEY_PATH
        )

        os.makedirs(self.log_path.parent, exist_ok=True)
        self._log_fh = open(self.log_path, "w", encoding="utf-8")
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.fast_api_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]
        print(
            f"[server] Launching FastAPI Gateway on {self.base_url} (logs: {self.log_path})...",
            flush=True,
        )
        self.process = subprocess.Popen(
            cmd,
            cwd=str(DEMO_ROOT),
            env=env,
            stdout=self._log_fh,
            stderr=subprocess.STDOUT,
            text=True,
        )
        await self._wait_healthy()
        return self.base_url

    async def _wait_healthy(self) -> None:
        deadline = time.monotonic() + 60.0
        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.monotonic() < deadline:
                if self.process is not None and self.process.poll() is not None:
                    tail = ""
                    if self.log_path.exists():
                        tail = self.log_path.read_text(encoding="utf-8")[-2000:]
                    raise RuntimeError(
                        f"Gateway uvicorn exited prematurely with code {self.process.returncode}:\n{tail}"
                    )
                try:
                    resp = await client.get(f"{self.base_url}/api/gateway/health")
                    if resp.status_code == 200:
                        print(
                            f"[server] Gateway healthy: {resp.json()}",
                            flush=True,
                        )
                        return
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        raise TimeoutError(f"Timed out waiting for {self.base_url}/api/gateway/health")

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self._log_fh is not None:
            self._log_fh.close()


async def run_preflight_checks(client: httpx.AsyncClient, base_url: str) -> dict[str, Any]:
    """Verifies Gateway REST endpoints and Live Studio UI static serving."""
    checks: dict[str, Any] = {}

    # 1. Health
    r_health = await client.get(f"{base_url}/api/gateway/health")
    r_health.raise_for_status()
    checks["health"] = {"status_code": r_health.status_code, "body": r_health.json()}

    # 2. UI index.html & /studio redirect
    r_ui = await client.get(f"{base_url}/ui/index.html")
    r_ui.raise_for_status()
    r_studio = await client.get(f"{base_url}/studio", follow_redirects=True)
    r_studio.raise_for_status()
    checks["ui"] = {
        "ui_index_status": r_ui.status_code,
        "ui_index_bytes": len(r_ui.content),
        "studio_redirect_status": r_studio.status_code,
        "contains_gateway_binding": "/api/gateway" in r_ui.text or "app.js" in r_ui.text,
    }

    # 3. Agents catalog
    r_agents = await client.get(f"{base_url}/api/gateway/agents")
    r_agents.raise_for_status()
    agents_payload = r_agents.json()
    agent_ids = [
        a.get("agent_id")
        for a in (
            agents_payload.get("agents", [])
            if isinstance(agents_payload, dict)
            else agents_payload
        )
    ]
    checks["agents_initial"] = {
        "status_code": r_agents.status_code,
        "agent_ids": agent_ids,
        "has_antigravity": "antigravity" in agent_ids,
    }

    # 4. Tools catalog
    r_tools = await client.get(f"{base_url}/api/gateway/tools")
    r_tools.raise_for_status()
    tools_payload = r_tools.json()
    checks["tools_initial"] = {
        "status_code": r_tools.status_code,
        "keys": list(tools_payload.keys()) if isinstance(tools_payload, dict) else [],
    }

    # 5. Usage summary & per-user usage
    r_sum = await client.get(f"{base_url}/api/gateway/usage/summary")
    r_sum.raise_for_status()
    r_usr = await client.get(f"{base_url}/api/gateway/usage/users/{DEFAULT_USER_ID}")
    r_usr.raise_for_status()
    checks["usage_endpoints"] = {
        "summary_status": r_sum.status_code,
        "user_status": r_usr.status_code,
    }

    return checks


async def call_gateway_chat_json(
    client: httpx.AsyncClient,
    base_url: str,
    *,
    user_id: str,
    agent_id: str,
    message: str,
    conversation_id: str | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Calls `POST /api/gateway/chat` with retry on transient errors."""
    payload: dict[str, Any] = {
        "user_id": user_id,
        "agent_id": agent_id,
        "message": message,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        try:
            resp = await client.post(
                f"{base_url}/api/gateway/chat",
                json=payload,
                timeout=600.0,
            )
            if resp.status_code >= 500 and attempt < max_attempts:
                print(
                    f"  [retry] POST /api/gateway/chat ({agent_id}) HTTP {resp.status_code}, retrying...",
                    flush=True,
                )
                await asyncio.sleep(3.0)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "latency_ms" not in data or not data["latency_ms"]:
                data["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
            return data
        except Exception as exc:
            last_err = exc
            if attempt < max_attempts:
                print(
                    f"  [retry] POST /api/gateway/chat ({agent_id}) error {exc}, retrying...",
                    flush=True,
                )
                await asyncio.sleep(3.0)
    raise RuntimeError(f"POST /api/gateway/chat failed for {agent_id}: {last_err}")


async def call_gateway_chat_stream(
    client: httpx.AsyncClient,
    base_url: str,
    *,
    user_id: str,
    agent_id: str,
    message: str,
    conversation_id: str | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Calls `POST /api/gateway/chat/stream` (SSE), logs live progress, and returns full turn data."""
    payload: dict[str, Any] = {
        "user_id": user_id,
        "agent_id": agent_id,
        "message": message,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        event_counts: dict[str, int] = {}
        dag_steps: list[dict[str, Any]] = []
        tool_calls_seen: list[str] = []
        media_items: list[dict[str, Any]] = []
        turn_complete_payload: dict[str, Any] | None = None
        usage_payload: dict[str, Any] | None = None
        stream_error: str | None = None
        text_chunks: list[str] = []
        turn_start_info: dict[str, Any] = {}

        try:
            async with client.stream(
                "POST",
                f"{base_url}/api/gateway/chat/stream",
                json=payload,
                timeout=600.0,
            ) as resp:
                resp.raise_for_status()
                current_event = "message"
                data_lines: list[str] = []

                async for raw_line in resp.aiter_lines():
                    line = raw_line.rstrip("\r")
                    if line.startswith("event:"):
                        current_event = line[len("event:") :].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[len("data:") :].strip())
                    elif line == "":
                        if not data_lines:
                            current_event = "message"
                            continue
                        raw_data = "\n".join(data_lines)
                        data_lines.clear()
                        try:
                            ev = json.loads(raw_data)
                        except json.JSONDecodeError:
                            current_event = "message"
                            continue

                        ev_type = str(ev.get("type") or current_event or "message")
                        event_counts[ev_type] = event_counts.get(ev_type, 0) + 1

                        if ev_type == "turn_start":
                            turn_start_info = ev
                        elif ev_type == "tool_call":
                            t_name = str(ev.get("tool_name") or ev.get("name") or "")
                            if t_name:
                                tool_calls_seen.append(t_name)
                                sub_tag = " (subagent)" if ev.get("is_subagent") else ""
                                print(
                                    f"    -> [SSE tool_call] {t_name}{sub_tag}",
                                    flush=True,
                                )
                        elif ev_type == "dag_step":
                            dag_steps.append(ev)
                            print(
                                f"    -> [SSE dag_step] {ev.get('node_id')}: {ev.get('status')}",
                                flush=True,
                            )
                        elif ev_type == "media":
                            media_items.append(ev)
                            print(
                                f"    -> [SSE media] {ev.get('kind')}: {ev.get('url')}",
                                flush=True,
                            )
                        elif ev_type == "text_delta":
                            if ev.get("text") and not ev.get("is_subagent"):
                                text_chunks.append(str(ev["text"]))
                        elif ev_type == "usage":
                            usage_payload = ev
                        elif ev_type == "turn_complete":
                            turn_complete_payload = ev
                        elif ev_type == "error":
                            stream_error = str(ev.get("error") or "Unknown SSE error")

                        current_event = "message"

            if stream_error:
                raise RuntimeError(f"SSE error event: {stream_error}")

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            result = dict(turn_complete_payload or {})
            if not result and usage_payload:
                result = {
                    "status": "ok",
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "conversation_id": turn_start_info.get("conversation_id")
                    or conversation_id,
                    "antigravity_conversation_id": turn_start_info.get(
                        "antigravity_conversation_id"
                    ),
                    "turn_number": usage_payload.get("turn_number", 1),
                    "response_text": "".join(text_chunks),
                    "request_tokens": usage_payload.get("request_tokens", {}),
                    "conversation_tokens": usage_payload.get(
                        "conversation_tokens", {}
                    ),
                    "user_tokens": usage_payload.get("user_tokens", {}),
                    "latency_ms": usage_payload.get("latency_ms", elapsed_ms),
                }
            result.setdefault("latency_ms", elapsed_ms)
            result["sse_event_counts"] = event_counts
            if not result.get("media") and media_items:
                result["media"] = media_items
            if dag_steps:
                result["sse_dag_steps"] = dag_steps
            if tool_calls_seen and not result.get("tool_calls"):
                result["tool_calls"] = [{"tool_name": n} for n in tool_calls_seen]
            else:
                result["sse_tool_names"] = tool_calls_seen
            return result

        except Exception as exc:
            last_err = exc
            if attempt < max_attempts:
                print(
                    f"  [retry] POST /api/gateway/chat/stream ({agent_id}) error {exc}, retrying...",
                    flush=True,
                )
                await asyncio.sleep(3.0)

    raise RuntimeError(
        f"POST /api/gateway/chat/stream failed for {agent_id}: {last_err}"
    )


def extract_tool_names_from_turn(turn_data: dict[str, Any]) -> list[str]:
    """Extracts ordered tool names invoked during a Gateway turn."""
    names: list[str] = []
    for tc in turn_data.get("tool_calls") or []:
        if isinstance(tc, str):
            names.append(tc)
        elif isinstance(tc, dict):
            n = tc.get("tool_name") or tc.get("name")
            if n:
                names.append(str(n))
    if not names:
        for ev in turn_data.get("events") or []:
            if isinstance(ev, dict) and ev.get("type") == "tool_call":
                n = ev.get("tool_name") or ev.get("name")
                if n:
                    names.append(str(n))
    for n in turn_data.get("sse_tool_names") or []:
        if n not in names:
            names.append(n)
    return names


async def execute_scenario(
    client: httpx.AsyncClient,
    base_url: str,
    spec: ScenarioSpec,
    user_id: str,
) -> dict[str, Any]:
    """Runs Step A (Creation via Antigravity) + Step B (Run via Custom Agent) + optional Step C."""
    print(
        f"\n======================================================================\n"
        f"SCENARIO #{spec.index}: {spec.display_name} ({spec.agent_id})\n"
        f"Topology: {spec.dag_pattern_title} [{spec.dag_topology}]\n"
        f"======================================================================",
        flush=True,
    )

    # ------------------------------------------------------------------
    # STEP A: Agent Creation via `agent_id="antigravity"`
    # ------------------------------------------------------------------
    print(f"  [Step A] Creating `{spec.agent_id}` via Antigravity Builder Agent...", flush=True)
    creation_prompt = spec.build_creation_prompt()
    creation_resp = await call_gateway_chat_json(
        client,
        base_url,
        user_id=user_id,
        agent_id="antigravity",
        message=creation_prompt,
    )
    creation_tokens = normalize_tokens(creation_resp.get("request_tokens"))
    creation_tools = extract_tool_names_from_turn(creation_resp)

    md_path = AGENTS_DIR / f"{spec.agent_id}.md"
    reg_path = REGISTRY_DIR / f"{spec.agent_id}.json"
    dynamic_tool_path = (
        DYNAMIC_TOOLS_DIR / f"{spec.dynamic_tool_spec['tool_name']}.py"
        if spec.dynamic_tool_spec
        else None
    )

    # Verify catalog registration via GET /api/gateway/agents
    r_agents = await client.get(f"{base_url}/api/gateway/agents")
    r_agents.raise_for_status()
    catalog_list = r_agents.json().get("agents", [])
    in_catalog = any(a.get("agent_id") == spec.agent_id for a in catalog_list)

    print(
        f"  [Step A Done] latency={creation_resp.get('latency_ms', 0):.0f}ms | "
        f"tokens={creation_tokens['total_tokens']:,} "
        f"(prompt={creation_tokens['prompt_tokens']:,}, cached={creation_tokens['cached_tokens']:,}, "
        f"thoughts={creation_tokens['thoughts_tokens']:,}, candidates={creation_tokens['candidates_tokens']:,}) | "
        f"tools={creation_tools} | md={md_path.exists()} | json={reg_path.exists()} | catalog={in_catalog}",
        flush=True,
    )

    if not md_path.exists() or not reg_path.exists():
        raise RuntimeError(
            f"Agent artifacts missing after Step A for {spec.agent_id}: "
            f"md={md_path.exists()}, json={reg_path.exists()}. Response: {creation_resp.get('response_text', '')[:400]}"
        )
    if dynamic_tool_path and not dynamic_tool_path.exists():
        raise RuntimeError(
            f"Dynamic tool file {dynamic_tool_path} was not created during Step A!"
        )

    # ------------------------------------------------------------------
    # STEP B: Custom Agent Fun Mission Execution via SSE `/api/gateway/chat/stream`
    # ------------------------------------------------------------------
    print(f"  [Step B] Running Fun Mission on `{spec.agent_id}` via SSE stream...", flush=True)
    run_resp = await call_gateway_chat_stream(
        client,
        base_url,
        user_id=user_id,
        agent_id=spec.agent_id,
        message=spec.mission_prompt,
    )
    run_tokens = normalize_tokens(run_resp.get("request_tokens"))
    run_tools = extract_tool_names_from_turn(run_resp)

    # Verify media serving on first media item if generated
    verified_media: list[dict[str, Any]] = []
    for m in run_resp.get("media") or []:
        m_url = m.get("url")
        http_ok = False
        if m_url and m_url.startswith("/"):
            rm = await client.get(f"{base_url}{m_url}")
            http_ok = rm.status_code == 200 and len(rm.content) > 0
        verified_media.append(
            {
                "kind": m.get("kind"),
                "mime_type": m.get("mime_type"),
                "filename": m.get("filename"),
                "url": m_url,
                "size_bytes": m.get("size_bytes"),
                "served_200_ok": http_ok,
            }
        )

    sandbox_checks = {
        fname: (SANDBOX_DIR / fname).exists() for fname in spec.expected_sandbox_files
    }

    print(
        f"  [Step B Done] latency={run_resp.get('latency_ms', 0):.0f}ms | "
        f"tokens={run_tokens['total_tokens']:,} "
        f"(prompt={run_tokens['prompt_tokens']:,}, cached={run_tokens['cached_tokens']:,}, "
        f"thoughts={run_tokens['thoughts_tokens']:,}, candidates={run_tokens['candidates_tokens']:,}, "
        f"subagent={run_tokens['subagent_tokens']:,}) | "
        f"tools={run_tools} | media={len(verified_media)} | sandbox={sandbox_checks}",
        flush=True,
    )

    # ------------------------------------------------------------------
    # STEP C: Optional Multi-Turn Follow-up on SAME conversation_id
    # ------------------------------------------------------------------
    multi_turn_result: dict[str, Any] | None = None
    if spec.multi_turn_followup_prompt:
        conv_id = str(run_resp.get("conversation_id"))
        print(
            f"  [Step C] Verifying Multi-Turn Continuity on conversation_id={conv_id}...",
            flush=True,
        )
        t2_resp = await call_gateway_chat_json(
            client,
            base_url,
            user_id=user_id,
            agent_id=spec.agent_id,
            conversation_id=conv_id,
            message=spec.multi_turn_followup_prompt,
        )
        t2_req_tokens = normalize_tokens(t2_resp.get("request_tokens"))
        t2_conv_tokens = normalize_tokens(t2_resp.get("conversation_tokens"))

        r_conv = await client.get(f"{base_url}/api/gateway/conversations/{conv_id}")
        r_conv.raise_for_status()
        conv_ledger = r_conv.json()
        turns_recorded = len(conv_ledger.get("turns", []))

        multi_turn_result = {
            "conversation_id": conv_id,
            "antigravity_conversation_id": t2_resp.get("antigravity_conversation_id"),
            "same_antigravity_trajectory": (
                t2_resp.get("antigravity_conversation_id")
                == run_resp.get("antigravity_conversation_id")
            ),
            "turn_number": t2_resp.get("turn_number"),
            "turns_recorded_in_gateway_db": turns_recorded,
            "turn_1_request_tokens": run_tokens,
            "turn_2_request_tokens": t2_req_tokens,
            "turn_2_cumulative_conversation_tokens": t2_conv_tokens,
            "cumulative_exceeds_turn_1": (
                t2_conv_tokens["total_tokens"] > run_tokens["total_tokens"]
            ),
            "latency_ms": round(float(t2_resp.get("latency_ms", 0.0)), 2),
            "tool_calls": extract_tool_names_from_turn(t2_resp),
            "response_preview": (t2_resp.get("response_text") or "")[:400],
        }
        print(
            f"  [Step C Done] turn_number={t2_resp.get('turn_number')} | "
            f"turn2_req={t2_req_tokens['total_tokens']:,} | "
            f"cumulative_conv={t2_conv_tokens['total_tokens']:,} (turn1={run_tokens['total_tokens']:,}) | "
            f"same_trajectory={multi_turn_result['same_antigravity_trajectory']}",
            flush=True,
        )

    combined_tokens = sum_token_dicts([creation_tokens, run_tokens])

    return {
        "index": spec.index,
        "agent_id": spec.agent_id,
        "display_name": spec.display_name,
        "dag_topology": spec.dag_topology,
        "dag_pattern_title": spec.dag_pattern_title,
        "enable_subagents": spec.enable_subagents,
        "dynamic_tool_created": (
            spec.dynamic_tool_spec["tool_name"] if spec.dynamic_tool_spec else None
        ),
        "artifacts": {
            "agent_md_path": str(md_path),
            "agent_md_exists": md_path.exists(),
            "agent_md_bytes": md_path.stat().st_size if md_path.exists() else 0,
            "agent_json_path": str(reg_path),
            "agent_json_exists": reg_path.exists(),
            "dynamic_tool_path": str(dynamic_tool_path) if dynamic_tool_path else None,
            "dynamic_tool_exists": (
                dynamic_tool_path.exists() if dynamic_tool_path else None
            ),
            "registered_in_gateway_catalog": in_catalog,
            "sandbox_files": sandbox_checks,
            "media": verified_media,
        },
        "creation": {
            "agent_id": "antigravity",
            "conversation_id": creation_resp.get("conversation_id"),
            "antigravity_conversation_id": creation_resp.get(
                "antigravity_conversation_id"
            ),
            "latency_ms": round(float(creation_resp.get("latency_ms", 0.0)), 2),
            "tokens": creation_tokens,
            "tool_calls": creation_tools,
            "response_preview": (creation_resp.get("response_text") or "")[:400],
        },
        "execution": {
            "agent_id": spec.agent_id,
            "conversation_id": run_resp.get("conversation_id"),
            "antigravity_conversation_id": run_resp.get("antigravity_conversation_id"),
            "latency_ms": round(float(run_resp.get("latency_ms", 0.0)), 2),
            "tokens": run_tokens,
            "tool_calls": run_tools,
            "sse_event_counts": run_resp.get("sse_event_counts", {}),
            "response_preview": (run_resp.get("response_text") or "")[:500],
        },
        "combined_scenario_tokens": combined_tokens,
        "multi_turn_continuity": multi_turn_result,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Renders `TEN_AGENTS_TOKEN_REPORT.md` from the structured benchmark report."""
    scenarios = report["scenarios"]
    totals = report["totals"]
    c_tot = totals["creation_total"]
    r_tot = totals["execution_total"]
    m_tot = totals["multi_turn_followup_total"]
    g_tot = totals["grand_total_all_turns"]

    lines: list[str] = [
        "# Antigravity 10-DAG Custom Agents — End-to-End Token & Verification Report",
        "",
        f"- **Generated At (UTC)**: `{report['generated_at']}`",
        f"- **GCP Project**: `{report['environment']['project']}`",
        f"- **Service Account**: `{report['environment']['service_account_email']}`",
        "- **Model**: `gemini-3.7-flash` (Vertex AI `global`) + `veo-3.1-lite-generate-001` (Veo 3.1 Video)",
        f"- **Gateway User ID**: `{report['user_id']}`",
        f"- **Scenarios Verified**: `{len(scenarios)} / 10`",
        "",
        "---",
        "",
        "## 1. Executive Token Usage Summary",
        "",
        "| Phase | Turns | Prompt Tokens | Cached Tokens | Thoughts Tokens | Candidates Tokens | Subagent Tokens | Total Tokens | Total Latency (s) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| **Step A: Agent Creation (`antigravity`)** | {len(scenarios)} | "
            f"{c_tot['prompt_tokens']:,} | {c_tot['cached_tokens']:,} | "
            f"{c_tot['thoughts_tokens']:,} | {c_tot['candidates_tokens']:,} | "
            f"{c_tot['subagent_tokens']:,} | **{c_tot['total_tokens']:,}** | "
            f"{totals['creation_latency_ms'] / 1000.0:.1f}s |"
        ),
        (
            f"| **Step B: Custom Agent Missions (`1..10`)** | {len(scenarios)} | "
            f"{r_tot['prompt_tokens']:,} | {r_tot['cached_tokens']:,} | "
            f"{r_tot['thoughts_tokens']:,} | {r_tot['candidates_tokens']:,} | "
            f"{r_tot['subagent_tokens']:,} | **{r_tot['total_tokens']:,}** | "
            f"{totals['execution_latency_ms'] / 1000.0:.1f}s |"
        ),
        (
            f"| **Step C: Multi-Turn Continuity Follow-up** | {totals['multi_turn_count']} | "
            f"{m_tot['prompt_tokens']:,} | {m_tot['cached_tokens']:,} | "
            f"{m_tot['thoughts_tokens']:,} | {m_tot['candidates_tokens']:,} | "
            f"{m_tot['subagent_tokens']:,} | **{m_tot['total_tokens']:,}** | "
            f"{totals['multi_turn_latency_ms'] / 1000.0:.1f}s |"
        ),
        (
            f"| **Grand Total (All Gateway Requests)** | **{2 * len(scenarios) + totals['multi_turn_count']}** | "
            f"**{g_tot['prompt_tokens']:,}** | **{g_tot['cached_tokens']:,}** | "
            f"**{g_tot['thoughts_tokens']:,}** | **{g_tot['candidates_tokens']:,}** | "
            f"**{g_tot['subagent_tokens']:,}** | **{g_tot['total_tokens']:,}** | "
            f"**{totals['total_latency_ms'] / 1000.0:.1f}s** |"
        ),
        "",
        "---",
        "",
        "## 2. Step A — Custom Agent Creation Token Breakdown (`agent_id=\"antigravity\"`)",
        "",
        "| # | Created Agent ID | DAG Topology | Prompt | Cached | Thoughts | Candidates | Subagent | Total Creation Tokens | Latency (s) | Builder Tools Invoked |",
        "| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
    ]

    for s in scenarios:
        ct = s["creation"]["tokens"]
        c_tools = ", ".join(f"`{t}`" for t in s["creation"]["tool_calls"]) or "—"
        lines.append(
            f"| {s['index']} | `{s['agent_id']}` | `{s['dag_topology']}` | "
            f"{ct['prompt_tokens']:,} | {ct['cached_tokens']:,} | "
            f"{ct['thoughts_tokens']:,} | {ct['candidates_tokens']:,} | "
            f"{ct['subagent_tokens']:,} | **{ct['total_tokens']:,}** | "
            f"{s['creation']['latency_ms'] / 1000.0:.1f}s | {c_tools} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Step B — Custom Agent Fun Mission Execution Token Breakdown (SSE `/api/gateway/chat/stream`)",
            "",
            "| # | Custom Agent ID | DAG Pattern | Prompt | Cached | Thoughts | Candidates | Subagent | Total Run Tokens | Latency (s) | Media & Sandbox Deliverables |",
            "| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )

    for s in scenarios:
        rt = s["execution"]["tokens"]
        media_count = len(s["artifacts"]["media"])
        sb_ok = [k for k, v in s["artifacts"]["sandbox_files"].items() if v]
        deliv_parts = []
        if sb_ok:
            deliv_parts.extend(f"`{f}`" for f in sb_ok)
        if media_count:
            deliv_parts.append(f"{media_count} media served (`200 OK`)")
        deliv_str = ", ".join(deliv_parts) or "Verified"
        lines.append(
            f"| {s['index']} | `{s['agent_id']}` | {s['dag_pattern_title']} | "
            f"{rt['prompt_tokens']:,} | {rt['cached_tokens']:,} | "
            f"{rt['thoughts_tokens']:,} | {rt['candidates_tokens']:,} | "
            f"{rt['subagent_tokens']:,} | **{rt['total_tokens']:,}** | "
            f"{s['execution']['latency_ms'] / 1000.0:.1f}s | {deliv_str} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Combined End-to-End Token Summary (Creation + Execution per Scenario)",
            "",
            "| # | Agent ID | Creation Tokens | Run Tokens | Subagent Tokens (Run) | Combined Tokens | `.md` & `.json` Verified |",
            "| ---: | :--- | ---: | ---: | ---: | ---: | :---: |",
        ]
    )

    for s in scenarios:
        ct_tot = s["creation"]["tokens"]["total_tokens"]
        rt_tot = s["execution"]["tokens"]["total_tokens"]
        sub_tot = s["execution"]["tokens"]["subagent_tokens"]
        comb_tot = s["combined_scenario_tokens"]["total_tokens"]
        ok_badge = (
            "YES"
            if (
                s["artifacts"]["agent_md_exists"]
                and s["artifacts"]["agent_json_exists"]
            )
            else "NO"
        )
        lines.append(
            f"| {s['index']} | `{s['agent_id']}` | {ct_tot:,} | {rt_tot:,} | {sub_tot:,} | **{comb_tot:,}** | {ok_badge} |"
        )

    # Dynamic tool synthesis + multi-turn proof sections
    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Special Capabilities & Stateful Gateway Proofs",
            "",
            "### 5.1 End-to-End Dynamic Tool Synthesis (`create_custom_tool`)",
        ]
    )
    dyn_scenarios = [s for s in scenarios if s.get("dynamic_tool_created")]
    for ds in dyn_scenarios:
        lines.extend(
            [
                f"- **Scenario #{ds['index']} (`{ds['agent_id']}`)**: Antigravity dynamically synthesized "
                f"`{ds['dynamic_tool_created']}` via `create_custom_tool` -> persisted to "
                f"`{ds['artifacts']['dynamic_tool_path']}` (`exists={ds['artifacts']['dynamic_tool_exists']}`).",
                f"- Creation Tool Calls: `{ds['creation']['tool_calls']}`",
                f"- Execution Tool Calls (confirming live invocation of synthesized tool): `{ds['execution']['tool_calls']}`",
            ]
        )

    mt_scenarios = [s for s in scenarios if s.get("multi_turn_continuity")]
    if mt_scenarios:
        mt = mt_scenarios[0]["multi_turn_continuity"]
        lines.extend(
            [
                "",
                "### 5.2 Multi-Turn Stateful Conversation & Cumulative Token Continuity",
                f"- **Agent**: `{mt_scenarios[0]['agent_id']}` | **Gateway `conversation_id`**: `{mt['conversation_id']}`",
                f"- **Deterministic `antigravity_conversation_id`**: `{mt['antigravity_conversation_id']}` (`same_trajectory={mt['same_antigravity_trajectory']}`)",
                f"- **Turn 1 Request Tokens**: `{mt['turn_1_request_tokens']['total_tokens']:,}`",
                f"- **Turn 2 Request Tokens**: `{mt['turn_2_request_tokens']['total_tokens']:,}` (`turn_number={mt['turn_number']}`, `turns_in_db={mt['turns_recorded_in_gateway_db']}`)",
                f"- **Turn 2 Cumulative Conversation Tokens**: `{mt['turn_2_cumulative_conversation_tokens']['total_tokens']:,}` (`cumulative_exceeds_turn_1={mt['cumulative_exceeds_turn_1']}`)",
            ]
        )

    gw_summary = report.get("gateway_ledger_summary", {})
    gw_user = report.get("gateway_user_ledger", {})
    lines.extend(
        [
            "",
            "### 5.3 Pre-Flight & Single API Gateway Ledger Audit",
            f"- **Health Endpoint (`/api/gateway/health`)**: HTTP `{report['preflight']['health']['status_code']}`",
            f"- **Live Studio UI (`/ui/index.html` & `/studio`)**: HTTP `{report['preflight']['ui']['ui_index_status']}` (`{report['preflight']['ui']['ui_index_bytes']:,}` bytes)",
            f"- **Per-User Ledger (`/api/gateway/usage/users/{report['user_id']}`)**: "
            f"`conversation_count={gw_user.get('conversation_count')}`, `turn_count={gw_user.get('turn_count')}`, "
            f"`total_tokens={(gw_user.get('tokens') or {}).get('total_tokens', gw_user.get('total_tokens', 0)):,}`",
            f"- **Global Summary (`/api/gateway/usage/summary`)**: "
            f"`agents_tracked={len(gw_summary.get('by_agent', []))}`, "
            f"`conversations_tracked={len(gw_summary.get('by_conversation', []))}`",
            "",
        ]
    )

    return "\n".join(lines)


async def async_main(args: argparse.Namespace) -> int:
    auth_info = ensure_gcp_auth()
    print(f"[auth] Verified GCP Auth: {auth_info}", flush=True)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

    selected_indices = (
        {int(x.strip()) for x in args.scenarios.split(",") if x.strip()}
        if args.scenarios
        else {s.index for s in SCENARIOS}
    )
    selected_specs = [s for s in SCENARIOS if s.index in selected_indices]

    checkpoint_path = Path("/tmp/antigravity_harness/benchmark_checkpoint.json")
    prior_results: dict[int, dict[str, Any]] = {}
    if args.resume and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for item in saved.get("scenarios", []):
            prior_results[int(item["index"])] = item
        print(
            f"[resume] Loaded {len(prior_results)} completed scenarios from checkpoint.",
            flush=True,
        )

    async with ManagedGatewayServer(
        gateway_url=args.gateway_url,
        port=args.port,
        fresh_db=args.fresh_db and not args.resume,
    ) as base_url:
        async with httpx.AsyncClient(timeout=600.0) as client:
            preflight = await run_preflight_checks(client, base_url)
            print(f"[preflight] All Gateway & UI checks passed: {preflight}", flush=True)

            results_by_index: dict[int, dict[str, Any]] = dict(prior_results)
            for spec in selected_specs:
                if args.resume and spec.index in results_by_index:
                    print(
                        f"[resume] Skipping already-completed Scenario #{spec.index} ({spec.agent_id})",
                        flush=True,
                    )
                    continue
                res = await execute_scenario(
                    client, base_url, spec, user_id=args.user_id
                )
                results_by_index[spec.index] = res
                checkpoint_path.write_text(
                    json.dumps(
                        {
                            "updated_at": datetime.datetime.now(
                                datetime.UTC
                            ).isoformat(),
                            "scenarios": [
                                results_by_index[k]
                                for k in sorted(results_by_index.keys())
                            ],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            ordered_scenarios = [
                results_by_index[k] for k in sorted(results_by_index.keys())
            ]

            r_user = await client.get(
                f"{base_url}/api/gateway/usage/users/{args.user_id}"
            )
            r_user.raise_for_status()
            user_ledger = r_user.json()

            r_summary = await client.get(f"{base_url}/api/gateway/usage/summary")
            r_summary.raise_for_status()
            summary_ledger = r_summary.json()

    creation_total = sum_token_dicts(
        [s["creation"]["tokens"] for s in ordered_scenarios]
    )
    execution_total = sum_token_dicts(
        [s["execution"]["tokens"] for s in ordered_scenarios]
    )
    mt_items = [
        s["multi_turn_continuity"]["turn_2_request_tokens"]
        for s in ordered_scenarios
        if s.get("multi_turn_continuity")
    ]
    multi_turn_total = sum_token_dicts(mt_items)
    grand_total = sum_token_dicts([creation_total, execution_total, multi_turn_total])

    creation_lat = sum(float(s["creation"]["latency_ms"]) for s in ordered_scenarios)
    execution_lat = sum(float(s["execution"]["latency_ms"]) for s in ordered_scenarios)
    mt_lat = sum(
        float(s["multi_turn_continuity"]["latency_ms"])
        for s in ordered_scenarios
        if s.get("multi_turn_continuity")
    )

    report_data: dict[str, Any] = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "user_id": args.user_id,
        "environment": auth_info,
        "preflight": preflight,
        "totals": {
            "scenarios_count": len(ordered_scenarios),
            "multi_turn_count": len(mt_items),
            "creation_total": creation_total,
            "execution_total": execution_total,
            "multi_turn_followup_total": multi_turn_total,
            "grand_total_all_turns": grand_total,
            "creation_latency_ms": round(creation_lat, 2),
            "execution_latency_ms": round(execution_lat, 2),
            "multi_turn_latency_ms": round(mt_lat, 2),
            "total_latency_ms": round(creation_lat + execution_lat + mt_lat, 2),
        },
        "scenarios": ordered_scenarios,
        "gateway_user_ledger": user_ledger,
        "gateway_ledger_summary": summary_ledger,
    }

    DEFAULT_JSON_REPORT.write_text(
        json.dumps(report_data, indent=2), encoding="utf-8"
    )
    md_text = render_markdown_report(report_data)
    DEFAULT_MD_REPORT.write_text(md_text, encoding="utf-8")

    print(
        f"\n[done] Wrote JSON report -> {DEFAULT_JSON_REPORT}\n"
        f"[done] Wrote Markdown report -> {DEFAULT_MD_REPORT}\n"
        f"[done] Grand Total Tokens across all turns: {grand_total['total_tokens']:,}",
        flush=True,
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all 10 Antigravity Custom DAG Agents end-to-end through the Single API Gateway."
    )
    parser.add_argument(
        "--gateway-url",
        default=None,
        help="Optional existing Gateway base URL (e.g. http://127.0.0.1:8000). Spawns local uvicorn if omitted.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Optional port when auto-launching uvicorn.",
    )
    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help="User ID sent to the Single API Gateway (default: cbribiescas).",
    )
    parser.add_argument(
        "--scenarios",
        default=None,
        help="Comma-separated scenario indices 1..10 to run (default: all 10).",
    )
    parser.add_argument(
        "--fresh-db",
        action="store_true",
        default=True,
        help="Start from a clean Gateway SQLite ledger before a full run (default: True).",
    )
    parser.add_argument(
        "--no-fresh-db",
        action="store_false",
        dest="fresh_db",
        help="Preserve existing Gateway SQLite ledger rows.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume from reports/.benchmark_checkpoint.json if interrupted.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main(parse_args())))
