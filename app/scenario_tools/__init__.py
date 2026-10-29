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

"""Unified Scenario Custom Tools Registry for the 10 Agentic DAG Scenarios.

Exports:
- `SCENARIO_TOOLS`: mapping of exact function name to Python tool callable.
- `get_scenario_tool_metadata()`: structured catalog of all scenario custom tools.
"""

import inspect
from collections.abc import Callable
from typing import Any

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

SCENARIO_TOOLS: dict[str, Callable[..., Any]] = {
    "generate_video_clip": generate_video_clip,
    "log_vision_critique": log_vision_critique,
    "validate_html5_game": validate_html5_game,
    "run_bot_tournament": run_bot_tournament,
    "verify_claim_math": verify_claim_math,
    "solve_crawl_constraints": solve_crawl_constraints,
    "export_ics_calendar": export_ics_calendar,
    "roll_crypto_d20": roll_crypto_d20,
    "manage_hero_state": manage_hero_state,
    "emit_dag_step": emit_dag_step,
    "record_pruned_branch": record_pruned_branch,
}


def get_scenario_tool_metadata() -> list[dict[str, Any]]:
    """Returns structured metadata for every registered scenario custom tool.

    Returns:
        List of dictionaries with keys `name`, `description`, `module`, and `source`.
    """
    metadata: list[dict[str, Any]] = []
    for name, fn in SCENARIO_TOOLS.items():
        doc = inspect.getdoc(fn) or ""
        first_paragraph = doc.split("\n\n", 1)[0].replace("\n", " ").strip()
        metadata.append(
            {
                "name": name,
                "description": first_paragraph or f"Scenario tool {name}.",
                "module": getattr(fn, "__module__", "app.scenario_tools"),
                "source": "scenario",
            }
        )
    return metadata


__all__ = [
    "SCENARIO_TOOLS",
    "emit_dag_step",
    "export_ics_calendar",
    "generate_video_clip",
    "get_scenario_tool_metadata",
    "log_vision_critique",
    "manage_hero_state",
    "record_pruned_branch",
    "roll_crypto_d20",
    "run_bot_tournament",
    "solve_crawl_constraints",
    "validate_html5_game",
    "verify_claim_math",
]
