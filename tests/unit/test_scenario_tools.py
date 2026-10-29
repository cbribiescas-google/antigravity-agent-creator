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
"""Unit tests for all 10-DAG Scenario Custom Tools (`app.scenario_tools`)."""

import inspect
import json
import os
import typing
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

from google.antigravity import LocalAgentConfig
from google.antigravity.tools.tool_runner import ToolRunner

from app.scenario_tools import SCENARIO_TOOLS, get_scenario_tool_metadata
from app.scenario_tools.arcade_tools import validate_html5_game
from app.scenario_tools.dnd_tools import manage_hero_state, roll_crypto_d20
from app.scenario_tools.foodie_tools import (
    export_ics_calendar,
    solve_crawl_constraints,
)
from app.scenario_tools.media_tools import (
    generate_video_clip,
    log_vision_critique,
)
from app.scenario_tools.mythbuster_tools import verify_claim_math
from app.scenario_tools.orchestration_tools import (
    emit_dag_step,
    record_pruned_branch,
)
from app.scenario_tools.tournament_tools import run_bot_tournament

EXPECTED_TOOL_NAMES = {
    "generate_video_clip",
    "log_vision_critique",
    "validate_html5_game",
    "run_bot_tournament",
    "verify_claim_math",
    "solve_crawl_constraints",
    "export_ics_calendar",
    "roll_crypto_d20",
    "manage_hero_state",
    "emit_dag_step",
    "record_pruned_branch",
}


def test_scenario_tools_registry_and_antigravity_sdk_compatibility() -> None:
    """Verify all 11 scenario tools export clean signatures, docstrings, metadata, and register with Antigravity."""
    assert set(SCENARIO_TOOLS.keys()) == EXPECTED_TOOL_NAMES

    for name, fn in SCENARIO_TOOLS.items():
        assert callable(fn)
        assert fn.__name__ == name
        doc = inspect.getdoc(fn)
        assert doc and len(doc) >= 20, f"Tool {name} missing descriptive docstring"
        hints = typing.get_type_hints(fn)
        assert "return" in hints, f"Tool {name} missing return type annotation"

    metadata = get_scenario_tool_metadata()
    assert len(metadata) == len(EXPECTED_TOOL_NAMES)
    by_name = {item["name"]: item for item in metadata}
    assert set(by_name.keys()) == EXPECTED_TOOL_NAMES
    for entry in by_name.values():
        assert entry["source"] == "scenario"
        assert entry["description"]
        assert entry["module"].startswith("app.scenario_tools.")

    # Verify compatibility with LocalAgentConfig & ToolRunner
    cfg = LocalAgentConfig(tools=list(SCENARIO_TOOLS.values()))
    assert len(cfg.tools) == len(EXPECTED_TOOL_NAMES)
    runner = ToolRunner(list(SCENARIO_TOOLS.values()))
    assert set(runner.tool_names) == EXPECTED_TOOL_NAMES


def test_media_tools_generate_video_clip_with_fallback(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify generate_video_clip falls back cleanly across Veo 3.1 models and saves MP4."""
    videos_dir = tmp_path / "videos"
    monkeypatch.setenv("ANTIGRAVITY_VIDEOS_DIR", str(videos_dir))

    mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom_trailer"
    attempted_models: list[str] = []

    class FakeModels:
        def generate_videos(self, *, model: str, source, config):
            attempted_models.append(model)
            if model == "veo-3.1-lite-generate-001":
                raise RuntimeError("Simulated lite capacity spike")
            return SimpleNamespace(
                done=True,
                error=None,
                result=SimpleNamespace(
                    generated_videos=[
                        SimpleNamespace(
                            video=SimpleNamespace(video_bytes=mp4_bytes)
                        )
                    ]
                ),
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.models = FakeModels()
            self.operations = SimpleNamespace(get=lambda op: op)

    with patch("app.scenario_tools.media_tools.genai.Client", FakeClient):
        res = generate_video_clip(
            prompt="Dramatic slow-motion mall parking lot showdown in rain",
            clip_name="Mall Parking Climax!",
            aspect_ratio="16:9",
            duration_seconds=4,
        )

    assert attempted_models[0] == "veo-3.1-lite-generate-001"
    assert res["model"] == "veo-3.1-fast-generate-001"
    assert res["mime_type"] == "video/mp4"
    assert os.path.isfile(res["output_path"])
    with open(res["output_path"], "rb") as f:
        assert f.read() == mp4_bytes


def test_media_tools_log_vision_critique(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify log_vision_critique scores draft images and persists critique history."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    draft_img = sandbox / "draft_v1.png"
    draft_img.write_bytes(b"\x89PNG\r\n\x1a\ndraft_comic")

    res_v1 = log_vision_critique(
        draft_image_path="draft_v1.png",
        composition_score=6,
        lighting_score=7,
        flaws_found="Cluttered speech bubbles and flat lighting in panel 2",
        upgraded_prompt="Clean 3-panel comic with dramatic rim lighting and crisp lettering",
    )
    assert res_v1["file_exists"] is True
    assert res_v1["needs_revision"] is True
    assert res_v1["average_score"] == 6.5

    res_v2 = log_vision_critique(
        draft_image_path=str(draft_img),
        composition_score=9,
        lighting_score=9,
        flaws_found="None — publication ready",
        upgraded_prompt="Final approved prompt",
    )
    assert res_v2["needs_revision"] is False
    assert os.path.isfile(res_v2["critique_log_path"])
    saved = json.loads(open(res_v2["critique_log_path"], encoding="utf-8").read())
    assert len(saved) == 2


def test_arcade_tools_validate_html5_game(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify validate_html5_game catches broken HTML/JS and passes valid HTML5 Canvas games."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    valid_game = sandbox / "kopi_dodge.html"
    valid_game.write_text(
        """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Kopi Dodge</title></head>
<body>
  <canvas id="gameCanvas" width="640" height="480"></canvas>
  <script>
    const canvas = document.getElementById("gameCanvas");
    const ctx = canvas.getContext("2d");
    let playerX = 300;
    window.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") playerX -= 10;
      if (e.key === "ArrowRight") playerX += 10;
    });
    function loop() {
      ctx.clearRect(0, 0, 640, 480);
      ctx.fillRect(playerX, 440, 40, 20);
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )
    ok = validate_html5_game("kopi_dodge.html")
    assert ok["passed"] is True
    assert ok["errors"] == []
    assert ok["byte_size"] > 100

    broken_game = sandbox / "broken_game.html"
    broken_game.write_text(
        """<html><body><div>No canvas here</div>
<script>function broken( { const x = 1; </script>
</body></html>""",
        encoding="utf-8",
    )
    bad = validate_html5_game(str(broken_game))
    assert bad["passed"] is False
    assert len(bad["errors"]) >= 2

    missing = validate_html5_game("does_not_exist.html")
    assert missing["passed"] is False
    assert missing["byte_size"] == 0


def test_tournament_tools_run_bot_tournament(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify deterministic Prisoner's Dilemma round-robin tournament across 3 bots."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    (sandbox / "tit_for_tat.py").write_text(
        """def decide(my_history: list[str], opponent_history: list[str]) -> str:
    if not opponent_history:
        return "C"
    return opponent_history[-1]
""",
        encoding="utf-8",
    )
    (sandbox / "always_defect.py").write_text(
        """def decide(my_history: list[str], opponent_history: list[str]) -> str:
    return "D"
""",
        encoding="utf-8",
    )
    (sandbox / "always_cooperate.py").write_text(
        """def decide(my_history: list[str], opponent_history: list[str]) -> str:
    return "C"
""",
        encoding="utf-8",
    )

    run1 = run_bot_tournament(
        "tit_for_tat.py", "always_defect.py", "always_cooperate.py", rounds=2000
    )
    run2 = run_bot_tournament(
        "tit_for_tat.py", "always_defect.py", "always_cooperate.py", rounds=2000
    )

    # Deterministic check
    assert run1["leaderboard"] == run2["leaderboard"]
    assert len(run1["leaderboard"]) == 3
    assert "match_matrix" in run1
    # Check exact math:
    # AlwaysDefect vs AlwaysCooperate (2000 rounds): D gets 5*2000=10000, C gets 0
    # AlwaysDefect vs TitForTat (2000 rounds): round 1 D vs C -> (5, 0), rounds 2..2000 D vs D -> (1999, 1999) => D=2004, TFT=1999
    # TitForTat vs AlwaysCooperate (2000 rounds): C vs C -> (6000, 6000)
    # Totals: AlwaysDefect = 12004, TitForTat = 7999, AlwaysCooperate = 6000
    scores = {row["bot_name"]: row["total_score"] for row in run1["leaderboard"]}
    assert sorted(scores.values(), reverse=True) == [12004, 7999, 6000]


def test_mythbuster_tools_verify_claim_math(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify isolated math verification routes CONFIRMED_INFOGRAPHIC vs BUSTED_ORIGIN_TRACE."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    busted = verify_claim_math(
        claim="All 8.1 billion humans submerged would overflow Loch Ness (7.45 km^3)",
        python_expression_or_script="8.1e9 * 0.062",
        expected_threshold=7.45e9,
        comparison=">=",
    )
    assert busted["confirmed"] is False
    assert busted["route_branch"] == "BUSTED_ORIGIN_TRACE"
    assert busted["computed_value"] == pytest.approx(5.022e8)

    confirmed = verify_claim_math(
        claim="Folding a 0.1mm paper 42 times exceeds Earth-Moon distance (384,400 km)",
        python_expression_or_script="thickness_m = 0.0001\nresult = (thickness_m * (2 ** 42)) / 1000.0",
        expected_threshold=384400.0,
        comparison=">=",
    )
    assert confirmed["confirmed"] is True
    assert confirmed["route_branch"] == "CONFIRMED_INFOGRAPHIC"
    assert confirmed["computed_value"] > 400000.0


def test_foodie_tools_solver_and_ics_export(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify crawl constraint solver (clear vs rainy) and valid .ics calendar export."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    candidates = [
        {
            "name": "Old Chang Kee Curry Puff",
            "category": "starter",
            "price_sgd": 2.2,
            "minutes": 10,
            "rating": 4.5,
            "sheltered": True,
        },
        {
            "name": "Open-Air Alley Satay Cart",
            "category": "starter",
            "price_sgd": 3.0,
            "minutes": 12,
            "rating": 4.9,
            "sheltered": False,
        },
        {
            "name": "Tian Tian Hainanese Chicken Rice",
            "category": "main",
            "price_sgd": 6.0,
            "minutes": 20,
            "rating": 4.8,
            "sheltered": True,
        },
        {
            "name": "Luxury Truffle Wagyu Bowl",
            "category": "main",
            "price_sgd": 25.0,
            "minutes": 20,
            "rating": 5.0,
            "sheltered": True,
        },
        {
            "name": "Jin Yu Man Tang Mango Pomelo Sago",
            "category": "dessert",
            "price_sgd": 5.5,
            "minutes": 15,
            "rating": 4.7,
            "sheltered": True,
        },
    ]

    clear_plan = solve_crawl_constraints(
        json.dumps(candidates),
        max_budget_sgd=20.0,
        max_minutes=75,
        weather_condition="clear",
    )
    assert clear_plan["feasible"] is True
    assert len(clear_plan["selected_stops"]) == 3
    assert clear_plan["total_cost_sgd"] <= 20.0
    assert clear_plan["total_minutes"] <= 75
    clear_names = {s["name"] for s in clear_plan["selected_stops"]}
    assert "Open-Air Alley Satay Cart" in clear_names

    rainy_plan = solve_crawl_constraints(
        json.dumps(candidates),
        max_budget_sgd=20.0,
        max_minutes=75,
        weather_condition="heavy rain thunderstorm",
    )
    assert rainy_plan["feasible"] is True
    rainy_names = {s["name"] for s in rainy_plan["selected_stops"]}
    assert "Open-Air Alley Satay Cart" not in rainy_names
    assert "Old Chang Kee Curry Puff" in rainy_names

    ics_res = export_ics_calendar(
        crawl_title="Maxwell S$20 Foodie Crawl",
        stops_json=json.dumps(rainy_plan["selected_stops"]),
        output_filename="maxwell_crawl.ics",
    )
    assert os.path.isfile(ics_res["output_path"])
    assert ics_res["event_count"] == 3
    ics_text = open(ics_res["output_path"], encoding="utf-8").read()
    assert "BEGIN:VCALENDAR" in ics_text
    assert ics_text.count("BEGIN:VEVENT") == 3
    assert "Tian Tian Hainanese Chicken Rice" in ics_text


def test_dnd_tools_crypto_d20_and_hero_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cryptographic d20 rolls and persistent hero_state.json state machine."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    rolls = [roll_crypto_d20(modifier=3, skill_name="Executive Persuasion") for _ in range(40)]
    naturals = {r["natural_roll"] for r in rolls}
    assert all(1 <= r["natural_roll"] <= 20 for r in rolls)
    assert all(r["total"] == r["natural_roll"] + 3 for r in rolls)
    assert len(naturals) > 3  # Real CSPRNG produces varied rolls

    init_res = manage_hero_state(action="init", hero_name="Spreadsheet Paladin")
    assert init_res["hp"] == 40
    assert os.path.isfile(init_res["state_path"])

    upd_res = manage_hero_state(
        action="update",
        hero_name="Spreadsheet Paladin",
        hp_delta=-12,
        item_to_add="Amulet of Approved Headcount",
    )
    assert upd_res["hp"] == 28
    assert "Amulet of Approved Headcount" in upd_res["inventory"]

    loaded = manage_hero_state(action="get", hero_name="Spreadsheet Paladin")
    assert loaded["hp"] == 28
    assert "Amulet of Approved Headcount" in loaded["inventory"]


def test_orchestration_tools_dag_telemetry_and_pruning(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify emit_dag_step and record_pruned_branch emit structured telemetry markers."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(sandbox))

    step = emit_dag_step(
        node_id="shark_numbers",
        node_label="The Numbers Hawk",
        status="completed",
        summary="Scored CAC/LTV 4/10 due to dog grooming overhead",
    )
    assert step["event_type"] == "dag_step"
    assert step["node_id"] == "shark_numbers"
    assert step["status"] == "completed"

    pruned = record_pruned_branch(
        branch_name="Bubble Tea -> Tapioca -> Brazil -> Soccer",
        reason="Dead end at hop 3 with no aerospace connection to Apollo 11",
    )
    assert pruned["event_type"] == "pruned_branch"
    assert pruned["status"] == "pruned"
    assert os.path.isfile(pruned["log_path"])
