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

"""Prisoner's Dilemma AI Bot Gladiator Arena tool for Scenario #5."""

import importlib.util
import inspect
import json
import os
import random
import sys
import tempfile
from collections.abc import Callable
from types import ModuleType
from typing import Any

_STRATEGY_FUNCTION_NAMES: tuple[str, ...] = (
    "decide",
    "move",
    "play",
    "choose",
    "strategy",
    "next_move",
    "get_move",
)

_STRATEGY_CLASS_NAMES: tuple[str, ...] = (
    "Bot",
    "Player",
    "Strategy",
    "Gladiator",
)

_PAYOFF_MATRIX: dict[tuple[str, str], tuple[int, int]] = {
    ("C", "C"): (3, 3),
    ("C", "D"): (0, 5),
    ("D", "C"): (5, 0),
    ("D", "D"): (1, 1),
}


def _resolve_sandbox_dir() -> str:
    """Resolves and ensures the Antigravity sandbox directory exists."""
    sandbox_dir = os.environ.get("ANTIGRAVITY_WORKSPACE_DIR") or os.path.join(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness"),
        "sandbox",
    )
    resolved = os.path.abspath(sandbox_dir)
    os.makedirs(resolved, exist_ok=True)
    return resolved


def _resolve_bot_path(raw_path: str, sandbox_dir: str) -> str:
    """Resolves a relative or absolute bot `.py` path against `sandbox_dir`."""
    cleaned = (raw_path or "").strip()
    if cleaned.startswith("file://"):
        cleaned = cleaned[len("file://") :]
    if not cleaned:
        raise ValueError("Bot file path must be a non-empty string.")

    if os.path.isabs(cleaned):
        candidate = os.path.abspath(cleaned)
        if os.path.isfile(candidate):
            return candidate
    else:
        candidate = os.path.abspath(os.path.join(sandbox_dir, cleaned))
        if os.path.isfile(candidate):
            return candidate
        if cleaned.startswith("sandbox/"):
            stripped_candidate = os.path.abspath(
                os.path.join(sandbox_dir, cleaned[len("sandbox/") :])
            )
            if os.path.isfile(stripped_candidate):
                return stripped_candidate

    basename_candidate = os.path.abspath(
        os.path.join(sandbox_dir, os.path.basename(cleaned))
    )
    if os.path.isfile(basename_candidate):
        return basename_candidate

    raise FileNotFoundError(
        f"Bot Python file not found: '{raw_path}' (resolved to '{candidate}')."
    )


def _load_module_from_path(file_path: str, module_tag: str) -> ModuleType:
    """Loads a fresh isolated Python module instance from `file_path`."""
    module_name = f"_antigravity_gladiator_bot_{module_tag}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for bot file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _extract_class_strategy(cls_obj: type[Any]) -> Callable[..., Any] | None:
    """Instantiates `cls_obj()` and locates a strategy method on the instance."""
    try:
        instance = cls_obj()
    except Exception:
        return None

    for method_name in _STRATEGY_FUNCTION_NAMES:
        method = getattr(instance, method_name, None)
        if callable(method):
            return method
    if callable(instance):
        return instance
    return None


def _discover_strategy_callable(
    module: ModuleType, file_path: str
) -> Callable[..., Any]:
    """Finds the bot's decision callable inside a loaded module."""
    # 1. Check canonical and common top-level strategy function names.
    for fn_name in _STRATEGY_FUNCTION_NAMES:
        candidate = getattr(module, fn_name, None)
        if callable(candidate) and not isinstance(candidate, type):
            return candidate

    # 2. Check standard strategy class names instantiable with `()`.
    for cls_name in _STRATEGY_CLASS_NAMES:
        cls_obj = getattr(module, cls_name, None)
        if isinstance(cls_obj, type):
            method = _extract_class_strategy(cls_obj)
            if method is not None:
                return method

    # 3. Fallback: first public user-defined function in the module.
    for attr_name, obj in module.__dict__.items():
        if (
            not attr_name.startswith("_")
            and inspect.isfunction(obj)
            and getattr(obj, "__module__", None) == module.__name__
        ):
            return obj

    # 4. Fallback: first public user-defined class with a strategy method.
    for attr_name, obj in module.__dict__.items():
        if (
            not attr_name.startswith("_")
            and isinstance(obj, type)
            and getattr(obj, "__module__", None) == module.__name__
        ):
            method = _extract_class_strategy(obj)
            if method is not None:
                return method

    raise ValueError(
        f"No strategy callable found in '{file_path}'. Define "
        "`decide(my_history: list[str], opponent_history: list[str]) -> str` "
        "returning 'C' or 'D'."
    )


def _determine_call_arity(fn: Callable[..., Any]) -> int:
    """Determines whether to invoke `fn` with 0, 1, 2, or 3 positional arguments."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    pos_params = [
        p
        for p in params
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    has_varargs = any(
        p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
    )
    required_pos = sum(
        1 for p in pos_params if p.default is inspect.Parameter.empty
    )
    max_pos = len(pos_params)

    if required_pos > 3:
        raise ValueError(
            f"Strategy callable '{fn}' requires {required_pos} positional "
            "arguments; at most 3 (my_history, opponent_history, round_index) "
            "are supported."
        )

    if has_varargs:
        if max_pos >= 3:
            return 3
        return 2

    if max_pos == 0:
        return 0
    if max_pos == 1:
        return 1
    if max_pos == 2:
        return 2
    return 3


def _normalize_move(raw_move: Any) -> tuple[str, bool]:
    """Normalizes a bot's raw return move to `('C' | 'D', is_valid)`."""
    if isinstance(raw_move, bool):
        return ("C" if raw_move else "D"), True
    if isinstance(raw_move, str):
        token = raw_move.strip().upper()
        if token in ("C", "COOPERATE"):
            return "C", True
        if token in ("D", "DEFECT"):
            return "D", True
    return "C", False


def _invoke_bot_move(
    fn: Callable[..., Any],
    arity: int,
    my_history: list[str],
    opponent_history: list[str],
    round_index: int,
) -> tuple[str, bool]:
    """Invokes a bot strategy safely and returns `(normalized_move, valid)`."""
    try:
        if arity == 0:
            raw = fn()
        elif arity == 1:
            raw = fn(opponent_history.copy())
        elif arity == 2:
            raw = fn(my_history.copy(), opponent_history.copy())
        else:
            raw = fn(my_history.copy(), opponent_history.copy(), round_index)
    except Exception:
        return "C", False

    return _normalize_move(raw)


def _derive_unique_bot_names(resolved_paths: list[str]) -> list[str]:
    """Derives readable, collision-free bot names from file paths."""
    raw_stems = [
        os.path.splitext(os.path.basename(p))[0] or f"bot_{idx + 1}"
        for idx, p in enumerate(resolved_paths)
    ]
    if len(set(raw_stems)) == len(raw_stems):
        return raw_stems

    slots = ("a", "b", "c")
    counts: dict[str, int] = {}
    for stem in raw_stems:
        counts[stem] = counts.get(stem, 0) + 1

    unique_names: list[str] = []
    for idx, stem in enumerate(raw_stems):
        if counts[stem] > 1:
            suffix = slots[idx] if idx < len(slots) else str(idx + 1)
            unique_names.append(f"{stem}_{suffix}")
        else:
            unique_names.append(stem)
    return unique_names


def _play_head_to_head(
    bot_1_name: str,
    bot_1_path: str,
    bot_2_name: str,
    bot_2_path: str,
    rounds: int,
    match_index: int,
) -> dict[str, Any]:
    """Runs a deterministic head-to-head iterated Prisoner's Dilemma match."""
    mod_1 = _load_module_from_path(bot_1_path, f"m{match_index}_p1")
    fn_1 = _discover_strategy_callable(mod_1, bot_1_path)
    arity_1 = _determine_call_arity(fn_1)

    mod_2 = _load_module_from_path(bot_2_path, f"m{match_index}_p2")
    fn_2 = _discover_strategy_callable(mod_2, bot_2_path)
    arity_2 = _determine_call_arity(fn_2)

    random.seed(42)

    history_1: list[str] = []
    history_2: list[str] = []
    score_1 = 0
    score_2 = 0
    coop_1 = 0
    coop_2 = 0
    round_wins_1 = 0
    round_wins_2 = 0
    mutual_coop = 0
    mutual_defect = 0
    forfeits_1 = 0
    forfeits_2 = 0

    for round_idx in range(rounds):
        move_1, valid_1 = _invoke_bot_move(
            fn_1, arity_1, history_1, history_2, round_idx
        )
        move_2, valid_2 = _invoke_bot_move(
            fn_2, arity_2, history_2, history_1, round_idx
        )
        if not valid_1:
            forfeits_1 += 1
        if not valid_2:
            forfeits_2 += 1

        pts_1, pts_2 = _PAYOFF_MATRIX[(move_1, move_2)]
        score_1 += pts_1
        score_2 += pts_2

        if move_1 == "C":
            coop_1 += 1
        if move_2 == "C":
            coop_2 += 1

        if pts_1 > pts_2:
            round_wins_1 += 1
        elif pts_2 > pts_1:
            round_wins_2 += 1
        elif move_1 == "C" and move_2 == "C":
            mutual_coop += 1
        else:
            mutual_defect += 1

        history_1.append(move_1)
        history_2.append(move_2)

    if score_1 > score_2:
        winner = bot_1_name
        outcome_1 = "WIN"
        outcome_2 = "LOSS"
    elif score_2 > score_1:
        winner = bot_2_name
        outcome_1 = "LOSS"
        outcome_2 = "WIN"
    else:
        winner = "DRAW"
        outcome_1 = "DRAW"
        outcome_2 = "DRAW"

    return {
        "match_index": match_index,
        "bot_1": bot_1_name,
        "bot_2": bot_2_name,
        "bot_1_score": score_1,
        "bot_2_score": score_2,
        "winner": winner,
        "outcome_1": outcome_1,
        "outcome_2": outcome_2,
        "rounds": rounds,
        "bot_1_cooperations": coop_1,
        "bot_2_cooperations": coop_2,
        "bot_1_cooperation_rate": round(coop_1 / rounds, 4),
        "bot_2_cooperation_rate": round(coop_2 / rounds, 4),
        "bot_1_round_wins": round_wins_1,
        "bot_2_round_wins": round_wins_2,
        "mutual_cooperation_rounds": mutual_coop,
        "mutual_defection_rounds": mutual_defect,
        "bot_1_forfeits": forfeits_1,
        "bot_2_forfeits": forfeits_2,
    }


def _persist_json_atomic(target_path: str, payload: dict[str, Any]) -> None:
    """Writes `payload` atomically to `target_path` as formatted JSON."""
    parent_dir = os.path.dirname(target_path)
    os.makedirs(parent_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tournament_results_", suffix=".json", dir=parent_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def run_bot_tournament(
    bot_a_path: str,
    bot_b_path: str,
    bot_c_path: str,
    rounds: int = 2000,
) -> dict[str, Any]:
    """Runs a deterministic 3-bot Iterated Prisoner's Dilemma gladiator tournament.

    Loads three Python strategy bot files from the Antigravity sandbox (or
    absolute paths), validates their decision functions, executes a single
    round-robin tournament across all 3 head-to-head matchups (`A vs B`,
    `A vs C`, `B vs C`) with `random.seed(42)` reset before each pairing, and
    persists full standings to `<sandbox_dir>/tournament_results.json`.

    Canonical Bot File Interface:
        Each Python bot file should define
        `decide(my_history: list[str], opponent_history: list[str]) -> str`
        returning `'C'` (Cooperate) or `'D'` (Defect).

        For convenience, the loader also accepts alternative function names
        (`move`, `play`, `choose`, `strategy`, `next_move`, `get_move`), class
        implementations (`Bot`, `Player`, `Strategy`, `Gladiator`) instantiable
        with `()`, signatures with 0 (`fn()`), 1 (`fn(opponent_history)`),
        2 (`fn(my_history, opponent_history)`), or 3
        (`fn(my_history, opponent_history, round_index)`) arguments, and return
        values `'C'`/`'cooperate'`/`True` or `'D'`/`'defect'`/`False`
        (defaulting invalid outputs or runtime exceptions to `'C'` while
        counting forfeits).

    Payoff Matrix (per round):
        - `('C', 'C')` -> `(3, 3)` (Mutual Cooperation)
        - `('C', 'D')` -> `(0, 5)` (Sucker's Payoff vs Temptation)
        - `('D', 'C')` -> `(5, 0)` (Temptation vs Sucker's Payoff)
        - `('D', 'D')` -> `(1, 1)` (Mutual Defection)

    Args:
        bot_a_path: File path to Bot A's `.py` strategy file (relative to the
            sandbox directory or an absolute path).
        bot_b_path: File path to Bot B's `.py` strategy file (relative to the
            sandbox directory or an absolute path).
        bot_c_path: File path to Bot C's `.py` strategy file (relative to the
            sandbox directory or an absolute path).
        rounds: Number of iterated rounds per head-to-head matchup, clamped to
            `[1, 10000]`. Defaults to `2000` (`6000` total rounds and `12000`
            total bot move decisions across the 3 matchups).

    Returns:
        A dictionary containing the tournament summary and standings:
            - `status`: `"completed"`.
            - `rounds_per_match`: Clamped number of rounds per matchup.
            - `total_matches`: `3` (all unique head-to-head pairings).
            - `total_rounds_played`: `3 * rounds_per_match`.
            - `total_interactions`: `6 * rounds_per_match` total bot moves.
            - `champion`: Name of the #1 ranked bot on the leaderboard.
            - `leaderboard`: Sorted list of bot standing dicts (descending by
              `total_score`, `win_rate`, `cooperation_rate`), each with keys
              `rank`, `bot_name`, `file_path`, `total_score`,
              `average_score_per_round`, `matches_won`, `matches_drawn`,
              `matches_lost`, `win_rate`, `round_win_rate`, `cooperation_rate`,
              and `forfeits`.
            - `match_matrix`: Nested dict `bot_x -> bot_y -> {"my_score",
              "opponent_score", "outcome", "my_cooperation_rate",
              "opponent_cooperation_rate", "rounds"}`.
            - `matches`: List of per-match head-to-head result summaries.
            - `results_path`: Absolute path to `tournament_results.json`.
    """
    try:
        clamped_rounds = int(rounds)
    except (TypeError, ValueError):
        clamped_rounds = 2000
    clamped_rounds = max(1, min(10000, clamped_rounds))

    sandbox_dir = _resolve_sandbox_dir()
    resolved_paths = [
        _resolve_bot_path(bot_a_path, sandbox_dir),
        _resolve_bot_path(bot_b_path, sandbox_dir),
        _resolve_bot_path(bot_c_path, sandbox_dir),
    ]
    bot_names = _derive_unique_bot_names(resolved_paths)

    # Pre-validate that every bot file loads cleanly and exposes a valid callable.
    for idx, path in enumerate(resolved_paths):
        check_mod = _load_module_from_path(path, f"validate_{idx}")
        check_fn = _discover_strategy_callable(check_mod, path)
        _determine_call_arity(check_fn)

    stats: dict[str, dict[str, Any]] = {
        name: {
            "slot": idx,
            "bot_name": name,
            "file_path": resolved_paths[idx],
            "total_score": 0,
            "matches_won": 0,
            "matches_drawn": 0,
            "matches_lost": 0,
            "rounds_played": 0,
            "round_wins": 0,
            "cooperations": 0,
            "forfeits": 0,
        }
        for idx, name in enumerate(bot_names)
    }

    match_matrix: dict[str, dict[str, dict[str, Any]]] = {
        name: {} for name in bot_names
    }
    matches: list[dict[str, Any]] = []

    pairings = ((0, 1), (0, 2), (1, 2))
    for match_idx, (i, j) in enumerate(pairings, start=1):
        name_i, path_i = bot_names[i], resolved_paths[i]
        name_j, path_j = bot_names[j], resolved_paths[j]

        raw_match = _play_head_to_head(
            bot_1_name=name_i,
            bot_1_path=path_i,
            bot_2_name=name_j,
            bot_2_path=path_j,
            rounds=clamped_rounds,
            match_index=match_idx,
        )

        # Accumulate bot i stats.
        stats[name_i]["total_score"] += raw_match["bot_1_score"]
        stats[name_i]["rounds_played"] += clamped_rounds
        stats[name_i]["round_wins"] += raw_match["bot_1_round_wins"]
        stats[name_i]["cooperations"] += raw_match["bot_1_cooperations"]
        stats[name_i]["forfeits"] += raw_match["bot_1_forfeits"]
        if raw_match["outcome_1"] == "WIN":
            stats[name_i]["matches_won"] += 1
        elif raw_match["outcome_1"] == "LOSS":
            stats[name_i]["matches_lost"] += 1
        else:
            stats[name_i]["matches_drawn"] += 1

        # Accumulate bot j stats.
        stats[name_j]["total_score"] += raw_match["bot_2_score"]
        stats[name_j]["rounds_played"] += clamped_rounds
        stats[name_j]["round_wins"] += raw_match["bot_2_round_wins"]
        stats[name_j]["cooperations"] += raw_match["bot_2_cooperations"]
        stats[name_j]["forfeits"] += raw_match["bot_2_forfeits"]
        if raw_match["outcome_2"] == "WIN":
            stats[name_j]["matches_won"] += 1
        elif raw_match["outcome_2"] == "LOSS":
            stats[name_j]["matches_lost"] += 1
        else:
            stats[name_j]["matches_drawn"] += 1

        match_matrix[name_i][name_j] = {
            "my_score": raw_match["bot_1_score"],
            "opponent_score": raw_match["bot_2_score"],
            "outcome": raw_match["outcome_1"],
            "my_cooperation_rate": raw_match["bot_1_cooperation_rate"],
            "opponent_cooperation_rate": raw_match["bot_2_cooperation_rate"],
            "rounds": clamped_rounds,
        }
        match_matrix[name_j][name_i] = {
            "my_score": raw_match["bot_2_score"],
            "opponent_score": raw_match["bot_1_score"],
            "outcome": raw_match["outcome_2"],
            "my_cooperation_rate": raw_match["bot_2_cooperation_rate"],
            "opponent_cooperation_rate": raw_match["bot_1_cooperation_rate"],
            "rounds": clamped_rounds,
        }

        matches.append(
            {
                "match_index": match_idx,
                "bot_1": name_i,
                "bot_2": name_j,
                "bot_1_score": raw_match["bot_1_score"],
                "bot_2_score": raw_match["bot_2_score"],
                "winner": raw_match["winner"],
                "rounds": clamped_rounds,
                "bot_1_cooperation_rate": raw_match["bot_1_cooperation_rate"],
                "bot_2_cooperation_rate": raw_match["bot_2_cooperation_rate"],
                "mutual_cooperation_rounds": raw_match[
                    "mutual_cooperation_rounds"
                ],
                "mutual_defection_rounds": raw_match["mutual_defection_rounds"],
                "bot_1_forfeits": raw_match["bot_1_forfeits"],
                "bot_2_forfeits": raw_match["bot_2_forfeits"],
            }
        )

    unranked_entries: list[tuple[int, dict[str, Any]]] = []
    for name in bot_names:
        s = stats[name]
        matches_played = (
            s["matches_won"] + s["matches_drawn"] + s["matches_lost"]
        )
        rounds_played = s["rounds_played"]
        win_rate = (
            round(s["matches_won"] / matches_played, 4)
            if matches_played > 0
            else 0.0
        )
        round_win_rate = (
            round(s["round_wins"] / rounds_played, 4)
            if rounds_played > 0
            else 0.0
        )
        cooperation_rate = (
            round(s["cooperations"] / rounds_played, 4)
            if rounds_played > 0
            else 0.0
        )
        avg_score = (
            round(s["total_score"] / rounds_played, 4)
            if rounds_played > 0
            else 0.0
        )
        unranked_entries.append(
            (
                s["slot"],
                {
                    "rank": 0,
                    "bot_name": name,
                    "file_path": s["file_path"],
                    "total_score": s["total_score"],
                    "average_score_per_round": avg_score,
                    "matches_won": s["matches_won"],
                    "matches_drawn": s["matches_drawn"],
                    "matches_lost": s["matches_lost"],
                    "win_rate": win_rate,
                    "round_win_rate": round_win_rate,
                    "cooperation_rate": cooperation_rate,
                    "forfeits": s["forfeits"],
                },
            )
        )

    unranked_entries.sort(
        key=lambda item: (
            -item[1]["total_score"],
            -item[1]["win_rate"],
            -item[1]["cooperation_rate"],
            -item[1]["round_win_rate"],
            item[0],
        )
    )

    leaderboard: list[dict[str, Any]] = []
    for rank_idx, (_, entry) in enumerate(unranked_entries, start=1):
        entry["rank"] = rank_idx
        leaderboard.append(entry)

    results_path = os.path.join(sandbox_dir, "tournament_results.json")
    result: dict[str, Any] = {
        "status": "completed",
        "rounds_per_match": clamped_rounds,
        "total_matches": 3,
        "total_rounds_played": 3 * clamped_rounds,
        "total_interactions": 6 * clamped_rounds,
        "champion": leaderboard[0]["bot_name"],
        "leaderboard": leaderboard,
        "match_matrix": match_matrix,
        "matches": matches,
        "results_path": results_path,
    }

    _persist_json_atomic(results_path, result)
    return result
