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

"""Custom tools for Scenario #10: Corporate D&D State Machine.

Provides a cryptographically secure d20 skill-check roller backed by Python's
`secrets` CSPRNG and an atomic JSON hero-state persistence manager inside the
Antigravity sandbox directory.
"""

import json
import os
import secrets
import tempfile
from datetime import UTC, datetime
from typing import Any

_DEFAULT_HERO_NAME = "Spreadsheet Paladin"
_DEFAULT_LEVEL = 5
_DEFAULT_MAX_HP = 40
_DEFAULT_INVENTORY: tuple[str, ...] = (
    "Ergonomic Keyboard Shield",
    "Pivot Table Greatsword",
)

_INIT_ACTIONS: frozenset[str] = frozenset(
    {"init", "initialize", "reset", "create", "new"}
)
_READ_ACTIONS: frozenset[str] = frozenset(
    {"get", "load", "read", "status", "inspect", "view"}
)


def _resolve_sandbox_dir() -> str:
    """Resolves the active sandbox directory dynamically from environment variables."""
    workspace_dir = os.environ.get("ANTIGRAVITY_WORKSPACE_DIR", "").strip()
    if workspace_dir:
        return workspace_dir
    base_dir = (
        os.environ.get("ANTIGRAVITY_BASE_DIR", "").strip()
        or "/tmp/antigravity_harness"
    )
    return os.path.join(base_dir, "sandbox")


def _build_default_hero_state(hero_name: str, iso_ts: str) -> dict[str, Any]:
    """Constructs a fresh initial hero state dictionary."""
    resolved_name = hero_name.strip() if hero_name and hero_name.strip() else _DEFAULT_HERO_NAME
    return {
        "hero_name": resolved_name,
        "level": _DEFAULT_LEVEL,
        "hp": _DEFAULT_MAX_HP,
        "max_hp": _DEFAULT_MAX_HP,
        "inventory": list(_DEFAULT_INVENTORY),
        "turn_count": 0,
        "status": "ACTIVE",
        "updated_at": iso_ts,
    }


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    """Writes a JSON dictionary atomically to disk via temporary file replacement."""
    parent_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".hero_state_", suffix=".tmp", dir=parent_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(payload, tmp_file, indent=2)
            tmp_file.write("\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def roll_crypto_d20(
    modifier: int = 0, skill_name: str = "Action"
) -> dict[str, Any]:
    """Rolls a cryptographically secure 20-sided die (d20) for a Corporate D&D check.

    Uses the operating system CSPRNG via `secrets.randbelow(20) + 1` so rolls
    are genuinely unpredictable and never simulated by an LLM.

    Args:
        modifier: Signed integer bonus or penalty added to the natural d20 roll
            (for example, `+4` for proficiency or `-2` for scope creep).
        skill_name: Name of the skill, save, or corporate action being attempted
            (for example, `"Executive Persuasion"` or `"Budget Stealth"`).

    Returns:
        A dictionary containing:
            - `skill_name`: Resolved name of the skill check.
            - `natural_roll`: Unmodified d20 result in `[1, 20]`.
            - `modifier`: Signed integer modifier applied.
            - `total`: Sum of `natural_roll + modifier`.
            - `is_critical_success`: `True` when `natural_roll == 20`.
            - `is_critical_failure`: `True` when `natural_roll == 1`.
            - `outcome_tier`: One of `"CRITICAL_SUCCESS"`, `"CRITICAL_FAILURE"`,
              `"HEROIC_SUCCESS"`, `"SUCCESS"`, `"PARTIAL_SUCCESS"`, or `"FAILURE"`.
            - `rng_source`: `"secrets.randbelow(20)+1"`.
            - `entropy_token`: 8-character hex entropy proof from `secrets.token_hex(4)`.
            - `timestamp`: UTC ISO-8601 timestamp of the roll.
    """
    natural_roll = secrets.randbelow(20) + 1
    mod = int(modifier)
    total = natural_roll + mod
    is_critical_success = natural_roll == 20
    is_critical_failure = natural_roll == 1
    entropy_token = secrets.token_hex(4)
    iso_ts = datetime.now(UTC).isoformat()

    if is_critical_success:
        outcome_tier = "CRITICAL_SUCCESS"
    elif is_critical_failure:
        outcome_tier = "CRITICAL_FAILURE"
    elif total >= 18:
        outcome_tier = "HEROIC_SUCCESS"
    elif total >= 12:
        outcome_tier = "SUCCESS"
    elif total >= 8:
        outcome_tier = "PARTIAL_SUCCESS"
    else:
        outcome_tier = "FAILURE"

    resolved_skill = (
        skill_name.strip()
        if isinstance(skill_name, str) and skill_name.strip()
        else "Action"
    )

    return {
        "skill_name": resolved_skill,
        "natural_roll": natural_roll,
        "modifier": mod,
        "total": total,
        "is_critical_success": is_critical_success,
        "is_critical_failure": is_critical_failure,
        "outcome_tier": outcome_tier,
        "rng_source": "secrets.randbelow(20)+1",
        "entropy_token": entropy_token,
        "timestamp": iso_ts,
    }


def manage_hero_state(
    action: str,
    hero_name: str = "Spreadsheet Paladin",
    hp_delta: int = 0,
    item_to_add: str = "",
) -> dict[str, Any]:
    """Loads, mutates, and atomically persists the Corporate D&D hero state JSON.

    Persists state to `<sandbox_dir>/hero_state.json`, resolving `<sandbox_dir>`
    dynamically from `ANTIGRAVITY_WORKSPACE_DIR` or
    `<ANTIGRAVITY_BASE_DIR>/sandbox` (defaulting to `/tmp/antigravity_harness/sandbox`).

    Args:
        action: Case-insensitive state operation to perform. Supported groups:
            - `"init"`, `"reset"`, `"create"`: Resets/creates fresh hero state.
            - `"get"`, `"load"`, `"read"`, `"status"`: Loads existing hero state
              (or initializes default state if missing) without mutating unless
              `hp_delta != 0` or `item_to_add` is non-empty.
            - `"update"`, `"mutate"`, `"save"`, `"damage"`, `"heal"`,
              `"add_item"`, `"loot"`: Applies signed `hp_delta` and/or inventory
              additions, increments `turn_count`, and saves atomically.
        hero_name: Character name used when creating/resetting state (or renaming
            when a non-default name is explicitly provided).
        hp_delta: Strictly signed hit-point adjustment applied as
            `new_hp = max(0, min(max_hp, current_hp + int(hp_delta)))`. Pass a
            negative integer for damage (e.g., `-8`) and a positive integer for
            healing (e.g., `+5`).
        item_to_add: Optional loot or equipment name to append to `inventory`
            (whitespace-trimmed; exact duplicates are ignored).

    Returns:
        A dictionary containing:
            - `action`: Normalized lowercase action string executed.
            - `state_path`: Absolute path to the persisted `hero_state.json`.
            - `hero_name`: Active hero name.
            - `level`: Current hero level.
            - `hp`: Current clamped hit points (`0` to `max_hp`).
            - `max_hp`: Maximum hit points.
            - `inventory`: Copy of the hero's inventory list.
            - `turn_count`: Number of mutated turns recorded.
            - `status`: `"DEFEATED"` when `hp == 0`, otherwise `"ACTIVE"`.
            - `hero_state`: Full persisted state dictionary.
    """
    sandbox_dir = _resolve_sandbox_dir()
    os.makedirs(sandbox_dir, exist_ok=True)
    state_path = os.path.abspath(os.path.join(sandbox_dir, "hero_state.json"))

    norm_action = (action or "").strip().lower() or "get"
    signed_delta = int(hp_delta)
    cleaned_item = item_to_add.strip() if isinstance(item_to_add, str) else ""
    iso_ts = datetime.now(UTC).isoformat()

    state: dict[str, Any] | None = None
    loaded_from_disk = False

    if norm_action not in _INIT_ACTIONS and os.path.isfile(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                max_hp_val = int(raw.get("max_hp", _DEFAULT_MAX_HP))
                hp_val = max(0, min(max_hp_val, int(raw.get("hp", max_hp_val))))
                raw_inv = raw.get("inventory")
                inv_list = (
                    [str(x) for x in raw_inv if str(x).strip()]
                    if isinstance(raw_inv, list)
                    else list(_DEFAULT_INVENTORY)
                )
                existing_name = str(raw.get("hero_name") or "").strip() or (
                    hero_name.strip() or _DEFAULT_HERO_NAME
                )
                state = {
                    "hero_name": existing_name,
                    "level": int(raw.get("level", _DEFAULT_LEVEL)),
                    "hp": hp_val,
                    "max_hp": max_hp_val,
                    "inventory": inv_list,
                    "turn_count": int(raw.get("turn_count", 0)),
                    "status": "DEFEATED" if hp_val == 0 else "ACTIVE",
                    "updated_at": str(raw.get("updated_at") or iso_ts),
                }
                loaded_from_disk = True
        except (OSError, ValueError, TypeError):
            state = None

    if state is None:
        state = _build_default_hero_state(hero_name=hero_name, iso_ts=iso_ts)

    has_explicit_mutation = signed_delta != 0 or bool(cleaned_item)
    is_init = norm_action in _INIT_ACTIONS
    is_read_only = norm_action in _READ_ACTIONS and not has_explicit_mutation

    if not is_init and not is_read_only:
        provided_name = hero_name.strip() if isinstance(hero_name, str) else ""
        if provided_name and provided_name != _DEFAULT_HERO_NAME:
            state["hero_name"] = provided_name

    if is_init or has_explicit_mutation or not is_read_only:
        max_hp = int(state["max_hp"])
        current_hp = int(state["hp"])
        new_hp = max(0, min(max_hp, current_hp + signed_delta))
        state["hp"] = new_hp

        inventory: list[str] = list(state["inventory"])
        if cleaned_item and cleaned_item not in inventory:
            inventory.append(cleaned_item)
        state["inventory"] = inventory

        if not is_init:
            state["turn_count"] = int(state["turn_count"]) + 1

        state["status"] = "DEFEATED" if new_hp == 0 else "ACTIVE"
        state["updated_at"] = iso_ts
        _atomic_write_json(state_path, state)
    elif not loaded_from_disk:
        _atomic_write_json(state_path, state)

    return {
        "action": norm_action,
        "state_path": state_path,
        "hero_name": state["hero_name"],
        "level": state["level"],
        "hp": state["hp"],
        "max_hp": state["max_hp"],
        "inventory": list(state["inventory"]),
        "turn_count": state["turn_count"],
        "status": state["status"],
        "hero_state": dict(state),
    }
