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

"""Sandboxed quantitative verification tools for Scenario #7 (Conditional Router MythBuster)."""

import contextlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from typing import Any

_SUPPORTED_COMPARISONS = frozenset({">=", ">", "<=", "<", "==", "!=", "approx"})

# Matches standalone numeric literals (integers, decimals, comma-grouped numbers,
# scientific notation) while avoiding unit exponents/suffixes like `m^3` or `km2`.
_STDOUT_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_.\^])"
    r"[+-]?"
    r"(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
    r"(?:[eE][+-]?\d+)?"
    r"(?![A-Za-z0-9_]|\.\d|\^\d)"
)

_RUNNER_TEMPLATE = """\
import ast
import decimal
import fractions
import json
import math
import statistics
import traceback

CODE = {code_literal}
OUTCOME_PATH = {outcome_path_literal}
CANDIDATE_VARS = ("result", "computed_value", "value", "answer", "output", "total")


def _to_float(val):
    if isinstance(val, bool) or val is None:
        return None
    if isinstance(val, (int, float, decimal.Decimal, fractions.Fraction)):
        fval = float(val)
        if math.isnan(fval):
            raise ValueError("Computed numeric value is NaN.")
        return fval
    return None


def _execute():
    namespace = {{
        "__builtins__": __builtins__,
        "__name__": "__main__",
        "math": math,
        "statistics": statistics,
        "fractions": fractions,
        "decimal": decimal,
        "Decimal": decimal.Decimal,
        "Fraction": fractions.Fraction,
    }}

    try:
        expr_ast = ast.parse(CODE.strip(), mode="eval")
    except SyntaxError:
        expr_ast = None

    if expr_ast is not None:
        raw_val = eval(compile(expr_ast, "<mythbuster_expr>", "eval"), namespace)
        return {{"ok": True, "computed_value": _to_float(raw_val)}}

    mod_ast = ast.parse(CODE, mode="exec")
    last_expr_val = None
    try:
        if mod_ast.body and isinstance(mod_ast.body[-1], ast.Expr):
            prefix_mod = ast.Module(body=mod_ast.body[:-1], type_ignores=[])
            ast.fix_missing_locations(prefix_mod)
            if prefix_mod.body:
                exec(compile(prefix_mod, "<mythbuster_script>", "exec"), namespace)
            tail_expr = ast.Expression(body=mod_ast.body[-1].value)
            ast.fix_missing_locations(tail_expr)
            last_expr_val = eval(
                compile(tail_expr, "<mythbuster_script>", "eval"), namespace
            )
        else:
            exec(compile(mod_ast, "<mythbuster_script>", "exec"), namespace)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise RuntimeError(
                f"Calculation script exited with status {{exc.code!r}}."
            ) from exc

    for var_name in CANDIDATE_VARS:
        if var_name in namespace:
            num_val = _to_float(namespace[var_name])
            if num_val is not None:
                return {{"ok": True, "computed_value": num_val}}

    num_val = _to_float(last_expr_val)
    if num_val is not None:
        return {{"ok": True, "computed_value": num_val}}

    return {{"ok": True, "computed_value": None}}


def main():
    try:
        payload = _execute()
    except Exception as exc:
        payload = {{
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }}
    with open(OUTCOME_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


if __name__ == "__main__":
    main()
"""


def _resolve_sandbox_dir() -> str:
    """Resolves and ensures the isolated sandbox directory at call time."""
    sandbox_dir = os.environ.get("ANTIGRAVITY_WORKSPACE_DIR") or os.path.join(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness"),
        "sandbox",
    )
    os.makedirs(sandbox_dir, exist_ok=True)
    return sandbox_dir


def _normalize_code(python_expression_or_script: str) -> str:
    """Normalizes expression or script text, removing optional markdown code fences."""
    if not isinstance(python_expression_or_script, str):
        raise ValueError("python_expression_or_script must be a string.")
    cleaned = textwrap.dedent(python_expression_or_script).strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = textwrap.dedent("\n".join(lines[1:-1])).strip()
    if not cleaned:
        raise ValueError("python_expression_or_script must not be empty.")
    return cleaned


def _normalize_comparison(comparison: str) -> str:
    """Validates and normalizes the threshold comparison operator."""
    if not isinstance(comparison, str):
        raise ValueError(f"Unsupported comparison operator: {comparison!r}.")
    norm = comparison.strip().lower()
    if norm not in _SUPPORTED_COMPARISONS:
        supported = ", ".join(sorted(_SUPPORTED_COMPARISONS))
        raise ValueError(
            f"Unsupported comparison operator {comparison!r}. "
            f"Expected one of: {supported}."
        )
    return norm


def _extract_number_from_stdout(stdout_text: str) -> float | None:
    """Extracts the last numeric value printed to stdout, scanning bottom-up."""
    for raw_line in reversed(stdout_text.splitlines()):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if " " not in stripped and "\t" not in stripped:
            with contextlib.suppress(ValueError):
                direct_val = float(stripped.replace(",", ""))
                if not math.isnan(direct_val):
                    return direct_val
        matches = _STDOUT_NUMBER_RE.findall(stripped)
        for token in reversed(matches):
            with contextlib.suppress(ValueError):
                parsed = float(token.replace(",", ""))
                if not math.isnan(parsed):
                    return parsed
    return None


def _evaluate_comparison(
    computed_value: float,
    expected_threshold: float,
    comparison: str,
) -> bool:
    """Evaluates whether `computed_value` satisfies `comparison` vs `expected_threshold`."""
    if comparison == ">=":
        return computed_value >= expected_threshold
    if comparison == ">":
        return computed_value > expected_threshold
    if comparison == "<=":
        return computed_value <= expected_threshold
    if comparison == "<":
        return computed_value < expected_threshold
    if comparison == "==":
        return math.isclose(
            computed_value, expected_threshold, rel_tol=1e-12, abs_tol=0.0
        )
    if comparison == "!=":
        return not math.isclose(
            computed_value, expected_threshold, rel_tol=1e-12, abs_tol=0.0
        )
    if comparison == "approx":
        return math.isclose(
            computed_value, expected_threshold, rel_tol=0.05, abs_tol=1e-6
        )
    raise ValueError(f"Unsupported comparison operator: {comparison!r}.")


def verify_claim_math(
    claim: str,
    python_expression_or_script: str,
    expected_threshold: float,
    comparison: str = ">=",
) -> dict[str, Any]:
    """Executes an isolated math/physics calculation to verify a quantitative claim.

    Runs `python_expression_or_script` inside an isolated Python subprocess (`-I`)
    rooted in the Antigravity sandbox with `math`, `statistics`, `fractions`, and
    `decimal` pre-imported. Compares the resulting `computed_value` against
    `expected_threshold` using `comparison`, and selects the Scenario #7
    Conditional Router MythBuster branch (`CONFIRMED_INFOGRAPHIC` when confirmed,
    or `BUSTED_ORIGIN_TRACE` when busted).

    Supports both single/multi-line Python expressions (`eval` mode) and full
    multi-line Python scripts (`exec` mode, extracting `computed_value` from
    `result`, `computed_value`, `value`, `answer`, `output`, or `total`, a trailing
    expression statement, or the last numeric value printed to `stdout`).

    Args:
        claim: Natural-language statement of the quantitative myth or claim being
            tested (for example, fitting 8.1 billion humans inside Loch Ness).
        python_expression_or_script: Python expression or multi-line script that
            computes the test quantity using standard math/physics formulas.
        expected_threshold: Numeric threshold against which the computed value is
            compared.
        comparison: Comparison operator applied as
            `computed_value <comparison> expected_threshold`. Supported values are
            `">="`, `">"`, `"<="`, `"<"`, `"=="`, `"!="`, and `"approx"` (within
            5% relative tolerance or `1e-6` absolute tolerance). Defaults to `">="`.

    Returns:
        Dictionary containing:
            - `confirmed` (bool): True if the comparison holds, False otherwise.
            - `computed_value` (float): Extracted numeric result of the calculation.
            - `expected_threshold` (float): Threshold converted to `float`.
            - `comparison` (str): Normalized comparison operator used.
            - `route_branch` (str): `"CONFIRMED_INFOGRAPHIC"` if confirmed else
              `"BUSTED_ORIGIN_TRACE"`.
            - `verdict` (str): `"CONFIRMED"` if confirmed else `"BUSTED"`.
            - `claim` (str): The evaluated claim string.
            - `stdout` (str): Stripped standard output captured from execution.

    Raises:
        ValueError: If `comparison` is unsupported, `expected_threshold` is not a
            valid number, execution fails, or no numeric `computed_value` can be
            extracted.
    """
    norm_comparison = _normalize_comparison(comparison)
    if isinstance(expected_threshold, bool):
        raise ValueError("expected_threshold must be numeric, not bool.")
    try:
        threshold_val = float(expected_threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"expected_threshold must be numeric, got {expected_threshold!r}."
        ) from exc
    if math.isnan(threshold_val):
        raise ValueError("expected_threshold must not be NaN.")

    cleaned_code = _normalize_code(python_expression_or_script)
    sandbox_dir = _resolve_sandbox_dir()

    with tempfile.NamedTemporaryFile(
        mode="w",
        prefix="_mythbuster_runner_",
        suffix=".py",
        dir=sandbox_dir,
        encoding="utf-8",
        delete=False,
    ) as runner_file:
        runner_path = runner_file.name
        outcome_path = f"{runner_path}.out.json"
        runner_file.write(
            _RUNNER_TEMPLATE.format(
                code_literal=repr(cleaned_code),
                outcome_path_literal=repr(outcome_path),
            )
        )

    try:

        isolated_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": sandbox_dir,
            "TMPDIR": sandbox_dir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-I", runner_path],
                cwd=sandbox_dir,
                env=isolated_env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "Calculation timed out after 10 seconds in isolated sandbox."
            ) from exc

        stdout_text = proc.stdout or ""
        stderr_text = (proc.stderr or "").strip()

        outcome: dict[str, Any] | None = None
        if os.path.exists(outcome_path):
            with open(outcome_path, encoding="utf-8") as outcome_file:
                outcome = json.load(outcome_file)

        if outcome is not None and not outcome.get("ok", False):
            err_type = outcome.get("error_type", "ExecutionError")
            err_msg = outcome.get("error", "Unknown error")
            raise ValueError(
                f"Failed to execute calculation ({err_type}: {err_msg})."
            )

        if proc.returncode != 0 and outcome is None:
            detail = stderr_text or f"subprocess exited with code {proc.returncode}"
            raise ValueError(f"Failed to execute calculation: {detail}")

        computed_raw: float | None = None
        if outcome is not None and outcome.get("computed_value") is not None:
            computed_raw = float(outcome["computed_value"])
        else:
            computed_raw = _extract_number_from_stdout(stdout_text)

        if computed_raw is None or math.isnan(computed_raw):
            raise ValueError(
                "Could not extract a numeric computed_value from expression, "
                "script variables (result, computed_value, value, answer, output, "
                "total), trailing expression, or stdout."
            )
    finally:
        with contextlib.suppress(OSError):
            os.unlink(runner_path)
        with contextlib.suppress(OSError):
            os.unlink(outcome_path)

    confirmed = _evaluate_comparison(computed_raw, threshold_val, norm_comparison)
    route_branch = "CONFIRMED_INFOGRAPHIC" if confirmed else "BUSTED_ORIGIN_TRACE"

    return {
        "confirmed": confirmed,
        "computed_value": float(computed_raw),
        "expected_threshold": threshold_val,
        "comparison": norm_comparison,
        "route_branch": route_branch,
        "verdict": "CONFIRMED" if confirmed else "BUSTED",
        "claim": claim,
        "stdout": stdout_text.strip(),
    }
