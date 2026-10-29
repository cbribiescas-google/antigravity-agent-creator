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

"""Tools for Scenario #9: Hourglass Foodie Optimizer.

Provides deterministic constraint optimization for a 3-stop Singapore hawker
food crawl (`starter + main + dessert`) under budget, duration, and weather
constraints, plus RFC 5545 iCalendar (`.ics`) schedule export.
"""

import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

_DEFAULT_LOCATION = "Maxwell / Chinatown"

_STARTER_TOKENS = frozenset(
    {
        "starter",
        "starters",
        "appetizer",
        "appetizers",
        "snack",
        "snacks",
        "drink",
        "drinks",
        "side",
        "sides",
        "beverage",
        "beverages",
        "opener",
    }
)
_MAIN_TOKENS = frozenset(
    {
        "main",
        "mains",
        "main course",
        "entree",
        "entrees",
        "entrée",
        "dish",
        "dishes",
        "noodle",
        "noodles",
        "rice",
        "savory",
    }
)
_DESSERT_TOKENS = frozenset(
    {
        "dessert",
        "desserts",
        "sweet",
        "sweets",
        "pastry",
        "pastries",
        "pudding",
        "ice cream",
        "treat",
        "treats",
    }
)
_WET_WEATHER_KEYWORDS = ("rain", "storm", "shower", "wet", "thunder")
_WET_WALK_BUFFER_MINUTES = 3


def _strip_json_fences(raw_text: str) -> str:
    """Strips optional Markdown code fences around a JSON payload."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _first_present(
    mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None
) -> Any:
    """Returns the first value in `mapping` whose key exists and is not None."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            val = mapping[key]
            if isinstance(val, str) and not val.strip():
                continue
            return val
    return default


def _parse_float(value: Any, default: float) -> float:
    """Coerces numeric or currency-formatted strings into a float."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]+", "", value.strip())
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return default
    return default


def _parse_int(value: Any, default: int) -> int:
    """Coerces numeric values or strings into an integer."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]+", "", value.strip())
        if cleaned:
            try:
                return round(float(cleaned))
            except ValueError:
                return default
    return default


def _parse_bool(value: Any, default: bool = True) -> bool:
    """Coerces booleans, numbers, or common truthy/falsy strings into a bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "sheltered", "indoor", "covered"}:
            return True
        if lowered in {"false", "no", "n", "0", "outdoor", "open-air", "unsheltered"}:
            return False
    return default


def _normalize_course(raw_course: Any, fallback: str = "") -> str:
    """Normalizes free-form course/category labels to starter, main, or dessert."""
    candidate = str(raw_course if raw_course is not None else fallback).strip().lower()
    if not candidate and fallback:
        candidate = fallback.strip().lower()
    if not candidate:
        return ""

    if candidate in _STARTER_TOKENS:
        return "starter"
    if candidate in _MAIN_TOKENS:
        return "main"
    if candidate in _DESSERT_TOKENS:
        return "dessert"

    # Substring / token fallback for composite labels such as "cold drink / starter"
    words = set(re.findall(r"[a-z]+", candidate))
    if words & _DESSERT_TOKENS or any(tok in candidate for tok in _DESSERT_TOKENS):
        return "dessert"
    if words & _STARTER_TOKENS or any(tok in candidate for tok in _STARTER_TOKENS):
        return "starter"
    if words & _MAIN_TOKENS or any(tok in candidate for tok in _MAIN_TOKENS):
        return "main"
    return ""


def _extract_raw_candidates(parsed: Any) -> list[tuple[dict[str, Any], str]]:
    """Extracts `(candidate_dict, fallback_course)` pairs from flexible JSON shapes."""
    extracted: list[tuple[dict[str, Any], str]] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                extracted.append((item, ""))
        return extracted

    if isinstance(parsed, dict):
        group_map = {
            "starters": "starter",
            "starter": "starter",
            "appetizers": "starter",
            "snacks": "starter",
            "drinks": "starter",
            "mains": "main",
            "main": "main",
            "entrees": "main",
            "dishes": "main",
            "desserts": "dessert",
            "dessert": "dessert",
            "sweets": "dessert",
        }
        matched_group = False
        for key, value in parsed.items():
            norm_key = str(key).strip().lower()
            if norm_key in group_map and isinstance(value, list):
                matched_group = True
                for item in value:
                    if isinstance(item, dict):
                        extracted.append((item, group_map[norm_key]))
        if matched_group:
            return extracted

        for list_key in ("candidates", "stalls", "stops", "items", "options"):
            if isinstance(parsed.get(list_key), list):
                for item in parsed[list_key]:
                    if isinstance(item, dict):
                        extracted.append((item, ""))
                return extracted

    return extracted


def _normalize_candidate(
    raw: dict[str, Any], fallback_course: str, index: int
) -> dict[str, Any]:
    """Normalizes a candidate dictionary into canonical solver fields."""
    name_val = _first_present(
        raw, ("name", "stall_name", "stall", "dish", "title"), f"Stall {index + 1}"
    )
    name = str(name_val).strip()

    stall_val = _first_present(raw, ("stall_name", "stall", "name", "title"), name)
    stall_key = str(stall_val).strip().lower()

    raw_course = _first_present(
        raw, ("course", "category", "type", "role", "meal_course", "stop_type"), None
    )
    course = _normalize_course(raw_course, fallback=fallback_course)

    price_raw = _first_present(raw, ("price_sgd", "price", "cost", "cost_sgd"), 0.0)
    price_sgd = max(0.0, _parse_float(price_raw, 0.0))

    mins_raw = _first_present(
        raw,
        (
            "minutes",
            "prep_minutes",
            "duration_minutes",
            "queue_minutes",
            "wait_minutes",
        ),
        15,
    )
    minutes = max(1, _parse_int(mins_raw, 15))

    has_explicit_walk = any(
        k in raw and raw[k] is not None
        for k in ("walk_minutes", "walk_time", "transit_minutes")
    )
    walk_raw = _first_present(raw, ("walk_minutes", "walk_time", "transit_minutes"), 5)
    walk_minutes = max(0, _parse_int(walk_raw, 5))

    rating_raw = _first_present(raw, ("rating", "score"), 4.5)
    rating = _parse_float(rating_raw, 4.5)

    sheltered_raw = _first_present(
        raw, ("sheltered", "indoor", "covered", "rain_safe"), True
    )
    sheltered = _parse_bool(sheltered_raw, default=True)

    explicit_loc = _first_present(
        raw, ("location", "hawker_centre", "hawker_center", "address", "venue"), None
    )
    has_explicit_location = explicit_loc is not None
    location = str(explicit_loc).strip() if explicit_loc is not None else _DEFAULT_LOCATION

    dish_val = _first_present(raw, ("dish", "signature_dish", "item"), None)
    notes_val = _first_present(raw, ("notes", "description"), None)

    normalized: dict[str, Any] = {
        "name": name,
        "course": course,
        "price_sgd": round(price_sgd, 2),
        "minutes": minutes,
        "walk_minutes": walk_minutes,
        "rating": round(rating, 2),
        "sheltered": sheltered,
        "location": location,
        "_stall_key": stall_key,
        "_has_explicit_location": has_explicit_location,
        "_has_explicit_walk": has_explicit_walk,
        "_index": index,
    }
    if dish_val is not None and str(dish_val).strip() != name:
        normalized["dish"] = str(dish_val).strip()
    if notes_val is not None:
        normalized["notes"] = str(notes_val).strip()
    return normalized


def _is_wet_weather(weather_condition: str) -> bool:
    """Checks whether weather_condition triggers rain-shelter and walk-buffer rules."""
    lowered = (weather_condition or "").strip().lower()
    return any(keyword in lowered for keyword in _WET_WEATHER_KEYWORDS)


def _same_hawker_centre(stop_a: dict[str, Any], stop_b: dict[str, Any]) -> bool:
    """Returns True when both stops explicitly share the exact same hawker centre."""
    if not (stop_a.get("_has_explicit_location") and stop_b.get("_has_explicit_location")):
        return False
    loc_a = str(stop_a.get("location", "")).strip().lower()
    loc_b = str(stop_b.get("location", "")).strip().lower()
    return bool(loc_a and loc_a == loc_b)


def _compute_inter_stop_walks(
    starter: dict[str, Any],
    main: dict[str, Any],
    dessert: dict[str, Any],
    is_wet: bool,
) -> tuple[int, int]:
    """Computes `(leg1_walk_minutes, leg2_walk_minutes)` across the 3 stops."""
    # Support both inbound walk convention (starter=0, main=6, dessert=4)
    # and default/outbound convention (starter=5, main=5, dessert=5 or 0).
    if (
        starter.get("_has_explicit_walk")
        and starter["walk_minutes"] == 0
        and dessert["walk_minutes"] > 0
    ):
        leg1 = int(main["walk_minutes"])
        leg2 = int(dessert["walk_minutes"])
    else:
        leg1 = int(starter["walk_minutes"])
        leg2 = int(main["walk_minutes"])

    if is_wet:
        if not _same_hawker_centre(starter, main):
            leg1 += _WET_WALK_BUFFER_MINUTES
        if not _same_hawker_centre(main, dessert):
            leg2 += _WET_WALK_BUFFER_MINUTES
    return leg1, leg2


def _format_stop_output(
    stop: dict[str, Any], stop_number: int, walk_to_next_minutes: int
) -> dict[str, Any]:
    """Formats a normalized stop dictionary for public tool output."""
    formatted: dict[str, Any] = {
        "stop_number": stop_number,
        "course": stop["course"],
        "name": stop["name"],
        "price_sgd": round(float(stop["price_sgd"]), 2),
        "minutes": int(stop["minutes"]),
        "walk_minutes": int(walk_to_next_minutes),
        "rating": round(float(stop["rating"]), 2),
        "sheltered": bool(stop["sheltered"]),
        "location": stop["location"],
    }
    if "dish" in stop:
        formatted["dish"] = stop["dish"]
    if "notes" in stop:
        formatted["notes"] = stop["notes"]
    return formatted


def solve_crawl_constraints(
    candidates_json: str,
    max_budget_sgd: float = 20.0,
    max_minutes: int = 75,
    weather_condition: str = "clear",
) -> dict[str, Any]:
    """Solves the optimal 3-stop starter + main + dessert hawker crawl under constraints.

    Evaluates all distinct-stall `(starter, main, dessert)` combinations against hard
    budget (`max_budget_sgd`), total duration (`max_minutes`), and wet-weather shelter
    constraints, ranking valid itineraries by highest total rating (tie-breaking by
    lower total cost and lower total duration).

    Expected `candidates_json` schema (parsed forgivingly):
        Accepts a JSON array of candidate objects, a wrapper object
        `{"candidates": [...]}` / `{"stalls": [...]}`, or a grouped object
        `{"starters": [...], "mains": [...], "desserts": [...]}`. Each candidate
        supports:
        - `name` (or `stall_name` / `stall` / `dish` / `title`, str): Stall or dish name.
        - `course` (or `category` / `type`, str): `"starter"` (`"appetizer"`, `"snack"`,
          `"drink"`, `"side"`), `"main"` (`"entree"`, `"dish"`, `"noodles"`, `"rice"`),
          or `"dessert"` (`"sweet"`, `"pastry"`).
        - `price_sgd` (or `price` / `cost` / `cost_sgd`, float): Price in SGD.
        - `minutes` (or `prep_minutes` / `duration_minutes` / `queue_minutes` /
          `wait_minutes`, int): Time spent queuing and eating at the stop (default 15).
        - `walk_minutes` (int): Base walking time in minutes per inter-stop leg (default 5).
        - `rating` (or `score`, float): Stall rating (default 4.5).
        - `sheltered` (or `indoor` / `covered` / `rain_safe`, bool): Rain-safe shelter
          flag (default True).
        - `location` (or `hawker_centre` / `address`, str): Hawker centre or area name
          (default `"Maxwell / Chinatown"`).

    Args:
        candidates_json: JSON string containing candidate hawker stalls/dishes.
        max_budget_sgd: Maximum total spend allowed in Singapore Dollars (default 20.0).
        max_minutes: Maximum total crawl duration in minutes including inter-stop walks
            (default 75).
        weather_condition: Current weather description such as `"clear"` or `"heavy rain"`
            (default `"clear"`). Wet conditions require `sheltered == True` and add a
            +3 minute cautious walk buffer per transition unless in the same hawker centre.

    Returns:
        Dictionary containing `feasible` (bool), `selected_stops` (list of 3 stop dicts),
        `total_cost_sgd`, `remaining_budget_sgd`, `total_minutes`, `max_budget_sgd`,
        `max_minutes`, `weather_condition`, `combinations_evaluated`, and `summary`.
        When no combination meets strict constraints, returns `feasible: False` along
        with `best_effort_stops` and a descriptive `constraint_violation` message.
    """
    budget_limit = float(max_budget_sgd)
    time_limit = int(max_minutes)
    weather_str = str(weather_condition or "clear")
    is_wet = _is_wet_weather(weather_str)

    try:
        if isinstance(candidates_json, list | dict):
            parsed = candidates_json
        else:
            cleaned_json = _strip_json_fences(str(candidates_json or ""))
            parsed = json.loads(cleaned_json)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        violation = f"Invalid candidates_json payload: {exc}"
        return {
            "feasible": False,
            "selected_stops": [],
            "best_effort_stops": [],
            "constraint_violation": violation,
            "total_cost_sgd": 0.0,
            "remaining_budget_sgd": round(budget_limit, 2),
            "total_minutes": 0,
            "max_budget_sgd": budget_limit,
            "max_minutes": time_limit,
            "weather_condition": weather_str,
            "combinations_evaluated": 0,
            "summary": f"Crawl optimization failed: {violation}",
        }

    raw_pairs = _extract_raw_candidates(parsed)
    normalized = [
        _normalize_candidate(item, fallback_course=fb, index=idx)
        for idx, (item, fb) in enumerate(raw_pairs)
    ]

    starters = [c for c in normalized if c["course"] == "starter"]
    mains = [c for c in normalized if c["course"] == "main"]
    desserts = [c for c in normalized if c["course"] == "dessert"]

    missing_courses = [
        course_name
        for course_name, group in (
            ("starter", starters),
            ("main", mains),
            ("dessert", desserts),
        )
        if not group
    ]
    if missing_courses:
        seen_stalls: set[str] = set()
        fallback_stops: list[dict[str, Any]] = []
        for cand in sorted(
            normalized,
            key=lambda c: (-c["rating"], c["price_sgd"], c["minutes"], c["_index"]),
        ):
            if cand["_stall_key"] in seen_stalls:
                continue
            if is_wet and not cand["sheltered"]:
                continue
            seen_stalls.add(cand["_stall_key"])
            fallback_stops.append(cand)
            if len(fallback_stops) == 3:
                break

        formatted_fallback = [
            _format_stop_output(
                stop,
                idx + 1,
                int(stop["walk_minutes"]) if idx < len(fallback_stops) - 1 else 0,
            )
            for idx, stop in enumerate(fallback_stops)
        ]
        violation = (
            f"Missing required course candidates for: {', '.join(missing_courses)}."
        )
        return {
            "feasible": False,
            "selected_stops": [],
            "best_effort_stops": formatted_fallback,
            "constraint_violation": violation,
            "total_cost_sgd": 0.0,
            "remaining_budget_sgd": round(budget_limit, 2),
            "total_minutes": 0,
            "max_budget_sgd": budget_limit,
            "max_minutes": time_limit,
            "weather_condition": weather_str,
            "combinations_evaluated": 0,
            "summary": f"Infeasible crawl: {violation}",
        }

    combinations_evaluated = 0
    valid_candidates: list[
        tuple[tuple[float, float, int, int, int, int], list[dict[str, Any]], float, int, float]
    ] = []
    best_effort_pool: list[
        tuple[
            tuple[int, float, float, float, float, int],
            list[dict[str, Any]],
            float,
            int,
            int,
        ]
    ] = []

    for starter in starters:
        for main in mains:
            if starter["_stall_key"] == main["_stall_key"]:
                continue
            if starter["name"].lower() == main["name"].lower():
                continue
            for dessert in desserts:
                if dessert["_stall_key"] in (
                    starter["_stall_key"],
                    main["_stall_key"],
                ):
                    continue
                if dessert["name"].lower() in (
                    starter["name"].lower(),
                    main["name"].lower(),
                ):
                    continue

                combinations_evaluated += 1
                leg1_walk, leg2_walk = _compute_inter_stop_walks(
                    starter, main, dessert, is_wet=is_wet
                )
                total_cost = round(
                    starter["price_sgd"] + main["price_sgd"] + dessert["price_sgd"], 2
                )
                total_mins = (
                    int(starter["minutes"])
                    + int(main["minutes"])
                    + int(dessert["minutes"])
                    + leg1_walk
                    + leg2_walk
                )
                total_rating = round(
                    starter["rating"] + main["rating"] + dessert["rating"], 4
                )

                stops_formatted = [
                    _format_stop_output(starter, 1, leg1_walk),
                    _format_stop_output(main, 2, leg2_walk),
                    _format_stop_output(dessert, 3, 0),
                ]

                unsheltered_count = (
                    sum(0 if s["sheltered"] else 1 for s in (starter, main, dessert))
                    if is_wet
                    else 0
                )
                budget_over = max(0.0, round(total_cost - budget_limit, 2))
                time_over = max(0, total_mins - time_limit)

                effort_key = (
                    unsheltered_count,
                    round(budget_over * 10.0 + float(time_over), 4),
                    budget_over,
                    float(time_over),
                    -total_rating,
                    total_mins,
                )
                best_effort_pool.append(
                    (
                        effort_key,
                        stops_formatted,
                        total_cost,
                        total_mins,
                        unsheltered_count,
                    )
                )

                if unsheltered_count == 0 and total_cost <= budget_limit + 1e-9 and total_mins <= time_limit:
                    rank_key = (
                        -total_rating,
                        total_cost,
                        total_mins,
                        int(starter["_index"]),
                        int(main["_index"]),
                        int(dessert["_index"]),
                    )
                    valid_candidates.append(
                        (rank_key, stops_formatted, total_cost, total_mins, total_rating)
                    )

    if valid_candidates:
        valid_candidates.sort(key=lambda item: item[0])
        _, selected_stops, best_cost, best_mins, best_rating = valid_candidates[0]
        stop_names = " -> ".join(s["name"] for s in selected_stops)
        summary = (
            f"Optimal 3-stop crawl ({stop_names}): SGD {best_cost:.2f} / "
            f"{budget_limit:.2f} budget, {best_mins} / {time_limit} min "
            f"(combined rating {best_rating:.2f}, weather='{weather_str}')."
        )
        return {
            "feasible": True,
            "selected_stops": selected_stops,
            "total_cost_sgd": round(best_cost, 2),
            "remaining_budget_sgd": round(budget_limit - best_cost, 2),
            "total_minutes": int(best_mins),
            "total_rating": round(best_rating, 2),
            "max_budget_sgd": budget_limit,
            "max_minutes": time_limit,
            "weather_condition": weather_str,
            "combinations_evaluated": combinations_evaluated,
            "summary": summary,
        }

    if not best_effort_pool:
        violation = (
            "No 3-stop combination with distinct stall names could be constructed "
            "from the provided candidates."
        )
        return {
            "feasible": False,
            "selected_stops": [],
            "best_effort_stops": [],
            "constraint_violation": violation,
            "total_cost_sgd": 0.0,
            "remaining_budget_sgd": round(budget_limit, 2),
            "total_minutes": 0,
            "max_budget_sgd": budget_limit,
            "max_minutes": time_limit,
            "weather_condition": weather_str,
            "combinations_evaluated": combinations_evaluated,
            "summary": f"Infeasible crawl: {violation}",
        }

    best_effort_pool.sort(key=lambda item: item[0])
    _, effort_stops, effort_cost, effort_mins, effort_unsheltered = best_effort_pool[0]

    reasons: list[str] = []
    if effort_unsheltered > 0:
        reasons.append(
            f"weather '{weather_str}' requires sheltered stalls ({effort_unsheltered} stop(s) unsheltered)"
        )
    if effort_cost > budget_limit + 1e-9:
        reasons.append(
            f"minimum cost SGD {effort_cost:.2f} exceeds max_budget_sgd SGD {budget_limit:.2f}"
        )
    if effort_mins > time_limit:
        reasons.append(
            f"minimum duration {effort_mins} min exceeds max_minutes {time_limit} min"
        )
    violation_msg = (
        "No valid 3-stop combination satisfied all hard constraints: "
        + "; ".join(reasons)
        + "."
    )

    return {
        "feasible": False,
        "selected_stops": [],
        "best_effort_stops": effort_stops,
        "constraint_violation": violation_msg,
        "total_cost_sgd": 0.0,
        "remaining_budget_sgd": round(budget_limit, 2),
        "total_minutes": 0,
        "max_budget_sgd": budget_limit,
        "max_minutes": time_limit,
        "weather_condition": weather_str,
        "combinations_evaluated": combinations_evaluated,
        "summary": f"Infeasible crawl: {violation_msg}",
    }


def _escape_ics_text(value: str) -> str:
    """Escapes a string value according to RFC 5545 Section 3.3.11 TEXT rules."""
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(";", "\\;").replace(",", "\\,")
    escaped = escaped.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    return escaped


def _format_ics_utc(dt: datetime) -> str:
    """Formats a timezone-aware datetime as an RFC 5545 UTC timestamp."""
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _resolve_sandbox_dir() -> str:
    """Resolves and creates the writable sandbox directory at call time."""
    sandbox_dir = os.environ.get("ANTIGRAVITY_WORKSPACE_DIR") or os.path.join(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness"), "sandbox"
    )
    abs_sandbox = os.path.abspath(sandbox_dir)
    os.makedirs(abs_sandbox, exist_ok=True)
    return abs_sandbox


def _sanitize_ics_filename(output_filename: str) -> str:
    """Sanitizes a user-provided `.ics` filename to prevent path traversal."""
    base = os.path.basename((output_filename or "crawl_schedule.ics").strip())
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).lstrip("._")
    if not cleaned:
        cleaned = "crawl_schedule.ics"
    if not cleaned.lower().endswith(".ics"):
        cleaned = f"{cleaned}.ics"
    if cleaned.lower() == ".ics":
        cleaned = "crawl_schedule.ics"
    return cleaned


def _extract_stops_list(stops_json: str) -> list[dict[str, Any]]:
    """Extracts a list of stop dictionaries from a JSON list or wrapper object."""
    if isinstance(stops_json, list):
        return [item for item in stops_json if isinstance(item, dict)]
    if isinstance(stops_json, dict):
        parsed: Any = stops_json
    else:
        cleaned = _strip_json_fences(str(stops_json or "[]"))
        parsed = json.loads(cleaned)

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        for key in ("selected_stops", "stops", "best_effort_stops", "itinerary", "items"):
            candidate_list = parsed.get(key)
            if isinstance(candidate_list, list) and candidate_list:
                return [item for item in candidate_list if isinstance(item, dict)]
        for key in ("selected_stops", "stops", "best_effort_stops"):
            candidate_list = parsed.get(key)
            if isinstance(candidate_list, list):
                return [item for item in candidate_list if isinstance(item, dict)]
    raise ValueError("stops_json must be a JSON list of stops or a dict containing 'selected_stops' or 'stops'.")


def export_ics_calendar(
    crawl_title: str,
    stops_json: str,
    output_filename: str = "crawl_schedule.ics",
) -> dict[str, Any]:
    """Exports an RFC 5545 iCalendar (`.ics`) file for a multi-stop food crawl.

    Writes sequential `VEVENT` entries spaced by each stop's `minutes` and
    inter-stop `walk_minutes` into the Antigravity sandbox directory using strict
    CRLF (`\\r\\n`) line endings.

    Args:
        crawl_title: Human-readable calendar title for the food crawl itinerary.
        stops_json: JSON string representing a list of stop dicts or a solver output
            dict containing `"selected_stops"` or `"stops"`.
        output_filename: Desired `.ics` filename inside the sandbox directory
            (default `"crawl_schedule.ics"`).

    Returns:
        Dictionary with `status` (`"created"`), `crawl_title`, `output_path`,
        `filename`, `event_count`, and `byte_size`.
    """
    sandbox_dir = _resolve_sandbox_dir()
    safe_filename = _sanitize_ics_filename(output_filename)
    output_path = os.path.abspath(os.path.join(sandbox_dir, safe_filename))
    if os.path.commonpath([sandbox_dir, output_path]) != sandbox_dir:
        safe_filename = "crawl_schedule.ics"
        output_path = os.path.join(sandbox_dir, safe_filename)

    stops = _extract_stops_list(stops_json)
    effective_title = (crawl_title or "").strip() or "Hourglass Hawker Crawl"

    now_utc = datetime.now(UTC).replace(second=0, microsecond=0)
    dtstamp_str = _format_ics_utc(now_utc)
    cursor_dt = now_utc + timedelta(minutes=5)

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Antigravity Hourglass Foodie Optimizer//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics_text(effective_title)}",
    ]

    for idx, raw_stop in enumerate(stops, start=1):
        name = str(
            _first_present(
                raw_stop, ("name", "stall_name", "stall", "dish", "title"), f"Stop {idx}"
            )
        ).strip()
        course_raw = _first_present(raw_stop, ("course", "category", "type"), "")
        course = _normalize_course(course_raw) or str(course_raw or f"stop {idx}").strip()
        price_sgd = _parse_float(
            _first_present(raw_stop, ("price_sgd", "price", "cost", "cost_sgd"), 0.0),
            0.0,
        )
        duration_mins = max(
            1,
            _parse_int(
                _first_present(
                    raw_stop,
                    ("minutes", "duration_minutes", "prep_minutes", "queue_minutes"),
                    15,
                ),
                15,
            ),
        )
        walk_mins = max(
            0,
            _parse_int(
                _first_present(
                    raw_stop, ("walk_minutes", "walk_time", "transit_minutes"), 5
                ),
                5,
            ),
        )
        location = str(
            _first_present(
                raw_stop,
                ("location", "hawker_centre", "hawker_center", "address"),
                _DEFAULT_LOCATION,
            )
        ).strip()
        rating = _parse_float(_first_present(raw_stop, ("rating", "score"), 4.5), 4.5)
        sheltered = _parse_bool(
            _first_present(raw_stop, ("sheltered", "indoor", "covered", "rain_safe"), True),
            default=True,
        )
        notes = str(
            _first_present(
                raw_stop,
                ("notes", "description", "dish"),
                f"{'Sheltered' if sheltered else 'Open-air'} stop ({walk_mins} min walk after stop)",
            )
        ).strip()

        start_dt = cursor_dt
        end_dt = start_dt + timedelta(minutes=duration_mins)
        cursor_dt = end_dt + timedelta(minutes=walk_mins)

        uid_seed = f"{effective_title}:{idx}:{name}:{_format_ics_utc(start_dt)}"
        uid_hash = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:12]
        uid = f"foodie-stop-{idx}-{uid_hash}@antigravity.local"

        summary_text = f"Stop {idx} ({course.title()}): {name}"
        description_text = (
            f"Course: {course.title()}\n"
            f"Price: SGD {price_sgd:.2f}\n"
            f"Rating: {rating:.1f}/5.0\n"
            f"Duration: {duration_mins} min\n"
            f"Notes: {notes}"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp_str}",
                f"DTSTART:{_format_ics_utc(start_dt)}",
                f"DTEND:{_format_ics_utc(end_dt)}",
                f"SUMMARY:{_escape_ics_text(summary_text)}",
                f"LOCATION:{_escape_ics_text(location)}",
                f"DESCRIPTION:{_escape_ics_text(description_text)}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    ics_payload = "\r\n".join(lines) + "\r\n"
    ics_bytes = ics_payload.encode("utf-8")

    with open(output_path, "wb") as f:
        f.write(ics_bytes)

    return {
        "status": "created",
        "crawl_title": crawl_title,
        "output_path": output_path,
        "filename": safe_filename,
        "event_count": len(stops),
        "byte_size": len(ics_bytes),
    }
