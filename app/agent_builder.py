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

"""Antigravity Agent Builder & Dynamic Tool Synthesis Engine.

Provides tools mounted onto the root **Antigravity Agent** so it can:
1. Synthesize, AST-validate, persist, and hot-register brand-new Python tools
   at runtime (`create_custom_tool`).
2. Compile and register real Antigravity Custom Agents with Markdown `.md`
   definitions (YAML frontmatter + System Instructions + DAG Architecture) and
   machine-loadable JSON registry specs (`build_custom_agent`).
3. Discover all built-in harness tools, scenario tools, dynamic tools, and
   registered custom agents (`list_registered_agents_and_tools`).

Also exposes Gateway helper APIs (`get_all_custom_tools_map`,
`list_agents_catalog`, and `build_local_agent_config`) so the Single API
Gateway can execute both the root `antigravity` builder agent and any created
custom DAG agent with stateful conversation persistence and full telemetry.
"""

import ast
import importlib.util
import inspect
import json
import logging
import os
import pathlib
import re
import sys
import threading
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

import google.auth
import google.auth.transport.requests
from google.antigravity import LocalAgentConfig, TemplatedSystemInstructions, types
from google.antigravity.connections.local.local_connection import callable_to_tool_proto
from google.antigravity.hooks import policy

logger = logging.getLogger(__name__)

_APP_PKG_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_PKG_DIR.parent

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MARKDOWN_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:python|py)?\s*\n(.*?)\n\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)

# Root agent aliases recognized by the Gateway and ADK runtime.
ROOT_AGENT_ALIASES: frozenset[str] = frozenset(
    {"antigravity", "gemini_antigravity_demo", "gemini-antigravity-demo"}
)
_RESERVED_AGENT_IDS: frozenset[str] = frozenset(
    {*ROOT_AGENT_ALIASES, "registry"}
)

# Core builder tool names that dynamic tools may not overwrite.
_PROTECTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "create_custom_tool",
        "build_custom_agent",
        "list_registered_agents_and_tools",
    }
)

# Dangerous modules and calls blocked inside dynamically synthesized tools.
_BLOCKED_IMPORT_ROOTS: frozenset[str] = frozenset(
    {
        "subprocess",
        "pty",
        "ctypes",
        "multiprocessing",
        "pickle",
        "marshal",
        "shelve",
        "socketserver",
        "SocketServer",
        "webbrowser",
    }
)
_BLOCKED_BUILTIN_CALLS: frozenset[str] = frozenset(
    {"eval", "exec", "compile", "__import__", "breakpoint"}
)
_BLOCKED_OS_ATTRS: frozenset[str] = frozenset(
    {
        "system",
        "popen",
        "fork",
        "forkpty",
        "kill",
        "killpg",
        "remove",
        "unlink",
        "rmdir",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "posix_spawn",
        "posix_spawnp",
    }
)

# Canonical built-in Antigravity harness tool metadata and enum mappings.
BUILTIN_TOOLS_METADATA: list[dict[str, str]] = [
    {
        "name": "view_file",
        "description": (
            "Read text, code, or image files (including multimodal vision "
            "inspection of generated drafts) inside the workspace."
        ),
        "source": "builtin",
        "category": "filesystem",
    },
    {
        "name": "create_file",
        "description": (
            "Create or overwrite files (code, HTML5 games, Markdown reports, "
            "JSON, scripts) inside the sandbox workspace."
        ),
        "source": "builtin",
        "category": "filesystem",
    },
    {
        "name": "edit_file",
        "description": "Perform targeted search-and-replace edits on existing workspace files.",
        "source": "builtin",
        "category": "filesystem",
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories inside the sandbox workspace.",
        "source": "builtin",
        "category": "filesystem",
    },
    {
        "name": "find_file",
        "description": "Search for files by glob or filename pattern inside the workspace.",
        "source": "builtin",
        "category": "filesystem",
    },
    {
        "name": "search_directory",
        "description": "Grep/regex search across file contents inside the sandbox workspace.",
        "source": "builtin",
        "category": "filesystem",
    },
    {
        "name": "run_command",
        "description": (
            "Execute bash commands, Python scripts, linters, or computations "
            "inside the sandbox environment."
        ),
        "source": "builtin",
        "category": "execution",
    },
    {
        "name": "search_web",
        "description": "Search the live web for facts, references, menus, or research.",
        "source": "builtin",
        "category": "web",
    },
    {
        "name": "read_url_content",
        "description": "Fetch and read full content from a web URL.",
        "source": "builtin",
        "category": "web",
    },
    {
        "name": "generate_image",
        "description": (
            "Generate visual illustrations, posters, comic panels, box art, "
            "infographics, or scene concept art."
        ),
        "source": "builtin",
        "category": "media",
    },
    {
        "name": "ask_question",
        "description": (
            "Present structured interactive choices/questions to the human "
            "player or user (Human-in-the-Loop)."
        ),
        "source": "builtin",
        "category": "interaction",
    },
    {
        "name": "start_subagent",
        "description": (
            "Spawn and delegate specialized parallel or sequential tasks to "
            "declared or autonomous subagents."
        ),
        "source": "builtin",
        "category": "orchestration",
    },
    {
        "name": "invoke_subagent",
        "description": (
            "Alias for start_subagent — delegates parallel or specialized "
            "sub-tasks to subagents in multi-agent DAG topologies."
        ),
        "source": "builtin",
        "category": "orchestration",
    },
]

_BUILTIN_NAME_TO_ENUM: dict[str, types.BuiltinTools] = {
    "view_file": types.BuiltinTools.VIEW_FILE,
    "read_file": types.BuiltinTools.VIEW_FILE,
    "create_file": types.BuiltinTools.CREATE_FILE,
    "write_file": types.BuiltinTools.CREATE_FILE,
    "write_to_file": types.BuiltinTools.CREATE_FILE,
    "edit_file": types.BuiltinTools.EDIT_FILE,
    "file_edit": types.BuiltinTools.EDIT_FILE,
    "list_directory": types.BuiltinTools.LIST_DIR,
    "list_dir": types.BuiltinTools.LIST_DIR,
    "find_file": types.BuiltinTools.FIND_FILE,
    "find": types.BuiltinTools.FIND_FILE,
    "search_directory": types.BuiltinTools.SEARCH_DIR,
    "search_dir": types.BuiltinTools.SEARCH_DIR,
    "grep_search": types.BuiltinTools.SEARCH_DIR,
    "run_command": types.BuiltinTools.RUN_COMMAND,
    "search_web": types.BuiltinTools.SEARCH_WEB,
    "read_url_content": types.BuiltinTools.READ_URL_CONTENT,
    "generate_image": types.BuiltinTools.GENERATE_IMAGE,
    "ask_question": types.BuiltinTools.ASK_QUESTION,
    "start_subagent": types.BuiltinTools.START_SUBAGENT,
    "invoke_subagent": types.BuiltinTools.START_SUBAGENT,
    "run_workflow": types.BuiltinTools.START_SUBAGENT,
    "finish": types.BuiltinTools.FINISH,
}

_BUILTIN_ALIAS_NORMALIZATION: dict[str, str] = {
    "read_file": "view_file",
    "write_file": "create_file",
    "write_to_file": "create_file",
    "file_edit": "edit_file",
    "list_dir": "list_directory",
    "find": "find_file",
    "search_dir": "search_directory",
    "grep_search": "search_directory",
    "run_workflow": "invoke_subagent",
}

_WORKSPACE_HELPER_BUILTINS: tuple[types.BuiltinTools, ...] = (
    types.BuiltinTools.VIEW_FILE,
    types.BuiltinTools.LIST_DIR,
    types.BuiltinTools.FIND_FILE,
    types.BuiltinTools.SEARCH_DIR,
)

# Live in-memory registry of dynamically created tools: tool_name -> callable.
_DYNAMIC_TOOLS_REGISTRY: dict[str, Callable[..., Any]] = {}

# Singleton state for the local GCE metadata token bridge (resolves RAPT-backed
# `impersonated_service_account` credentials via Python `google.auth` for the Go
# `localharness` subprocess, which does not parse `rapt_token` directly).
_METADATA_SERVER_LOCK = threading.Lock()
_METADATA_SERVER_PORT: int | None = None
_METADATA_CREDS_LOCK = threading.Lock()
_METADATA_CACHED_CREDS: Any = None
_METADATA_CACHED_SOURCE: str = ""
_CLOUD_PLATFORM_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class AgentNotFoundError(KeyError, ValueError):
    """Raised when a requested `agent_id` is not registered."""


def _resolve_local_credentials_file() -> str:
    """Finds the best local ADC/SA JSON file for `google.auth` token minting."""
    candidates = [
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip(),
        os.path.expanduser("~/.config/gcloud/gemini-enterprise-admin-key.json"),
        os.path.expanduser("~/.config/gcloud/application_default_credentials.json"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def _get_metadata_access_token() -> tuple[str, int]:
    """Refreshes and returns `(access_token, expires_in_seconds)` thread-safely."""
    global _METADATA_CACHED_CREDS, _METADATA_CACHED_SOURCE

    with _METADATA_CREDS_LOCK:
        creds_file = _resolve_local_credentials_file()
        if _METADATA_CACHED_CREDS is None or creds_file != _METADATA_CACHED_SOURCE:
            if creds_file:
                _METADATA_CACHED_CREDS, _ = google.auth.load_credentials_from_file(
                    creds_file,
                    scopes=_CLOUD_PLATFORM_SCOPES,
                )
            else:
                _METADATA_CACHED_CREDS, _ = google.auth.default(
                    scopes=_CLOUD_PLATFORM_SCOPES,
                )
            _METADATA_CACHED_SOURCE = creds_file

        creds = _METADATA_CACHED_CREDS
        needs_refresh = not getattr(creds, "valid", False) or not getattr(
            creds, "token", None
        )
        expiry = getattr(creds, "expiry", None)
        if not needs_refresh and expiry is not None:
            now_utc = (
                datetime.now(UTC)
                if expiry.tzinfo is not None
                else datetime.utcnow()
            )
            if (expiry - now_utc).total_seconds() < 120:
                needs_refresh = True

        if needs_refresh:
            creds.refresh(google.auth.transport.requests.Request())

        token = str(creds.token)
        expires_in = 3500
        expiry = getattr(creds, "expiry", None)
        if expiry is not None:
            now_utc = (
                datetime.now(UTC)
                if expiry.tzinfo is not None
                else datetime.utcnow()
            )
            remaining = int((expiry - now_utc).total_seconds())
            if remaining > 60:
                expires_in = remaining
        return token, expires_in


class _LocalMetadataHandler(BaseHTTPRequestHandler):
    """Minimal GCE Metadata v1 server bridging Python `google.auth` to Go `localharness`."""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(
        self, status: int, body: bytes, content_type: str = "text/plain"
    ) -> None:
        self.send_response(status)
        self.send_header("Metadata-Flavor", "Google")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb")
        sa_email = (
            f"gemini-enterprise-admin@{project}.iam.gserviceaccount.com"
        )

        if path == "/" or path == "/computeMetadata/v1":
            self._send(200, b"computeMetadata/\n")
            return
        if path == "/computeMetadata/v1/project/project-id":
            self._send(200, project.encode("utf-8"))
            return
        if path == "/computeMetadata/v1/project/numeric-project-id":
            self._send(200, b"0")
            return
        if path == "/computeMetadata/v1/instance/service-accounts":
            self._send(200, f"default/\n{sa_email}/\n".encode())
            return
        if path in (
            "/computeMetadata/v1/instance/service-accounts/default",
            f"/computeMetadata/v1/instance/service-accounts/{sa_email}",
        ):
            if query.get("recursive", ["false"])[0].lower() == "true":
                payload = json.dumps(
                    {
                        "aliases": ["default"],
                        "email": sa_email,
                        "scopes": _CLOUD_PLATFORM_SCOPES,
                    }
                ).encode("utf-8")
                self._send(200, payload, content_type="application/json")
            else:
                self._send(200, b"aliases\nemail\nidentity\nscopes\ntoken\n")
            return
        if path.endswith("/email"):
            self._send(200, sa_email.encode("utf-8"))
            return
        if path.endswith("/scopes"):
            self._send(200, (_CLOUD_PLATFORM_SCOPES[0] + "\n").encode("utf-8"))
            return
        if path.endswith("/aliases"):
            self._send(200, b"default\n")
            return
        if path.endswith("/token"):
            try:
                token, expires_in = _get_metadata_access_token()
                payload = json.dumps(
                    {
                        "access_token": token,
                        "expires_in": expires_in,
                        "token_type": "Bearer",
                    }
                ).encode("utf-8")
                self._send(200, payload, content_type="application/json")
            except Exception as exc:
                err_payload = json.dumps({"error": str(exc)}).encode("utf-8")
                self._send(500, err_payload, content_type="application/json")
            return

        self._send(404, b"Not Found")


def ensure_localharness_env() -> dict[str, str] | None:
    """Returns subprocess `env` overrides bridging Python `google.auth` to Go `localharness`.

    On developer workstations where ADC is an `impersonated_service_account`
    backed by a `rapt_token`, Go's `oauth2/google` inside `localharness` fails
    with `invalid_grant (invalid_rapt)`. Running a loopback GCE metadata token
    endpoint backed by Python's `google.auth` resolves tokens transparently
    while leaving Cloud Run / Agent Engine managed environments untouched.
    """
    global _METADATA_SERVER_PORT

    # On Cloud Run or Vertex AI Agent Runtime, native GCE metadata is already live.
    if (
        os.environ.get("K_SERVICE")
        or os.environ.get("CLOUD_RUN_JOB")
        or os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")
    ):
        return None
    if not _resolve_local_credentials_file():
        return None

    with _METADATA_SERVER_LOCK:
        if _METADATA_SERVER_PORT is None:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalMetadataHandler)
            _METADATA_SERVER_PORT = int(server.server_address[1])
            thread = threading.Thread(
                target=server.serve_forever,
                name="antigravity-local-metadata-bridge",
                daemon=True,
            )
            thread.start()

    harness_home = os.path.join(_get_base_dir(), "home")
    os.makedirs(harness_home, exist_ok=True)
    return {
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "HOME": harness_home,
        "GCE_METADATA_HOST": f"127.0.0.1:{_METADATA_SERVER_PORT}",
    }


# ---------------------------------------------------------------------------
# Directory & Runtime Path Helpers
# ---------------------------------------------------------------------------


def _get_base_dir() -> str:
    return os.path.abspath(
        os.environ.get("ANTIGRAVITY_BASE_DIR", "/tmp/antigravity_harness")
    )


def _get_workspace_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_WORKSPACE_DIR",
            os.path.join(_get_base_dir(), "sandbox"),
        )
    )


def _get_trajectories_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_TRAJECTORIES_DIR",
            os.path.join(_get_base_dir(), "trajectories"),
        )
    )


def _get_app_data_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "ANTIGRAVITY_APP_DATA_DIR",
            os.path.join(_get_base_dir(), "app_data"),
        )
    )


def _get_dynamic_tools_dir() -> pathlib.Path:
    raw = os.environ.get("ANTIGRAVITY_DYNAMIC_TOOLS_DIR")
    path = pathlib.Path(raw).resolve() if raw else (_APP_PKG_DIR / "dynamic_tools")
    path.mkdir(parents=True, exist_ok=True)
    init_file = path / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            '"""Dynamically created Antigravity Python tools."""\n',
            encoding="utf-8",
        )
    return path


def _get_harness_dynamic_tools_dir() -> pathlib.Path:
    raw = os.environ.get("ANTIGRAVITY_HARNESS_DYNAMIC_TOOLS_DIR")
    path = (
        pathlib.Path(raw).resolve()
        if raw
        else pathlib.Path(os.path.join(_get_base_dir(), "dynamic_tools")).resolve()
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_agents_dir() -> pathlib.Path:
    raw = os.environ.get("ANTIGRAVITY_AGENTS_DIR")
    path = pathlib.Path(raw).resolve() if raw else (_PROJECT_ROOT / "agents")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_registry_dir() -> pathlib.Path:
    raw = os.environ.get("ANTIGRAVITY_AGENTS_REGISTRY_DIR")
    path = (
        pathlib.Path(raw).resolve()
        if raw
        else (_get_agents_dir() / "registry")
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_agent_id(agent_id: str) -> str:
    """Normalizes an `agent_id` to clean lowercase kebab-case (e.g. `trailer-director`)."""
    if not isinstance(agent_id, str):
        raise ValueError("agent_id must be a non-empty string.")
    normalized = re.sub(r"[^a-z0-9]+", "-", agent_id.strip().lower()).strip("-")
    if not normalized:
        raise ValueError(
            f"Invalid agent_id {agent_id!r}: must contain alphanumeric characters."
        )
    return normalized


# ---------------------------------------------------------------------------
# Dynamic Tool AST Validation, Compilation & Discovery
# ---------------------------------------------------------------------------


def _strip_code_fences(code: str) -> str:
    match = _MARKDOWN_CODE_FENCE_RE.match(code)
    if match:
        return match.group(1).strip()
    return code.strip()


def _infer_ast_annotation_name(default_node: ast.expr | None) -> str:
    """Infers a safe primitive annotation name when a parameter omits type hints."""
    if isinstance(default_node, ast.Constant):
        val = default_node.value
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, int):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            return "str"
    if isinstance(default_node, ast.List):
        return "list"
    if isinstance(default_node, ast.Dict):
        return "dict"
    return "str"


def _validate_and_prepare_tool_ast(
    tool_name: str, description: str, python_code: str
) -> str:
    """Parses `python_code`, enforces safety rules, and guarantees docstring + type hints."""
    cleaned_code = _strip_code_fences(python_code)
    if not cleaned_code:
        raise ValueError("python_code must not be empty.")

    try:
        tree = ast.parse(cleaned_code, filename=f"{tool_name}.py")
    except SyntaxError as exc:
        raise ValueError(
            f"Invalid Python syntax in tool '{tool_name}': {exc}"
        ) from exc

    # Security scan over AST imports and calls.
    os_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in _BLOCKED_IMPORT_ROOTS:
                    raise ValueError(
                        f"Import of module '{alias.name}' is blocked in dynamic tools."
                    )
                if root_mod == "os":
                    os_aliases.add(alias.asname or "os")
        elif isinstance(node, ast.ImportFrom):
            root_mod = (node.module or "").split(".")[0]
            if root_mod in _BLOCKED_IMPORT_ROOTS:
                raise ValueError(
                    f"Import from module '{node.module}' is blocked in dynamic tools."
                )
            if root_mod == "os":
                for alias in node.names:
                    if alias.name in _BLOCKED_OS_ATTRS:
                        raise ValueError(
                            f"Import of 'os.{alias.name}' is blocked in dynamic tools."
                        )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BLOCKED_BUILTIN_CALLS:
                raise ValueError(
                    f"Call to '{func.id}()' is blocked in dynamic tools."
                )
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in (os_aliases | {"os"})
                and func.attr in _BLOCKED_OS_ATTRS
            ):
                raise ValueError(
                    f"Call to 'os.{func.attr}()' is blocked in dynamic tools."
                )

    # Locate top-level function matching `tool_name`.
    target_fn: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for stmt in tree.body:
        if (
            isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            and stmt.name == tool_name
        ):
            target_fn = stmt
            break

    if target_fn is None:
        top_level_fns = [
            stmt.name
            for stmt in tree.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        raise ValueError(
            f"python_code must define a top-level function 'def {tool_name}(...)'. "
            f"Found top-level functions: {top_level_fns}"
        )

    ast_mutated = False

    # Inject docstring if missing or empty.
    existing_doc = ast.get_docstring(target_fn)
    if not existing_doc or not existing_doc.strip():
        doc_stmt = ast.Expr(value=ast.Constant(value=description.strip()))
        target_fn.body.insert(0, doc_stmt)
        ast_mutated = True

    # Ensure every positional/keyword argument has a type annotation so
    # google.genai FunctionDeclaration schema extraction never fails.
    pos_args = list(target_fn.args.posonlyargs) + list(target_fn.args.args)
    num_defaults = len(target_fn.args.defaults)
    default_offset = len(pos_args) - num_defaults
    for idx, arg in enumerate(pos_args):
        if arg.arg in ("self", "cls"):
            continue
        if arg.annotation is None:
            default_node = (
                target_fn.args.defaults[idx - default_offset]
                if idx >= default_offset
                else None
            )
            inferred = _infer_ast_annotation_name(default_node)
            arg.annotation = ast.Name(id=inferred, ctx=ast.Load())
            ast_mutated = True

    for idx, kwarg in enumerate(target_fn.args.kwonlyargs):
        if kwarg.annotation is None:
            kw_default = (
                target_fn.args.kw_defaults[idx]
                if idx < len(target_fn.args.kw_defaults)
                else None
            )
            inferred = _infer_ast_annotation_name(kw_default)
            kwarg.annotation = ast.Name(id=inferred, ctx=ast.Load())
            ast_mutated = True

    if ast_mutated:
        ast.fix_missing_locations(tree)
        return ast.unparse(tree) + "\n"
    return cleaned_code + "\n"


def _import_tool_from_file(
    tool_name: str, module_path: pathlib.Path
) -> Callable[..., Any]:
    """Dynamically imports `<tool_name>` from `module_path` and validates its schema."""
    module_qualname = f"app.dynamic_tools.{tool_name}"
    spec = importlib.util.spec_from_file_location(module_qualname, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to create module spec for dynamic tool '{tool_name}' at {module_path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_qualname] = module
    spec.loader.exec_module(module)

    fn = getattr(module, tool_name, None)
    if not callable(fn):
        raise ValueError(
            f"Module '{module_path}' did not expose a callable named '{tool_name}'."
        )

    # Validate that Antigravity's FunctionDeclaration converter accepts this callable.
    callable_to_tool_proto(fn)
    return fn


def _load_dynamic_tools_from_disk() -> dict[str, Callable[..., Any]]:
    """Loads any `.py` dynamic tools present on disk that aren't in memory yet."""
    loaded: dict[str, Callable[..., Any]] = {}
    search_dirs = [_get_dynamic_tools_dir(), _get_harness_dynamic_tools_dir()]
    seen_names: set[str] = set()

    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for py_file in sorted(directory.glob("*.py")):
            stem = py_file.stem
            if stem.startswith("_") or not _TOOL_NAME_RE.match(stem):
                continue
            if stem in seen_names:
                continue
            seen_names.add(stem)
            try:
                fn = _import_tool_from_file(stem, py_file)
                loaded[stem] = fn
                _DYNAMIC_TOOLS_REGISTRY[stem] = fn
            except Exception as exc:
                logger.warning(
                    "Skipping invalid dynamic tool file %s: %s", py_file, exc
                )

    # Include any in-memory tools registered during the current process lifetime
    # if they belong to the currently active dynamic tools directory.
    active_dir = _get_dynamic_tools_dir()
    for name, fn in list(_DYNAMIC_TOOLS_REGISTRY.items()):
        if name not in loaded and (active_dir / f"{name}.py").is_file():
            loaded[name] = fn
    return loaded


def _load_scenario_tools() -> tuple[dict[str, Callable[..., Any]], list[dict[str, Any]]]:
    """Gracefully imports `SCENARIO_TOOLS` and metadata from `app.scenario_tools`."""
    try:
        import app.scenario_tools as scenario_mod

        raw_tools = getattr(scenario_mod, "SCENARIO_TOOLS", None) or {}
        tools_dict: dict[str, Callable[..., Any]] = {
            str(k): v for k, v in raw_tools.items() if callable(v)
        }
        meta_fn = getattr(scenario_mod, "get_scenario_tool_metadata", None)
        if callable(meta_fn):
            metadata = list(meta_fn())
        else:
            metadata = [
                {
                    "name": name,
                    "description": (inspect.getdoc(fn) or "").splitlines()[0]
                    if inspect.getdoc(fn)
                    else f"Scenario tool {name}",
                    "module": getattr(fn, "__module__", "app.scenario_tools"),
                    "source": "scenario",
                }
                for name, fn in tools_dict.items()
            ]
        return tools_dict, metadata
    except Exception as exc:
        logger.debug("app.scenario_tools not yet available: %s", exc)
        return {}, []


def _get_core_generate_video() -> Callable[..., Any] | None:
    """Retrieves `generate_video` from `app.agent` without circular top-level imports."""
    agent_mod = sys.modules.get("app.agent")
    if agent_mod is not None and callable(getattr(agent_mod, "generate_video", None)):
        return agent_mod.generate_video
    try:
        from app import agent as imported_agent_mod

        fn = getattr(imported_agent_mod, "generate_video", None)
        return fn if callable(fn) else None
    except Exception:
        return None


def _refresh_root_sdk_config() -> None:
    """Refreshes `app.agent.sdk_config.tools` in-place when new dynamic tools are added."""
    agent_mod = sys.modules.get("app.agent")
    if agent_mod is None:
        return
    sdk_cfg = getattr(agent_mod, "sdk_config", None)
    if sdk_cfg is None:
        return

    tool_list: list[Callable[..., Any]] = []
    seen: set[str] = set()

    gen_vid = getattr(agent_mod, "generate_video", None)
    for fn in (
        gen_vid,
        create_custom_tool,
        build_custom_agent,
        list_registered_agents_and_tools,
        *_load_dynamic_tools_from_disk().values(),
    ):
        if callable(fn):
            fname = getattr(fn, "__name__", "")
            if fname and fname not in seen:
                seen.add(fname)
                tool_list.append(fn)

    sdk_cfg.tools = tool_list
    local_env = ensure_localharness_env()
    if local_env is not None and not sdk_cfg.env:
        sdk_cfg.env = local_env


# ---------------------------------------------------------------------------
# Root Antigravity Agent Builder Tools
# ---------------------------------------------------------------------------


def create_custom_tool(
    tool_name: str,
    description: str,
    python_code: str,
) -> dict[str, Any]:
    """Synthesizes, validates, persists, and live-registers a new custom Python tool.

    Use this tool when building a custom agent that requires a brand-new Python
    computation, parser, domain helper, or API utility not already in the tool
    catalog. Once created, `tool_name` can immediately be passed in `tool_names`
    to `build_custom_agent`!

    Args:
        tool_name: Valid snake_case Python function identifier (`^[a-z][a-z0-9_]*$`).
        description: Clear one-paragraph summary of what the tool computes and returns.
        python_code: Complete valid Python module code defining top-level
            `def <tool_name>(...)` with typed parameters (`str`, `int`, `float`,
            `bool`, `list`, `dict`) and returning a JSON-serializable dict or string.

    Returns:
        Dictionary confirming creation status, module paths, and parameter names.
    """
    clean_name = (tool_name or "").strip()
    if not _TOOL_NAME_RE.match(clean_name):
        raise ValueError(
            f"Invalid tool_name {tool_name!r}: must match '^[a-z][a-z0-9_]*$'."
        )
    if clean_name in _PROTECTED_TOOL_NAMES:
        raise ValueError(
            f"Cannot overwrite protected Agent Builder tool '{clean_name}'."
        )
    if clean_name in _BUILTIN_NAME_TO_ENUM:
        raise ValueError(
            f"Tool name '{clean_name}' collides with a built-in Antigravity harness tool."
        )

    clean_desc = (description or "").strip()
    if not clean_desc:
        raise ValueError("description must be a non-empty string.")

    final_source = _validate_and_prepare_tool_ast(
        clean_name, clean_desc, python_code
    )

    primary_dir = _get_dynamic_tools_dir()
    mirror_dir = _get_harness_dynamic_tools_dir()
    primary_path = primary_dir / f"{clean_name}.py"
    mirror_path = mirror_dir / f"{clean_name}.py"

    # Write to a staging path or validate execution before finalizing registration.
    primary_path.write_text(final_source, encoding="utf-8")
    try:
        fn = _import_tool_from_file(clean_name, primary_path)
    except Exception:
        if primary_path.exists():
            primary_path.unlink(missing_ok=True)
        raise

    if mirror_path.resolve() != primary_path.resolve():
        mirror_path.write_text(final_source, encoding="utf-8")

    _DYNAMIC_TOOLS_REGISTRY[clean_name] = fn
    _refresh_root_sdk_config()

    return {
        "status": "created",
        "tool_name": clean_name,
        "description": (inspect.getdoc(fn) or clean_desc).strip(),
        "module_path": str(primary_path),
        "mirror_path": str(mirror_path),
        "parameters": list(inspect.signature(fn).parameters.keys()),
    }


def _parse_json_list_param(raw: str | list[Any], param_name: str) -> list[dict[str, Any]]:
    """Parses a JSON list string (or Python list) of objects cleanly."""
    if isinstance(raw, list):
        parsed = raw
    elif isinstance(raw, str):
        stripped = raw.strip() or "[]"
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in {param_name}: {exc}"
            ) from exc
    else:
        raise ValueError(f"{param_name} must be a JSON array string.")

    if not isinstance(parsed, list):
        raise ValueError(f"{param_name} must decode to a JSON array (list).")
    return [item for item in parsed if isinstance(item, dict)]


def _normalize_dag_graph(
    dag_topology: str,
    raw_nodes: list[dict[str, Any]],
    raw_edges: list[dict[str, Any]],
    tools_bound: list[str],
    subagent_specs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalizes `dag_nodes` and `dag_edges`, synthesizing a clean topology if empty."""
    nodes: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_nodes):
        node_id = str(
            item.get("id") or item.get("node_id") or f"node_{idx + 1}"
        ).strip()
        label = str(
            item.get("label")
            or item.get("name")
            or item.get("title")
            or node_id
        ).strip()
        node_type = str(item.get("type") or item.get("kind") or "step").strip()
        normalized_node: dict[str, Any] = {
            **item,
            "id": node_id,
            "label": label,
            "type": node_type,
        }
        nodes.append(normalized_node)

    edges: list[dict[str, Any]] = []
    for item in raw_edges:
        src = str(item.get("from") or item.get("source") or "").strip()
        dst = str(item.get("to") or item.get("target") or "").strip()
        if not src or not dst:
            continue
        edge_label = str(item.get("label") or item.get("condition") or "").strip()
        normalized_edge: dict[str, Any] = {
            **item,
            "from": src,
            "to": dst,
            "source": src,
            "target": dst,
            "label": edge_label,
        }
        edges.append(normalized_edge)

    if not nodes:
        nodes = [
            {"id": "intake", "label": "Mission Intake", "type": "input"},
        ]
        if subagent_specs:
            for sub in subagent_specs:
                sid = f"sub_{sub['name']}"
                nodes.append(
                    {
                        "id": sid,
                        "label": sub.get("description", sub["name"])[:36]
                        or sub["name"],
                        "type": "subagent",
                    }
                )
            nodes.append(
                {
                    "id": "synthesize",
                    "label": "Synthesize & Deliver",
                    "type": "output",
                }
            )
            edges = [
                *[
                    {
                        "from": "intake",
                        "to": f"sub_{sub['name']}",
                        "source": "intake",
                        "target": f"sub_{sub['name']}",
                        "label": "fan-out",
                    }
                    for sub in subagent_specs
                ],
                *[
                    {
                        "from": f"sub_{sub['name']}",
                        "to": "synthesize",
                        "source": f"sub_{sub['name']}",
                        "target": "synthesize",
                        "label": "reduce",
                    }
                    for sub in subagent_specs
                ],
            ]
        else:
            nodes.extend(
                [
                    {
                        "id": "execute_dag",
                        "label": dag_topology[:40] or "Execute Tools",
                        "type": "process",
                        "tools": tools_bound,
                    },
                    {
                        "id": "deliver",
                        "label": "Verified Output",
                        "type": "output",
                    },
                ]
            )
            edges = [
                {
                    "from": "intake",
                    "to": "execute_dag",
                    "source": "intake",
                    "target": "execute_dag",
                    "label": "",
                },
                {
                    "from": "execute_dag",
                    "to": "deliver",
                    "source": "execute_dag",
                    "target": "deliver",
                    "label": "",
                },
            ]

    return nodes, edges


def _yaml_quote(value: str) -> str:
    """Safely quotes a single-line YAML scalar using JSON string escaping."""
    collapsed = " ".join((value or "").splitlines()).strip()
    return json.dumps(collapsed, ensure_ascii=False)


def _render_custom_agent_markdown(
    agent_id: str,
    display_name: str,
    description: str,
    dag_topology: str,
    tools_bound: list[str],
    system_instructions: str,
    dag_nodes: list[dict[str, Any]],
    dag_edges: list[dict[str, Any]],
    enable_subagents: bool,
    subagent_specs: list[dict[str, Any]],
) -> str:
    """Renders an Antigravity Custom Agent `.md` file with YAML frontmatter."""
    tools_yaml = (
        "\n".join(f"  - {t}" for t in tools_bound)
        if tools_bound
        else "  []"
    )
    if tools_bound:
        tools_block = f"tools:\n{tools_yaml}"
    else:
        tools_block = "tools: []"

    nodes_bullets = "\n".join(
        f"- **`{n['id']}`** ({n.get('type', 'step')}): {n.get('label', n['id'])}"
        for n in dag_nodes
    )
    edges_bullets = "\n".join(
        f"- `{e['from']}` -> `{e['to']}`"
        + (f" ({e['label']})" if e.get("label") else "")
        for e in dag_edges
    )
    subagents_section = ""
    if enable_subagents and subagent_specs:
        sub_lines = "\n".join(
            f"- **`{s['name']}`**: {s.get('description', '')} "
            f"(tools: `{', '.join(s.get('tools', [])) or 'read-only'}`)"
            for s in subagent_specs
        )
        subagents_section = f"\n### Declared Subagents\n{sub_lines}\n"

    return (
        "---\n"
        f"name: {agent_id}\n"
        f"display_name: {_yaml_quote(display_name)}\n"
        f"description: {_yaml_quote(description)}\n"
        f"dag_topology: {_yaml_quote(dag_topology)}\n"
        f"{tools_block}\n"
        "mainAgent: true\n"
        "subagent: true\n"
        "commandExecutionPolicy: auto\n"
        "---\n\n"
        "# System Instructions\n\n"
        f"{system_instructions.strip()}\n\n"
        "# DAG Architecture\n\n"
        f"- **Topology**: {dag_topology}\n"
        f"- **Subagents Enabled**: `{str(enable_subagents).lower()}`\n\n"
        "### DAG Nodes\n"
        f"{nodes_bullets or '- Single autonomous execution node'}\n\n"
        "### DAG Edges\n"
        f"{edges_bullets or '- Direct execution flow'}\n"
        f"{subagents_section}"
    )


def build_custom_agent(
    agent_id: str,
    display_name: str,
    description: str,
    dag_topology: str,
    system_instructions: str,
    tool_names: list[str],
    dag_nodes_json: str = "[]",
    dag_edges_json: str = "[]",
    enable_subagents: bool = False,
    subagent_specs_json: str = "[]",
) -> dict[str, Any]:
    """Builds and registers a custom Antigravity DAG Agent (`.md` + JSON registry spec).

    Validates all requested `tool_names` against built-in Antigravity harness
    tools, scenario tools, `generate_video`, and dynamically synthesized tools,
    writes `agents/<agent_id>.md` and `agents/registry/<agent_id>.json`, and
    verifies the resulting `LocalAgentConfig` is immediately runnable via the
    Single API Gateway.

    Args:
        agent_id: Unique kebab-case identifier (e.g. 'trailer-director', 'arcade-builder').
        display_name: Human-friendly agent title (e.g. 'Hollywood Trailer Director').
        description: Concise summary of the agent's mission and persona.
        dag_topology: Name of the agentic DAG pattern (e.g. 'Linear Sequential Pipeline',
            'Generator-Verifier Self-Healing Loop', 'Parallel Map-Reduce Fan-Out').
        system_instructions: Detailed Markdown system prompt guiding step-by-step
            DAG execution, tool usage, quality gates, and output formatting.
        tool_names: List of built-in and custom tool names to bind to this agent.
        dag_nodes_json: JSON array string of DAG node objects, e.g.
            `'[{"id": "draft", "label": "Draft V1", "type": "generator"}]'`.
        dag_edges_json: JSON array string of DAG edge objects, e.g.
            `'[{"from": "draft", "to": "critique", "label": "inspect"}]'`.
        enable_subagents: Set True if the agent spawns parallel or adversarial
            subagents via `start_subagent` / `invoke_subagent`.
        subagent_specs_json: Optional JSON array string of static subagent specs, e.g.
            `'[{"name": "shark_fin", "description": "Unit economics shark", "system_instructions": "...", "tools": ["emit_dag_step"]}]'`.

    Returns:
        Structured summary `{status, agent_id, md_path, registry_path, tools_bound, dag_topology}`.
    """
    normalized_id = normalize_agent_id(agent_id)
    if normalized_id in _RESERVED_AGENT_IDS:
        raise ValueError(
            f"agent_id '{normalized_id}' is reserved. Choose a distinct custom agent ID."
        )

    clean_display_name = (display_name or "").strip() or normalized_id
    clean_description = (description or "").strip()
    if not clean_description:
        raise ValueError("description must be a non-empty string.")
    clean_topology = (dag_topology or "").strip() or "Autonomous Agentic DAG"
    clean_instructions = (system_instructions or "").strip()
    if not clean_instructions:
        raise ValueError("system_instructions must be a non-empty string.")

    custom_tools_map = get_all_custom_tools_map()
    valid_tool_names = set(_BUILTIN_NAME_TO_ENUM.keys()) | set(custom_tools_map.keys())

    if not isinstance(tool_names, list):
        raise ValueError("tool_names must be a list of tool name strings.")

    tools_bound: list[str] = []
    unknown_tools: list[str] = []
    for raw_t in tool_names:
        t_str = str(raw_t).strip()
        if not t_str:
            continue
        canonical_t = _BUILTIN_ALIAS_NORMALIZATION.get(t_str, t_str)
        if canonical_t not in valid_tool_names and t_str not in valid_tool_names:
            unknown_tools.append(t_str)
            continue
        chosen = canonical_t if canonical_t in valid_tool_names else t_str
        if chosen not in tools_bound:
            tools_bound.append(chosen)

    raw_nodes = _parse_json_list_param(dag_nodes_json, "dag_nodes_json")
    raw_edges = _parse_json_list_param(dag_edges_json, "dag_edges_json")
    raw_subagents = _parse_json_list_param(subagent_specs_json, "subagent_specs_json")

    normalized_subagents: list[dict[str, Any]] = []
    seen_sub_names: set[str] = set()
    for idx, sub in enumerate(raw_subagents):
        raw_sub_name = str(sub.get("name") or f"subagent_{idx + 1}").strip()
        sub_name = re.sub(r"[^a-z0-9_-]+", "_", raw_sub_name.lower()).strip("_-")
        if not sub_name or sub_name in seen_sub_names:
            continue
        seen_sub_names.add(sub_name)

        sub_desc = str(sub.get("description") or f"Subagent {sub_name}").strip()
        sub_si = str(sub.get("system_instructions") or sub_desc).strip()
        raw_sub_tools = sub.get("tools") or []
        sub_tools: list[str] = []
        if isinstance(raw_sub_tools, list):
            for st in raw_sub_tools:
                st_str = str(st).strip()
                if not st_str:
                    continue
                canonical_st = _BUILTIN_ALIAS_NORMALIZATION.get(st_str, st_str)
                if canonical_st not in valid_tool_names and st_str not in valid_tool_names:
                    unknown_tools.append(st_str)
                    continue
                chosen_st = canonical_st if canonical_st in valid_tool_names else st_str
                if chosen_st not in sub_tools:
                    sub_tools.append(chosen_st)

        raw_allowed = sub.get("allowed_subagents") or []
        allowed_subs = (
            [str(a).strip() for a in raw_allowed if str(a).strip()]
            if isinstance(raw_allowed, list)
            else []
        )
        normalized_subagents.append(
            {
                "name": sub_name,
                "description": sub_desc,
                "system_instructions": sub_si,
                "tools": sub_tools,
                "allowed_subagents": allowed_subs,
            }
        )

    if unknown_tools:
        available_sorted = sorted(
            {t["name"] for t in BUILTIN_TOOLS_METADATA} | set(custom_tools_map.keys())
        )
        raise ValueError(
            f"Unknown tool_names requested: {sorted(set(unknown_tools))}. "
            f"Available tools are: {available_sorted}. "
            "Use `create_custom_tool` first if you want to synthesize a new Python tool."
        )

    effective_enable_subagents = bool(
        enable_subagents
        or normalized_subagents
        or "start_subagent" in tools_bound
        or "invoke_subagent" in tools_bound
    )
    if (
        effective_enable_subagents
        and "start_subagent" not in tools_bound
        and "invoke_subagent" not in tools_bound
    ):
        tools_bound.append("start_subagent")

    dag_nodes, dag_edges = _normalize_dag_graph(
        clean_topology,
        raw_nodes,
        raw_edges,
        tools_bound,
        normalized_subagents,
    )

    agents_dir = _get_agents_dir()
    registry_dir = _get_registry_dir()
    md_path = agents_dir / f"{normalized_id}.md"
    registry_path = registry_dir / f"{normalized_id}.json"

    now_iso = datetime.now(UTC).isoformat()
    created_at = now_iso
    if registry_path.is_file():
        try:
            existing = json.loads(registry_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("created_at"):
                created_at = str(existing["created_at"])
        except Exception:
            pass

    md_content = _render_custom_agent_markdown(
        agent_id=normalized_id,
        display_name=clean_display_name,
        description=clean_description,
        dag_topology=clean_topology,
        tools_bound=tools_bound,
        system_instructions=clean_instructions,
        dag_nodes=dag_nodes,
        dag_edges=dag_edges,
        enable_subagents=effective_enable_subagents,
        subagent_specs=normalized_subagents,
    )
    md_path.write_text(md_content, encoding="utf-8")

    spec_payload: dict[str, Any] = {
        "agent_id": normalized_id,
        "display_name": clean_display_name,
        "description": clean_description,
        "dag_topology": clean_topology,
        "dag_nodes": dag_nodes,
        "dag_edges": dag_edges,
        "system_instructions": clean_instructions,
        "tool_names": tools_bound,
        "tool_count": len(tools_bound),
        "enable_subagents": effective_enable_subagents,
        "subagent_specs": normalized_subagents,
        "md_path": str(md_path),
        "is_builder": False,
        "created_at": created_at,
        "updated_at": now_iso,
    }
    registry_path.write_text(
        json.dumps(spec_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Validate immediately that `build_local_agent_config` builds cleanly.
    build_local_agent_config(normalized_id)

    return {
        "status": "created",
        "agent_id": normalized_id,
        "display_name": clean_display_name,
        "md_path": str(md_path),
        "registry_path": str(registry_path),
        "tools_bound": tools_bound,
        "dag_topology": clean_topology,
        "enable_subagents": effective_enable_subagents,
    }


def list_registered_agents_and_tools() -> dict[str, Any]:
    """Lists all available built-in, scenario, and dynamic tools plus registered custom agents.

    Call this tool to inspect exact tool names and descriptions before calling
    `build_custom_agent`, or to check which custom agents and dynamic tools are
    currently registered in the Antigravity catalog.

    Returns:
        Dictionary containing `builtin_tools`, `core_custom_tools`,
        `scenario_tools`, `dynamic_tools`, `all_tool_names`, `tools`,
        `registered_agents`, and `counts`.
    """
    _, scenario_meta = _load_scenario_tools()
    dynamic_map = _load_dynamic_tools_from_disk()
    dynamic_dir = _get_dynamic_tools_dir()

    core_custom_tools: list[dict[str, Any]] = []
    if _get_core_generate_video() is not None:
        core_custom_tools.append(
            {
                "name": "generate_video",
                "description": (
                    "Generates an MP4 video clip from a text prompt using "
                    "Vertex AI Veo 3.1."
                ),
                "source": "core",
            }
        )
    core_custom_tools.extend(
        [
            {
                "name": "create_custom_tool",
                "description": (
                    "Synthesizes, AST-validates, and hot-registers a new custom "
                    "Python tool in app/dynamic_tools/."
                ),
                "source": "builder",
            },
            {
                "name": "build_custom_agent",
                "description": (
                    "Builds and registers a Custom Antigravity DAG Agent (.md + "
                    "JSON registry spec)."
                ),
                "source": "builder",
            },
            {
                "name": "list_registered_agents_and_tools",
                "description": (
                    "Lists all built-in tools, scenario tools, dynamic tools, "
                    "and registered custom agents."
                ),
                "source": "builder",
            },
        ]
    )

    dynamic_tools_meta: list[dict[str, Any]] = [
        {
            "name": name,
            "description": (inspect.getdoc(fn) or "").splitlines()[0]
            if inspect.getdoc(fn)
            else f"Dynamic tool {name}",
            "module_path": str(dynamic_dir / f"{name}.py"),
            "source": "dynamic",
        }
        for name, fn in sorted(dynamic_map.items())
    ]

    unified_tools: list[dict[str, Any]] = [
        *BUILTIN_TOOLS_METADATA,
        *core_custom_tools,
        *scenario_meta,
        *dynamic_tools_meta,
    ]
    all_tool_names: list[str] = []
    for item in unified_tools:
        tname = item.get("name", "")
        if tname and tname not in all_tool_names:
            all_tool_names.append(tname)

    custom_agents = [
        entry
        for entry in list_agents_catalog()
        if not entry.get("is_builder", False)
    ]

    return {
        "builtin_tools": list(BUILTIN_TOOLS_METADATA),
        "core_custom_tools": core_custom_tools,
        "scenario_tools": scenario_meta,
        "dynamic_tools": dynamic_tools_meta,
        "all_tool_names": all_tool_names,
        "tools": unified_tools,
        "registered_agents": custom_agents,
        "counts": {
            "builtin_tools": len(BUILTIN_TOOLS_METADATA),
            "core_custom_tools": len(core_custom_tools),
            "scenario_tools": len(scenario_meta),
            "dynamic_tools": len(dynamic_tools_meta),
            "total_tools": len(all_tool_names),
            "registered_agents": len(custom_agents),
        },
    }


# ---------------------------------------------------------------------------
# Gateway Helper APIs
# ---------------------------------------------------------------------------


def get_all_custom_tools_map() -> dict[str, Callable[..., Any]]:
    """Returns `{tool_name: callable}` merging `generate_video`, `SCENARIO_TOOLS`, dynamic tools, and builder tools."""
    merged: dict[str, Callable[..., Any]] = {}

    gen_vid = _get_core_generate_video()
    if gen_vid is not None:
        merged["generate_video"] = gen_vid

    scenario_tools, _ = _load_scenario_tools()
    merged.update(scenario_tools)

    dynamic_tools = _load_dynamic_tools_from_disk()
    merged.update(dynamic_tools)

    merged["create_custom_tool"] = create_custom_tool
    merged["build_custom_agent"] = build_custom_agent
    merged["list_registered_agents_and_tools"] = list_registered_agents_and_tools

    return merged


def _build_antigravity_root_catalog_entry() -> dict[str, Any]:
    """Builds the catalog metadata entry for the root `antigravity` builder agent."""
    dynamic_names = sorted(_load_dynamic_tools_from_disk().keys())
    root_tools = [
        "view_file",
        "create_file",
        "edit_file",
        "run_command",
        "search_web",
        "read_url_content",
        "generate_image",
        "generate_video",
        "start_subagent",
        "list_registered_agents_and_tools",
        "create_custom_tool",
        "build_custom_agent",
        *dynamic_names,
    ]
    return {
        "agent_id": "antigravity",
        "display_name": "Antigravity (Agent & Tool Builder)",
        "description": (
            "Autonomous meta-builder and software engineering agent powered by "
            "the Google Antigravity SDK harness — synthesizes custom Python "
            "tools on the fly and compiles specialized multi-agent DAGs."
        ),
        "dag_topology": "Autonomous Meta-Builder & Dynamic Tool Synthesis Loop",
        "dag_nodes": [
            {
                "id": "discover",
                "label": "Inspect Catalog & Spec",
                "type": "input",
                "tools": ["list_registered_agents_and_tools"],
            },
            {
                "id": "synthesize_tool",
                "label": "Synthesize Custom Tool",
                "type": "builder",
                "tools": ["create_custom_tool"],
            },
            {
                "id": "compile_dag",
                "label": "Compile Agent (.md + .json)",
                "type": "builder",
                "tools": ["build_custom_agent"],
            },
            {
                "id": "ready",
                "label": "Live on Single Gateway",
                "type": "output",
                "tools": [],
            },
        ],
        "dag_edges": [
            {
                "from": "discover",
                "to": "synthesize_tool",
                "source": "discover",
                "target": "synthesize_tool",
                "label": "if new tool needed",
            },
            {
                "from": "discover",
                "to": "compile_dag",
                "source": "discover",
                "target": "compile_dag",
                "label": "existing tools",
            },
            {
                "from": "synthesize_tool",
                "to": "compile_dag",
                "source": "synthesize_tool",
                "target": "compile_dag",
                "label": "hot-register",
            },
            {
                "from": "compile_dag",
                "to": "ready",
                "source": "compile_dag",
                "target": "ready",
                "label": "verified",
            },
        ],
        "tool_names": root_tools,
        "tool_count": len(root_tools),
        "enable_subagents": True,
        "subagent_specs": [],
        "is_builder": True,
        "created_at": "2026-10-29T00:00:00+00:00",
    }


def list_agents_catalog() -> list[dict[str, Any]]:
    """Returns the `"antigravity"` root builder entry plus all custom agents in `agents/registry/*.json`."""
    catalog: list[dict[str, Any]] = [_build_antigravity_root_catalog_entry()]
    registry_dir = _get_registry_dir()
    if not registry_dir.is_dir():
        return catalog

    custom_entries: list[dict[str, Any]] = []
    for json_file in sorted(registry_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data.get("agent_id"):
                continue
            tool_names = list(data.get("tool_names") or [])
            data.setdefault("tool_count", len(tool_names))
            data.setdefault("is_builder", False)
            data.setdefault("dag_nodes", [])
            data.setdefault("dag_edges", [])
            data.setdefault("subagent_specs", [])
            custom_entries.append(data)
        except Exception as exc:
            logger.warning("Skipping invalid agent registry file %s: %s", json_file, exc)

    custom_entries.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("agent_id", ""))))
    catalog.extend(custom_entries)
    return catalog


def build_local_agent_config(agent_id: str) -> LocalAgentConfig:
    """Builds a live `LocalAgentConfig` for either `antigravity` or any registered custom agent."""
    raw_id = (agent_id or "").strip()
    if raw_id in ROOT_AGENT_ALIASES or (
        raw_id and normalize_agent_id(raw_id) in ROOT_AGENT_ALIASES
    ):
        from app import agent as agent_mod

        _refresh_root_sdk_config()
        return agent_mod.sdk_config

    normalized_id = normalize_agent_id(raw_id)
    registry_path = _get_registry_dir() / f"{normalized_id}.json"
    if not registry_path.is_file() and normalized_id == "foodie-hourglass-solver":
        normalized_id = "food-crawl-planner"
        registry_path = _get_registry_dir() / f"{normalized_id}.json"
    if not registry_path.is_file():
        raise AgentNotFoundError(
            f"Custom agent '{normalized_id}' not found at {registry_path}."
        )

    spec = json.loads(registry_path.read_text(encoding="utf-8"))
    display_name = str(spec.get("display_name") or normalized_id)
    description = str(spec.get("description") or "")
    dag_topology = str(spec.get("dag_topology") or "Autonomous Agentic DAG")
    system_instructions = str(spec.get("system_instructions") or "")
    requested_tool_names: list[str] = [
        str(t).strip() for t in (spec.get("tool_names") or []) if str(t).strip()
    ]
    subagent_specs: list[dict[str, Any]] = [
        s for s in (spec.get("subagent_specs") or []) if isinstance(s, dict)
    ]
    enable_subagents = bool(
        spec.get("enable_subagents", False)
        or subagent_specs
        or "start_subagent" in requested_tool_names
        or "invoke_subagent" in requested_tool_names
    )

    workspace_dir = _get_workspace_dir()
    trajectories_dir = _get_trajectories_dir()
    app_data_dir = _get_app_data_dir()
    os.makedirs(workspace_dir, exist_ok=True)
    os.makedirs(trajectories_dir, exist_ok=True)
    os.makedirs(app_data_dir, exist_ok=True)

    custom_tools_map = get_all_custom_tools_map()
    enabled_builtins: list[types.BuiltinTools] = [types.BuiltinTools.FINISH]
    custom_callables: list[Callable[..., Any]] = []
    seen_custom_names: set[str] = set()

    def _add_builtin(b_enum: types.BuiltinTools) -> None:
        if b_enum not in enabled_builtins:
            enabled_builtins.append(b_enum)

    def _add_custom(name: str) -> None:
        fn = custom_tools_map.get(name)
        if fn is not None and name not in seen_custom_names:
            seen_custom_names.add(name)
            custom_callables.append(fn)

    has_workspace_mutation_or_exec = False
    for t_name in requested_tool_names:
        canonical = _BUILTIN_ALIAS_NORMALIZATION.get(t_name, t_name)
        if canonical in _BUILTIN_NAME_TO_ENUM:
            b_enum = _BUILTIN_NAME_TO_ENUM[canonical]
            _add_builtin(b_enum)
            if b_enum in (
                types.BuiltinTools.VIEW_FILE,
                types.BuiltinTools.CREATE_FILE,
                types.BuiltinTools.EDIT_FILE,
                types.BuiltinTools.RUN_COMMAND,
            ):
                has_workspace_mutation_or_exec = True
        elif t_name in custom_tools_map:
            _add_custom(t_name)
        elif canonical in custom_tools_map:
            _add_custom(canonical)
        else:
            logger.warning(
                "Custom agent '%s' references unavailable tool '%s'; skipping.",
                normalized_id,
                t_name,
            )

    if has_workspace_mutation_or_exec:
        for helper_b in _WORKSPACE_HELPER_BUILTINS:
            _add_builtin(helper_b)

    if enable_subagents:
        _add_builtin(types.BuiltinTools.START_SUBAGENT)

    # Build SubagentConfig objects (if any), routing built-ins to SubagentCapabilities
    # and custom Python tools to both SubagentConfig.tools and main_agent tools!
    declared_sub_names = {
        str(s.get("name", "")).strip()
        for s in subagent_specs
        if str(s.get("name", "")).strip()
    }
    subagent_configs: list[types.SubagentConfig] = []
    for s in subagent_specs:
        s_name = str(s.get("name") or "").strip()
        if not s_name:
            continue
        s_desc = str(s.get("description") or f"Subagent {s_name}")
        s_instructions = str(s.get("system_instructions") or s_desc)

        sub_builtins: list[types.BuiltinTools] = []
        sub_custom_names: list[str] = []
        for st_raw in s.get("tools") or []:
            st = str(st_raw).strip()
            canonical_st = _BUILTIN_ALIAS_NORMALIZATION.get(st, st)
            if canonical_st in _BUILTIN_NAME_TO_ENUM:
                b_enum = _BUILTIN_NAME_TO_ENUM[canonical_st]
                if b_enum not in sub_builtins:
                    sub_builtins.append(b_enum)
            elif st in custom_tools_map:
                _add_custom(st)
                if st not in sub_custom_names:
                    sub_custom_names.append(st)
            elif canonical_st in custom_tools_map:
                _add_custom(canonical_st)
                if canonical_st not in sub_custom_names:
                    sub_custom_names.append(canonical_st)

        valid_allowed_subs = [
            a
            for a in (s.get("allowed_subagents") or [])
            if isinstance(a, str) and a in declared_sub_names
        ]
        if valid_allowed_subs and types.BuiltinTools.START_SUBAGENT not in sub_builtins:
            sub_builtins.append(types.BuiltinTools.START_SUBAGENT)

        if sub_builtins:
            if types.BuiltinTools.FINISH not in sub_builtins:
                sub_builtins.append(types.BuiltinTools.FINISH)
            sub_enabled_tools = sub_builtins
        else:
            sub_enabled_tools = list(types.BuiltinTools.read_only())

        sub_caps = types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
            enabled_tools=sub_enabled_tools,
            allowed_subagents=valid_allowed_subs or None,
        )
        subagent_configs.append(
            types.SubagentConfig(
                name=s_name,
                description=s_desc,
                system_instructions=s_instructions,
                capabilities=sub_caps,
                tools=sub_custom_names,
            )
        )

    templated_si = TemplatedSystemInstructions(
        identity=(
            f"You are **{display_name}** (`{normalized_id}`), an autonomous "
            f"custom agent powered by the Google Antigravity SDK harness.\n"
            f"Mission & Persona: {description}\n"
            f"DAG Topology: {dag_topology}\n\n"
            f"{system_instructions}"
        ),
        sections=[
            types.SystemInstructionSection(
                title="sandbox_and_dag_execution_guidelines",
                content=(
                    f"- **Sandbox Workspace**: `{workspace_dir}` — write all "
                    f"generated code, HTML5 apps, Python scripts, JSON, and `.ics` "
                    f"files strictly inside `{workspace_dir}` using clean absolute paths.\n"
                    f"- **DAG Topology**: `{dag_topology}` — execute each stage "
                    "methodically. If `emit_dag_step` is bound in your tools, call "
                    "it at major node transitions so live telemetry updates.\n"
                    "- **Generated Media**: When calling `generate_image`, "
                    "`generate_video`, or `generate_video_clip`, do NOT include "
                    "raw `/tmp/...` Markdown image/video links in your text reply."
                ),
            )
        ],
    )

    capabilities = types.CapabilitiesConfig(
        enable_subagents=enable_subagents,
        agent_behavior=types.AgentBehavior.AUTONOMOUS,
        enabled_tools=enabled_builtins,
        max_subagent_depth=3 if enable_subagents else None,
    )

    model_name = os.environ.get("ANTIGRAVITY_MODEL", "gemini-3.7-flash")
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in (
        "true",
        "1",
    )
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    return LocalAgentConfig(
        model=model_name,
        vertex=use_vertex,
        project=project,
        location=location,
        system_instructions=templated_si,
        capabilities=capabilities,
        tools=custom_callables,
        subagents=subagent_configs,
        workspaces=[workspace_dir],
        env=ensure_localharness_env(),
        policies=[
            policy.allow_all(),
            *policy.workspace_only([workspace_dir]),
        ],
        save_dir=trajectories_dir,
        app_data_dir=app_data_dir,
    )
