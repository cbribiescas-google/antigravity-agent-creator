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

"""Headless HTML5 Canvas arcade game validator tool for Scenario #2."""

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

__all__ = ["validate_html5_game"]

_EXECUTABLE_SCRIPT_TYPES = frozenset(
    {
        "",
        "module",
        "text/javascript",
        "application/javascript",
        "ecmascript",
        "text/ecmascript",
        "application/ecmascript",
    }
)

_KEYBOARD_EVENT_NAMES = frozenset({"onkeydown", "onkeyup", "onkeypress"})
_KEYBOARD_JS_RE = re.compile(
    r"\b(?:keydown|keyup|keypress|onkeydown|onkeyup|onkeypress)\b",
    re.IGNORECASE,
)
_GAME_LOOP_JS_RE = re.compile(r"\brequestAnimationFrame\b")
_DOCTYPE_HTML_RE = re.compile(r"^doctype\s+html\b", re.IGNORECASE)
_ESM_STATEMENT_RE = re.compile(
    r"(?:^|[;\n\r])\s*(?:import(?:\s+[\w*{$\"']|\s*\()|export\s+(?:default\b|const\b|let\b|var\b|function\b|class\b|async\b|\*|\{))"
)

_REGEX_PRECEDING_KEYWORDS = frozenset(
    {
        "return",
        "typeof",
        "void",
        "delete",
        "throw",
        "new",
        "in",
        "of",
        "instanceof",
        "case",
        "yield",
        "await",
        "else",
        "do",
    }
)

_MATCHING_CLOSERS = {"(": ")", "[": "]", "{": "}"}
_CLOSING_DELIMS = frozenset({")", "]", "}"})


@dataclass
class _ScriptBlock:
    """Extracted `<script>` element details from an HTML document."""

    script_type: str
    has_src: bool
    code: str
    is_closed: bool


class _GameHTMLParser(HTMLParser):
    """HTML5 structural and inline `<script>` extractor preserving raw script text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.declarations: list[str] = []
        self.start_tags: set[str] = set()
        self.end_tags: set[str] = set()
        self.canvas_open_count: int = 0
        self.canvas_close_count: int = 0
        self.event_attr_names: set[str] = set()
        self.event_attr_values: list[str] = []
        self.script_blocks: list[_ScriptBlock] = []

        self._in_script: bool = False
        self._current_script_type: str = ""
        self._current_script_has_src: bool = False
        self._script_buf: list[str] = []

    def handle_decl(self, decl: str) -> None:
        self.declarations.append(decl)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        self.start_tags.add(tag_lower)
        if tag_lower == "canvas":
            self.canvas_open_count += 1

        attrs_dict: dict[str, str] = {}
        for attr_name, attr_val in attrs:
            name_lower = attr_name.lower()
            val_str = attr_val or ""
            attrs_dict[name_lower] = val_str
            if name_lower.startswith("on"):
                self.event_attr_names.add(name_lower)
                if val_str:
                    self.event_attr_values.append(val_str)

        if tag_lower == "script":
            self._in_script = True
            self._current_script_type = attrs_dict.get("type", "").strip().lower()
            self._current_script_has_src = "src" in attrs_dict
            self._script_buf = []

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        # Record only the opening tag so self-closing `<canvas />` does not satisfy
        # the requirement for an explicit closing `</canvas>` tag.
        self.handle_starttag(tag, attrs)
        if tag.lower() == "script" and self._in_script:
            self._in_script = False
            self.script_blocks.append(
                _ScriptBlock(
                    script_type=self._current_script_type,
                    has_src=self._current_script_has_src,
                    code="".join(self._script_buf),
                    is_closed=True,
                )
            )
            self._script_buf = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        self.end_tags.add(tag_lower)
        if tag_lower == "canvas":
            self.canvas_close_count += 1
        if tag_lower == "script" and self._in_script:
            self._in_script = False
            self.script_blocks.append(
                _ScriptBlock(
                    script_type=self._current_script_type,
                    has_src=self._current_script_has_src,
                    code="".join(self._script_buf),
                    is_closed=True,
                )
            )
            self._script_buf = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_buf.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._in_script:
            self._script_buf.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._in_script:
            self._script_buf.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        if self._in_script:
            self._script_buf.append(f"<!--{data}-->")

    def finalize(self) -> None:
        """Flushes parser buffers and records any unclosed `<script>` block."""
        self.close()
        if self._in_script:
            self._in_script = False
            self.script_blocks.append(
                _ScriptBlock(
                    script_type=self._current_script_type,
                    has_src=self._current_script_has_src,
                    code="".join(self._script_buf),
                    is_closed=False,
                )
            )
            self._script_buf = []


def _resolve_sandbox_dir() -> str:
    """Resolves the active sandbox directory dynamically at call time."""
    return os.environ.get("ANTIGRAVITY_WORKSPACE_DIR") or os.path.join(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness"),
        "sandbox",
    )


def _resolve_game_file_path(file_path: str) -> tuple[str, bool]:
    """Resolves `file_path` against `sandbox_dir` when relative.

    Returns:
        A tuple of `(resolved_path, is_empty_input)`.
    """
    sandbox_dir = _resolve_sandbox_dir()
    cleaned = str(file_path).strip()
    if cleaned.startswith("file://"):
        cleaned = cleaned[len("file://") :]
    if not cleaned:
        return os.path.abspath(sandbox_dir), True
    if os.path.isabs(cleaned):
        return os.path.abspath(cleaned), False
    return os.path.abspath(os.path.join(sandbox_dir, cleaned)), False


def _scan_js_comments_and_delimiters(
    code: str, script_index: int
) -> tuple[str, list[str]]:
    """Strips JS comments while checking balanced `()`, `{}`, `[]` and literals.

    Ignores delimiters inside single/double-quoted strings, template literal text
    segments (while validating expressions inside `${...}`), line/block comments,
    and regular expression literals.

    Args:
        code: Raw JavaScript source string.
        script_index: 1-based inline `<script>` index for error messages.

    Returns:
        Tuple `(code_without_comments, delimiter_errors)`.
    """
    out: list[str] = []
    errors: list[str] = []
    # Stack items: (expected_closer, open_line, resumes_template_literal)
    stack: list[tuple[str, int, bool]] = []

    n = len(code)
    i = 0
    line = 1
    in_template = False
    template_open_line = 1
    prev_token_kind = "start"  # "start" | "op" | "value"

    while i < n:
        ch = code[i]

        if in_template:
            if ch == "\\":
                out.append(ch)
                if i + 1 < n:
                    nxt = code[i + 1]
                    out.append(nxt)
                    if nxt == "\n":
                        line += 1
                    i += 2
                else:
                    i += 1
                continue
            if ch == "`":
                out.append(ch)
                in_template = False
                prev_token_kind = "value"
                i += 1
                continue
            if ch == "$" and i + 1 < n and code[i + 1] == "{":
                out.append("${")
                stack.append(("}", line, True))
                in_template = False
                prev_token_kind = "op"
                i += 2
                continue
            out.append(ch)
            if ch == "\n":
                line += 1
            i += 1
            continue

        # Whitespace
        if ch in " \t\r\f\v":
            out.append(ch)
            i += 1
            continue
        if ch == "\n":
            out.append("\n")
            line += 1
            i += 1
            continue

        # Single-line comment //
        if ch == "/" and i + 1 < n and code[i + 1] == "/":
            out.append("  ")
            i += 2
            while i < n and code[i] != "\n":
                out.append(" ")
                i += 1
            continue

        # Multi-line comment /* ... */
        if ch == "/" and i + 1 < n and code[i + 1] == "*":
            comment_start_line = line
            out.append("  ")
            i += 2
            closed = False
            while i < n:
                if code[i] == "*" and i + 1 < n and code[i + 1] == "/":
                    out.append("  ")
                    i += 2
                    closed = True
                    break
                if code[i] == "\n":
                    out.append("\n")
                    line += 1
                else:
                    out.append(" ")
                i += 1
            if not closed:
                errors.append(
                    f"inline_script_and_js_syntax: Unclosed block comment '/*' in inline <script #{script_index}> starting at line {comment_start_line}."
                )
                break
            continue

        # Single or double quoted string literal
        if ch in ("'", '"'):
            quote = ch
            str_start_line = line
            out.append(ch)
            i += 1
            closed = False
            while i < n:
                c = code[i]
                if c == "\\":
                    out.append(c)
                    if i + 1 < n:
                        nxt = code[i + 1]
                        out.append(nxt)
                        if nxt == "\n":
                            line += 1
                        elif nxt == "\r" and i + 2 < n and code[i + 2] == "\n":
                            out.append("\n")
                            line += 1
                            i += 1
                        i += 2
                    else:
                        i += 1
                    continue
                if c == quote:
                    out.append(c)
                    i += 1
                    closed = True
                    break
                if c in ("\n", "\r"):
                    errors.append(
                        f"inline_script_and_js_syntax: Unterminated string literal ({quote}) in inline <script #{script_index}> at line {str_start_line}."
                    )
                    break
                out.append(c)
                i += 1
            if not closed and not errors:
                errors.append(
                    f"inline_script_and_js_syntax: Unterminated string literal ({quote}) in inline <script #{script_index}> starting at line {str_start_line}."
                )
            prev_token_kind = "value"
            if errors:
                break
            continue

        # Template literal `...`
        if ch == "`":
            out.append(ch)
            in_template = True
            template_open_line = line
            i += 1
            continue

        # Regex literal /.../flags vs division operator /
        if ch == "/" and prev_token_kind in ("start", "op"):
            regex_start_line = line
            out.append(ch)
            i += 1
            in_char_class = False
            closed = False
            while i < n:
                c = code[i]
                if c == "\\":
                    out.append(c)
                    if i + 1 < n and code[i + 1] not in ("\n", "\r"):
                        out.append(code[i + 1])
                        i += 2
                        continue
                    i += 1
                    continue
                if c in ("\n", "\r"):
                    break
                if c == "[" and not in_char_class:
                    in_char_class = True
                    out.append(c)
                    i += 1
                    continue
                if c == "]" and in_char_class:
                    in_char_class = False
                    out.append(c)
                    i += 1
                    continue
                if c == "/" and not in_char_class:
                    out.append(c)
                    i += 1
                    while i < n and (code[i].isalpha() or code[i] == "$"):
                        out.append(code[i])
                        i += 1
                    closed = True
                    break
                out.append(c)
                i += 1
            if not closed:
                errors.append(
                    f"inline_script_and_js_syntax: Unterminated regular expression literal in inline <script #{script_index}> at line {regex_start_line}."
                )
                break
            prev_token_kind = "value"
            continue

        # Opening delimiters
        if ch in _MATCHING_CLOSERS:
            out.append(ch)
            stack.append((_MATCHING_CLOSERS[ch], line, False))
            prev_token_kind = "op"
            i += 1
            continue

        # Closing delimiters
        if ch in _CLOSING_DELIMS:
            out.append(ch)
            if not stack:
                errors.append(
                    f"inline_script_and_js_syntax: Unexpected closing delimiter '{ch}' in inline <script #{script_index}> at line {line}."
                )
                break
            expected, open_line, resumes_template = stack.pop()
            if ch != expected:
                errors.append(
                    f"inline_script_and_js_syntax: Mismatched delimiter in inline <script #{script_index}> at line {line}: expected '{expected}' (opened at line {open_line}), found '{ch}'."
                )
                break
            if resumes_template:
                in_template = True
            else:
                prev_token_kind = "value"
            i += 1
            continue

        # Identifiers / keywords
        if ch.isalpha() or ch in ("_", "$"):
            start = i
            while i < n and (code[i].isalnum() or code[i] in ("_", "$")):
                i += 1
            ident = code[start:i]
            out.append(ident)
            # Property access `.return` is a property name, not a keyword.
            is_prop = start > 0 and code[start - 1] == "."
            if not is_prop and ident in _REGEX_PRECEDING_KEYWORDS:
                prev_token_kind = "op"
            else:
                prev_token_kind = "value"
            continue

        # Numeric literals
        if ch.isdigit():
            start = i
            while i < n and (code[i].isalnum() or code[i] in (".", "_")):
                i += 1
            out.append(code[start:i])
            prev_token_kind = "value"
            continue

        # ++ and -- preserve postfix value vs prefix operator context
        if ch in ("+", "-") and i + 1 < n and code[i + 1] == ch:
            out.append(ch * 2)
            if prev_token_kind != "value":
                prev_token_kind = "op"
            i += 2
            continue

        # Other punctuation / operators
        out.append(ch)
        prev_token_kind = "op"
        i += 1

    if not errors:
        if in_template:
            errors.append(
                f"inline_script_and_js_syntax: Unterminated template literal (`) in inline <script #{script_index}> starting at line {template_open_line}."
            )
        elif stack:
            expected, open_line, _ = stack[-1]
            opener = next(k for k, v in _MATCHING_CLOSERS.items() if v == expected)
            errors.append(
                f"inline_script_and_js_syntax: Unclosed delimiter '{opener}' in inline <script #{script_index}> opened at line {open_line} (expected '{expected}')."
            )

    return "".join(out), errors


def _format_node_syntax_error(stderr: str, tmp_js_path: str, script_index: int) -> str:
    """Formats `node --check` stderr into a concise, actionable single-line error."""
    cleaned = stderr.replace(tmp_js_path, f"<script #{script_index}>")
    kept_lines: list[str] = []
    line_num_hint = ""

    for raw_line in cleaned.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("at ") or stripped.startswith("Node.js v"):
            continue
        match_loc = re.match(rf"^<script #{script_index}>:(\d+)", stripped)
        if match_loc:
            line_num_hint = f"line {match_loc.group(1)}"
            continue
        if set(stripped) == {"^"}:
            continue
        kept_lines.append(stripped)

    syntax_line = next(
        (ln for ln in kept_lines if "SyntaxError" in ln or "Error:" in ln),
        kept_lines[-1] if kept_lines else "Invalid JavaScript syntax",
    )
    snippet_candidates = [ln for ln in kept_lines if ln != syntax_line]
    snippet_part = f" near `{snippet_candidates[0][:100]}`" if snippet_candidates else ""
    loc_part = f" ({line_num_hint})" if line_num_hint else ""
    return (
        f"inline_script_and_js_syntax: JavaScript syntax error in inline "
        f"<script #{script_index}>{loc_part}: {syntax_line}{snippet_part}"
    )


def _validate_js_syntax(
    code: str,
    code_without_comments: str,
    is_module: bool,
    script_index: int,
    fallback_errors: list[str],
) -> list[str]:
    """Validates inline JS syntax via `node --check`, with Python delimiter fallback."""
    node_bin = shutil.which("node")
    if not node_bin:
        return fallback_errors

    use_mjs = is_module or bool(_ESM_STATEMENT_RE.search(code_without_comments))
    suffix = ".mjs" if use_mjs else ".js"
    tmp_js_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            encoding="utf-8",
            delete=False,
        ) as tmp_file:
            tmp_file.write(code)
            tmp_js_path = tmp_file.name

        proc = subprocess.run(
            [node_bin, "--check", tmp_js_path],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0:
            err_output = proc.stderr or proc.stdout or "JavaScript syntax check failed."
            return [_format_node_syntax_error(err_output, tmp_js_path, script_index)]
        return []
    except (OSError, subprocess.SubprocessError):
        return fallback_errors
    finally:
        if tmp_js_path and os.path.exists(tmp_js_path):
            with contextlib.suppress(OSError):
                os.unlink(tmp_js_path)


def validate_html5_game(file_path: str) -> dict[str, Any]:
    """Validates a single-file HTML5 Canvas arcade game headlessly for self-healing loops.

    Checks that the target file exists, has valid HTML5 document structure,
    includes a `<canvas>...</canvas>` rendering surface, embeds syntactically valid
    inline JavaScript (checked with `node --check` when available, or a lexical
    balanced-delimiter fallback), wires keyboard controls, and runs an animation
    game loop via `requestAnimationFrame`.

    Args:
        file_path: Path to the HTML5 game file. Relative paths are resolved inside
            the active sandbox directory (`ANTIGRAVITY_WORKSPACE_DIR` or
            `<ANTIGRAVITY_BASE_DIR>/sandbox`).

    Returns:
        A dictionary containing:
            - `passed` (`bool`): `True` if all five validation checks pass with zero errors.
            - `errors` (`list[str]`): Actionable diagnostic messages for any failed checks.
            - `byte_size` (`int`): Size of the HTML file in bytes (`0` if missing).
            - `file_path` (`str`): Absolute resolved path to the inspected HTML file.
            - `checks` (`dict[str, bool]`): Per-check pass/fail status map for
              `html5_structure`, `canvas_element`, `inline_script_and_js_syntax`,
              `keyboard_controls`, and `game_loop` (empty dict if file is missing).
    """
    resolved_path, is_empty_input = _resolve_game_file_path(file_path)
    if is_empty_input or not os.path.isfile(resolved_path):
        return {
            "passed": False,
            "errors": [f"File not found: {resolved_path}"],
            "byte_size": 0,
            "file_path": resolved_path,
            "checks": {},
        }

    try:
        with open(resolved_path, "rb") as fh:
            raw_bytes = fh.read()
    except OSError:
        return {
            "passed": False,
            "errors": [f"File not found: {resolved_path}"],
            "byte_size": 0,
            "file_path": resolved_path,
            "checks": {},
        }

    byte_size = len(raw_bytes)
    html_text = raw_bytes.decode("utf-8", errors="replace")

    parser = _GameHTMLParser()
    parser.feed(html_text)
    parser.finalize()

    errors: list[str] = []
    checks: dict[str, bool] = {}

    # 1. html5_structure
    if not html_text.strip():
        errors.append(
            "html5_structure: File is empty; provide a complete HTML5 document with <!DOCTYPE html>, <html>, <body>, and </html>."
        )
        checks["html5_structure"] = False
    else:
        has_doctype = any(
            bool(_DOCTYPE_HTML_RE.match(decl.strip())) for decl in parser.declarations
        )
        has_html_open = "html" in parser.start_tags
        has_html_close = "html" in parser.end_tags
        has_body_open = "body" in parser.start_tags

        missing_structure: list[str] = []
        if not (has_doctype or has_html_open):
            missing_structure.append("<!DOCTYPE html> or <html>")
        if not has_body_open:
            missing_structure.append("<body>")
        if not has_html_close:
            missing_structure.append("</html>")

        if missing_structure:
            errors.append(
                "html5_structure: Missing required HTML5 document structure: "
                + ", ".join(missing_structure)
                + "."
            )
            checks["html5_structure"] = False
        else:
            checks["html5_structure"] = True

    # 2. canvas_element
    if parser.canvas_open_count == 0 and parser.canvas_close_count == 0:
        errors.append(
            "canvas_element: Missing <canvas>...</canvas> element required to render the game."
        )
        checks["canvas_element"] = False
    elif parser.canvas_open_count == 0:
        errors.append(
            "canvas_element: Found closing </canvas> tag without an opening <canvas> tag."
        )
        checks["canvas_element"] = False
    elif parser.canvas_close_count < parser.canvas_open_count:
        errors.append(
            "canvas_element: Missing closing </canvas> tag for <canvas> element."
        )
        checks["canvas_element"] = False
    else:
        checks["canvas_element"] = True

    # 3. inline_script_and_js_syntax
    script_errors: list[str] = []
    inline_js_blocks = [
        blk
        for blk in parser.script_blocks
        if not blk.has_src and blk.script_type in _EXECUTABLE_SCRIPT_TYPES
    ]
    stripped_js_chunks: list[str] = []

    non_empty_inline_scripts = [
        blk for blk in inline_js_blocks if blk.code.strip()
    ]
    for blk in parser.script_blocks:
        if not blk.is_closed:
            script_errors.append(
                "inline_script_and_js_syntax: Unclosed <script> tag; add a matching closing </script> tag."
            )

    if not non_empty_inline_scripts:
        script_errors.append(
            "inline_script_and_js_syntax: No non-empty inline <script>...</script> block found; embed the game JavaScript inline."
        )
    else:
        for idx, blk in enumerate(non_empty_inline_scripts, start=1):
            js_no_comments, fallback_errs = _scan_js_comments_and_delimiters(
                blk.code, idx
            )
            stripped_js_chunks.append(js_no_comments)
            if blk.is_closed:
                js_errs = _validate_js_syntax(
                    code=blk.code,
                    code_without_comments=js_no_comments,
                    is_module=(blk.script_type == "module"),
                    script_index=idx,
                    fallback_errors=fallback_errs,
                )
                script_errors.extend(js_errs)

    if script_errors:
        errors.extend(script_errors)
        checks["inline_script_and_js_syntax"] = False
    else:
        checks["inline_script_and_js_syntax"] = True

    combined_js_no_comments = "\n".join(stripped_js_chunks)
    combined_attr_js = "\n".join(parser.event_attr_values)

    # 4. keyboard_controls
    has_keyboard_attr = bool(parser.event_attr_names & _KEYBOARD_EVENT_NAMES)
    has_keyboard_js = bool(
        _KEYBOARD_JS_RE.search(combined_js_no_comments)
        or _KEYBOARD_JS_RE.search(combined_attr_js)
    )
    if has_keyboard_attr or has_keyboard_js:
        checks["keyboard_controls"] = True
    else:
        errors.append(
            "keyboard_controls: Missing keyboard event handling; add a 'keydown'/'keyup' listener (e.g. window.addEventListener('keydown', ...))."
        )
        checks["keyboard_controls"] = False

    # 5. game_loop
    has_game_loop = bool(
        _GAME_LOOP_JS_RE.search(combined_js_no_comments)
        or _GAME_LOOP_JS_RE.search(combined_attr_js)
    )
    if has_game_loop:
        checks["game_loop"] = True
    else:
        errors.append(
            "game_loop: Missing requestAnimationFrame game loop; call requestAnimationFrame(...) to drive continuous Canvas updates."
        )
        checks["game_loop"] = False

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "byte_size": byte_size,
        "file_path": resolved_path,
        "checks": checks,
    }
