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

"""Unit tests for the Antigravity Agent Builder & Dynamic Tool Synthesis Engine."""

import json
import os
import pathlib
import urllib.request

import pytest

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

from google.antigravity import LocalAgentConfig, TemplatedSystemInstructions, types

from app import agent as agent_mod
from app import agent_builder
from app.agent_builder import (
    AgentNotFoundError,
    build_custom_agent,
    build_local_agent_config,
    create_custom_tool,
    ensure_localharness_env,
    get_all_custom_tools_map,
    list_agents_catalog,
    list_registered_agents_and_tools,
    normalize_agent_id,
)


@pytest.fixture()
def isolated_builder_dirs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, pathlib.Path]:
    """Redirects dynamic_tools, mirror dynamic_tools, and agents registry to tmp_path."""
    dyn_dir = tmp_path / "dynamic_tools"
    mirror_dir = tmp_path / "harness_dynamic_tools"
    agents_dir = tmp_path / "agents"
    registry_dir = agents_dir / "registry"
    base_dir = tmp_path / "harness_base"

    monkeypatch.setenv("ANTIGRAVITY_DYNAMIC_TOOLS_DIR", str(dyn_dir))
    monkeypatch.setenv("ANTIGRAVITY_HARNESS_DYNAMIC_TOOLS_DIR", str(mirror_dir))
    monkeypatch.setenv("ANTIGRAVITY_AGENTS_DIR", str(agents_dir))
    monkeypatch.setenv("ANTIGRAVITY_AGENTS_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setenv("ANTIGRAVITY_BASE_DIR", str(base_dir))
    monkeypatch.setenv("ANTIGRAVITY_WORKSPACE_DIR", str(base_dir / "sandbox"))
    monkeypatch.setenv("ANTIGRAVITY_TRAJECTORIES_DIR", str(base_dir / "trajectories"))
    monkeypatch.setenv("ANTIGRAVITY_APP_DATA_DIR", str(base_dir / "app_data"))

    saved_registry = dict(agent_builder._DYNAMIC_TOOLS_REGISTRY)
    saved_sdk_tools = list(agent_mod.sdk_config.tools)
    agent_builder._DYNAMIC_TOOLS_REGISTRY.clear()

    yield {
        "dyn_dir": dyn_dir,
        "mirror_dir": mirror_dir,
        "agents_dir": agents_dir,
        "registry_dir": registry_dir,
        "base_dir": base_dir,
    }

    agent_builder._DYNAMIC_TOOLS_REGISTRY.clear()
    agent_builder._DYNAMIC_TOOLS_REGISTRY.update(saved_registry)
    agent_mod.sdk_config.tools = saved_sdk_tools


def test_root_agent_wires_builder_tools() -> None:
    """Verify `app.agent.sdk_config` and `SYSTEM_INSTRUCTIONS` expose Agent Builder tools."""
    tool_names = [getattr(t, "__name__", "") for t in agent_mod.sdk_config.tools]
    assert "generate_video" in tool_names
    assert "create_custom_tool" in tool_names
    assert "build_custom_agent" in tool_names
    assert "list_registered_agents_and_tools" in tool_names

    assert "create_custom_tool" in agent_mod.SYSTEM_INSTRUCTIONS
    assert "build_custom_agent" in agent_mod.SYSTEM_INSTRUCTIONS
    assert "list_registered_agents_and_tools" in agent_mod.SYSTEM_INSTRUCTIONS


def test_normalize_agent_id() -> None:
    """Verify kebab-case normalization and invalid ID rejection."""
    assert normalize_agent_id("Trailer_Director") == "trailer-director"
    assert normalize_agent_id("  Six Degrees Detective!! ") == "six-degrees-detective"
    with pytest.raises(ValueError):
        normalize_agent_id("   ---   ")


def test_create_custom_tool_validates_writes_mirrors_and_auto_injects_docstring(
    isolated_builder_dirs: dict[str, pathlib.Path],
) -> None:
    """Verify `create_custom_tool` AST checks, auto-docstring/type injection, mirroring, and live registration."""
    code = """
import math

def compute_nessie_ratio(humans_count=8100000000, loch_ness_km3: float = 7.45):
    human_vol_km3 = (humans_count * 0.062) / 1e9
    return {
        "human_vol_km3": round(human_vol_km3, 4),
        "loch_ness_km3": loch_ness_km3,
        "fits_easily": human_vol_km3 < loch_ness_km3,
        "sqrt_check": round(math.sqrt(loch_ness_km3), 3),
    }
"""
    res = create_custom_tool(
        tool_name="compute_nessie_ratio",
        description="Computes human crowd volume against Loch Ness volume in cubic kilometers.",
        python_code=code,
    )
    assert res["status"] == "created"
    assert res["tool_name"] == "compute_nessie_ratio"
    assert res["parameters"] == ["humans_count", "loch_ness_km3"]
    assert "Loch Ness" in res["description"]

    mod_path = pathlib.Path(res["module_path"])
    mirror_path = pathlib.Path(res["mirror_path"])
    assert mod_path.is_file()
    assert mirror_path.is_file()
    assert mod_path.read_text(encoding="utf-8") == mirror_path.read_text(encoding="utf-8")

    # Verify the callable is immediately live in `get_all_custom_tools_map()` and executable.
    tools_map = get_all_custom_tools_map()
    assert "compute_nessie_ratio" in tools_map
    fn = tools_map["compute_nessie_ratio"]
    out = fn()
    assert out["fits_easily"] is True
    assert out["human_vol_km3"] == pytest.approx(0.5022, rel=1e-3)

    # Verify root sdk_config was also refreshed with the new dynamic tool.
    root_cfg = build_local_agent_config("antigravity")
    root_tool_names = [getattr(t, "__name__", "") for t in root_cfg.tools]
    assert "compute_nessie_ratio" in root_tool_names


def test_create_custom_tool_rejects_invalid_names_syntax_and_dangerous_imports(
    isolated_builder_dirs: dict[str, pathlib.Path],
) -> None:
    """Verify validation guards on `create_custom_tool`."""
    # Invalid identifier
    with pytest.raises(ValueError, match="Invalid tool_name"):
        create_custom_tool(
            tool_name="Bad-Tool-Name",
            description="Invalid name",
            python_code="def bad(): return 1",
        )

    # Protected builder tool override blocked
    with pytest.raises(ValueError, match="protected"):
        create_custom_tool(
            tool_name="build_custom_agent",
            description="Attempt override",
            python_code="def build_custom_agent(x: str): return x",
        )

    # Syntax error
    with pytest.raises(ValueError, match="Invalid Python syntax"):
        create_custom_tool(
            tool_name="broken_syntax",
            description="Broken",
            python_code="def broken_syntax(x: int) ->\n    return x",
        )

    # Missing matching top-level def
    with pytest.raises(ValueError, match="must define a top-level function"):
        create_custom_tool(
            tool_name="expected_fn",
            description="Wrong fn name",
            python_code="def other_fn(x: int) -> int:\n    '''Doc.'''\n    return x\n",
        )

    # Dangerous subprocess import blocked
    with pytest.raises(ValueError, match="blocked"):
        create_custom_tool(
            tool_name="sneaky_shell",
            description="Should fail",
            python_code="import subprocess\ndef sneaky_shell(cmd: str) -> str:\n    return cmd\n",
        )

    # Dangerous eval() call blocked
    with pytest.raises(ValueError, match="blocked"):
        create_custom_tool(
            tool_name="sneaky_eval",
            description="Should fail",
            python_code="def sneaky_eval(expr: str) -> str:\n    return str(eval(expr))\n",
        )


def test_build_custom_agent_end_to_end_with_dynamic_and_scenario_tools(
    isolated_builder_dirs: dict[str, pathlib.Path],
) -> None:
    """Verify building a custom DAG agent writes `.md` + `.json` and produces a valid `LocalAgentConfig`."""
    create_custom_tool(
        tool_name="score_pitch_valuation",
        description="Calculates implied post-money valuation from Shark offer.",
        python_code="""
def score_pitch_valuation(ask_amount: float, equity_pct: float) -> dict:
    \"\"\"Computes implied valuation from investment ask and equity percentage.\"\"\"
    valuation = ask_amount / (equity_pct / 100.0) if equity_pct > 0 else 0.0
    return {"implied_valuation": round(valuation, 2)}
""",
    )

    dag_nodes = [
        {"id": "pitch_intake", "label": "Founder Pitch", "type": "input"},
        {"id": "shark_panel", "label": "3-Shark Parallel Roast", "type": "fanout"},
        {"id": "term_sheet", "label": "Term Sheet Synthesis", "type": "reduce"},
    ]
    dag_edges = [
        {"from": "pitch_intake", "to": "shark_panel", "label": "broadcast"},
        {"from": "shark_panel", "to": "term_sheet", "label": "aggregate"},
    ]
    subagents = [
        {
            "name": "numbers_shark",
            "description": "Unit economics & margin shark",
            "system_instructions": "Scrutinize CAC, LTV, and gross margins ruthlessly.",
            "tools": ["search_web", "score_pitch_valuation", "emit_dag_step"],
        },
        {
            "name": "brand_shark",
            "description": "Viral consumer brand shark",
            "system_instructions": "Evaluate consumer hype, retention, and storytelling.",
            "tools": ["view_file", "emit_dag_step"],
        },
    ]

    summary = build_custom_agent(
        agent_id="Shark Tank Panel",
        display_name="Shark Tank Venture Panel",
        description="Parallel 3-Shark map-reduce venture pitch evaluator.",
        dag_topology="Parallel Map-Reduce Fan-Out DAG",
        system_instructions="Coordinate Shark subagents in parallel and synthesize a Term Sheet.",
        tool_names=[
            "create_file",
            "generate_image",
            "emit_dag_step",
            "score_pitch_valuation",
        ],
        dag_nodes_json=json.dumps(dag_nodes),
        dag_edges_json=json.dumps(dag_edges),
        enable_subagents=True,
        subagent_specs_json=json.dumps(subagents),
    )

    assert summary["status"] == "created"
    assert summary["agent_id"] == "shark-tank-panel"
    assert summary["dag_topology"] == "Parallel Map-Reduce Fan-Out DAG"
    assert "score_pitch_valuation" in summary["tools_bound"]
    assert "emit_dag_step" in summary["tools_bound"]
    assert "start_subagent" in summary["tools_bound"]

    # Check Markdown custom agent file
    md_path = pathlib.Path(summary["md_path"])
    assert md_path.is_file()
    md_text = md_path.read_text(encoding="utf-8")
    assert md_text.startswith("---\n")
    assert "name: shark-tank-panel" in md_text
    assert "mainAgent: true" in md_text
    assert "subagent: true" in md_text
    assert "commandExecutionPolicy: auto" in md_text
    assert "# System Instructions" in md_text
    assert "# DAG Architecture" in md_text

    # Check Registry JSON spec
    reg_path = pathlib.Path(summary["registry_path"])
    assert reg_path.is_file()
    spec = json.loads(reg_path.read_text(encoding="utf-8"))
    assert spec["agent_id"] == "shark-tank-panel"
    assert spec["enable_subagents"] is True
    assert len(spec["dag_nodes"]) == 3
    assert len(spec["dag_edges"]) == 2
    assert spec["dag_edges"][0]["source"] == "pitch_intake"
    assert spec["dag_edges"][0]["target"] == "shark_panel"

    # Check list_agents_catalog includes both root `antigravity` and `shark-tank-panel`
    catalog = list_agents_catalog()
    assert catalog[0]["agent_id"] == "antigravity"
    assert catalog[0]["is_builder"] is True
    custom_ids = [entry["agent_id"] for entry in catalog[1:]]
    assert "shark-tank-panel" in custom_ids

    # Check list_registered_agents_and_tools reflects dynamic tool, scenario tools, and registered agent
    inventory = list_registered_agents_and_tools()
    assert "score_pitch_valuation" in inventory["all_tool_names"]
    assert "emit_dag_step" in inventory["all_tool_names"]
    assert inventory["counts"]["dynamic_tools"] == 1
    assert inventory["counts"]["registered_agents"] == 1

    # Check build_local_agent_config constructs a real LocalAgentConfig with SubagentConfigs
    cfg = build_local_agent_config("shark-tank-panel")
    assert isinstance(cfg, LocalAgentConfig)
    assert cfg.model == "gemini-3.7-flash"
    assert isinstance(cfg.system_instructions, TemplatedSystemInstructions)
    assert "Shark Tank Venture Panel" in (cfg.system_instructions.identity or "")
    assert cfg.capabilities.enable_subagents is True
    assert types.BuiltinTools.START_SUBAGENT in (cfg.capabilities.enabled_tools or [])
    assert types.BuiltinTools.CREATE_FILE in (cfg.capabilities.enabled_tools or [])
    assert len(cfg.subagents) == 2
    sub_names = {s.name for s in cfg.subagents}
    assert sub_names == {"numbers_shark", "brand_shark"}
    cfg_custom_tool_names = {getattr(t, "__name__", "") for t in cfg.tools}
    assert {"score_pitch_valuation", "emit_dag_step"} <= cfg_custom_tool_names


def test_build_custom_agent_rejects_unknown_tools_and_missing_agent_raises(
    isolated_builder_dirs: dict[str, pathlib.Path],
) -> None:
    """Verify unknown tool validation and `AgentNotFoundError` for nonexistent agents."""
    with pytest.raises(ValueError, match="Unknown tool_names"):
        build_custom_agent(
            agent_id="bad-tools-agent",
            display_name="Bad Tools Agent",
            description="Uses nonexistent tool",
            dag_topology="Linear",
            system_instructions="Do something.",
            tool_names=["view_file", "totally_nonexistent_magic_tool_xyz"],
        )

    with pytest.raises(AgentNotFoundError):
        build_local_agent_config("nonexistent-agent-id")


def test_local_metadata_bridge_serves_google_flavor_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `ensure_localharness_env` starts the loopback GCE metadata bridge when local ADC exists."""
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CLOUD_RUN_JOB", raising=False)

    env = ensure_localharness_env()
    if env is not None:
        assert env["GOOGLE_APPLICATION_CREDENTIALS"] == ""
        assert "127.0.0.1:" in env["GCE_METADATA_HOST"]
        host = env["GCE_METADATA_HOST"]
        req = urllib.request.Request(
            f"http://{host}/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers.get("Metadata-Flavor") == "Google"
            body = resp.read().decode("utf-8")
            assert len(body) > 0
