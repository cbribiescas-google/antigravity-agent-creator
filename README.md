# Antigravity Agent Creator (`antigravity-agent-creator`)

An end-to-end **Google Antigravity SDK + Google ADK (>2.0) + Gemini Enterprise** platform for interactively designing, synthesizing tools for, executing, and benchmarking multi-step **Agentic DAGs** — complete with a **Single Unified API Gateway**, **Live DAG Studio Web UI**, **4-Sink Per-User/Per-Conversation Token Telemetry**, and **1-Command Infrastructure-as-Code (IaC)** provisioning.

---

## Key Capabilities

1. **Autonomous `Antigravity` Root Builder & Interactive Workshop Coach ([`app/agent.py`](app/agent.py), [`app/agent_builder.py`](app/agent_builder.py))**:
   - Powered by `google.antigravity.LocalAgentConfig` wrapped inside `google.adk.labs.antigravity.AntigravityAgent`.
   - Equipped with sandboxed file operations (`view_file`, `create_file`, `edit_file`), `run_command`, `search_web`, `read_url_content`, `invoke_subagent`, `run_workflow`, `generate_image`, **Veo 3.1** `generate_video`, plus dynamic agent & tool synthesis:
     - `create_custom_tool(tool_name, description, python_code)` — AST-validates, persists (`app/dynamic_tools/`), and hot-registers brand-new Python tools at runtime.
     - `build_custom_agent(...)` — Compiles and registers multi-step DAG agents (`agents/<id>.md` + `agents/registry/<id>.json`) immediately runnable on the Gateway and deployable to Vertex AI Agent Runtime.
   - Supports **3 Interactive Workshop Design Modes**:
     - **Option 1**: Guided interactive interview -> Business & Technical Requirements Doc (BRD) -> Agent build.
     - **Option 2**: Fill-in-the-blanks ("Mad-Libs") Skeleton BRD -> Agent build.
     - **Option 3**: Bring-your-own-idea (Blank BRD or Freestyle prompt) -> Agent build.

2. **Showcase Agentic DAG Fleet ([`agents/`](agents/), [`app/scenario_tools/`](app/scenario_tools/))**:
   - **🎬 Trailer Director (`trailer-director`)** — *Linear Sequential Pipeline*: 3-beat trailer script -> cinema poster (`generate_image`) -> 4s 16:9 Veo 3.1 clip (`generate_video_clip`).
   - **🦈 Shark Tank Panel (`shark-tank-panel`)** — *Parallel Map-Reduce Fan-Out*: simultaneous evaluation by `Numbers Hawk`, `Hype Visionary`, and `Skeptical Customer` subagents -> weighted term-sheet synthesis.
   - **🍜 Food Crawl Planner (`food-crawl-planner`)** — *Hourglass Gather-Solve-Publish*: live neighborhood `search_web` -> deterministic walking/budget solver (`solve_crawl_constraints`) -> `.ics` calendar + `.html` route card + watercolor postcard.
   - **🕹️ Arcade Builder (`arcade-builder`)** — *Generator-Verifier Self-Healing Loop*: single-file HTML5 Canvas game generation -> `validate_html5_game` DOM/JS/controls loop until zero errors -> 16-bit box art.
   - **🧭 Six Degrees Detective (`six-degrees-detective`)** — *Dynamic Tree Search & Branch Pruning*: live multi-hop web graph search + `record_pruned_branch` dead-end pruning -> verified shortest connection chain.
   - Plus 5 additional pre-built DAG recipes in `agents/registry/` (`corporate-dnd-master`, `mythbuster-router`, `perfectionist-art-director`, `supreme-court-debate`, `bot-gladiator-arena`).

3. **Single Unified API Gateway & Live DAG Studio UI ([`app/gateway.py`](app/gateway.py), [`frontend/`](frontend/))**:
   - Routes execution across both `antigravity` and all registered custom DAG agents (`POST /api/gateway/stream`, `POST /api/gateway/run`) over NDJSON streaming.
   - Tracks live per-user and per-conversation token ledgers (`GET /api/gateway/usage`) and renders real-time DAG node execution, tool calls, inline images/videos, and HTML/ICS artifacts at `/studio/`.

4. **1:1 Gemini Enterprise App Alignment & 4-Sink Token Telemetry ([`app/telemetry.py`](app/telemetry.py), [`app/app_utils/reasoning_engine_adapter.py`](app/app_utils/reasoning_engine_adapter.py))**:
   - Deterministically maps each Gemini Enterprise conversation (`ge_conversation_id`) to a persistent Antigravity SQLite trajectory backed up in GCS (`gs://<PROJECT_ID>-antigravity-telemetry/trajectories/`).
   - Emits per-turn and cumulative conversation token usage (`prompt`, `cached`, `candidates`, `thoughts`, `total`) to **BigQuery**, **Cloud Logging**, **Cloud Trace (OpenTelemetry)**, and the **ADK Event Stream**.

---

## Self-Contained Infrastructure Setup (`scripts/`)

All GCP project bootstrap, IAM, licensing, storage, Vertex AI Agent Runtime deployment, and Gemini Enterprise registration scripts live in [`scripts/`](scripts/):

| Script | Purpose |
| :--- | :--- |
| [`scripts/setup_all.sh`](scripts/setup_all.sh) | **Master 1-command IaC script** — runs full project bootstrap, IAM, licenses, shared bucket, Agent Runtime fleet deploy, Gemini Enterprise `ALL_USERS` registration, and LHS nav pinning |
| [`scripts/bootstrap_project_and_sa.sh`](scripts/bootstrap_project_and_sa.sh) | Creates/verifies GCP project, links billing, enables all required APIs, creates & binds `gemini-enterprise-admin` SA |
| [`scripts/enable_antigravity.sh`](scripts/enable_antigravity.sh) | Enables `aiplatform.googleapis.com` and grants `roles/aiplatform.user` to the SA and target users/domains |
| [`scripts/assign_gemini_enterprise_licenses.sh`](scripts/assign_gemini_enterprise_licenses.sh) | Configures `GSUITE` `aclConfig`, binds Discovery Engine IAM, and assigns Gemini Enterprise Plus licenses across the domain |
| [`scripts/provision_shared_agent_bucket.sh`](scripts/provision_shared_agent_bucket.sh) | Creates private shared GCS bucket (`gs://<PROJECT_ID>-agents-shared`) with enforced Public Access Prevention |
| [`scripts/provision.sh`](scripts/provision.sh) | Provisions BigQuery telemetry + Discovery Engine Engine, deploys `Antigravity` + the 5 Showcase Agents concurrently to Vertex AI Agent Runtime, publishes to Gemini Enterprise (`ALL_USERS`), and pins to LHS |
| [`scripts/pin_agents_lhs.sh`](scripts/pin_agents_lhs.sh) | Programmatically pins registered agents on the Gemini Enterprise LHS nav panel via `UserAnnotationManagementService` |
| [`scripts/deploy_studio_cloud_run.sh`](scripts/deploy_studio_cloud_run.sh) | Deploys the standalone Unified API Gateway & Live DAG Studio UI (`/studio/`) to Cloud Run |
| [`scripts/query_telemetry.sh`](scripts/query_telemetry.sh) | Queries BigQuery for per-conversation and turn-by-turn token usage reports |
| [`scripts/stream_logs.sh`](scripts/stream_logs.sh) | Streams live logs from Vertex AI Agent Runtime (`ReasoningEngine`) |

---

## Quickstart

### 1. Full GCP & Gemini Enterprise Provisioning (From Scratch)

```bash
chmod +x scripts/*.sh
PROJECT_ID="your-gcp-project-id" DOMAIN="your-domain.com" ./scripts/setup_all.sh
```

Or to re-deploy/update the Agent Runtime fleet and Gemini Enterprise registrations on an already-bootstrapped project:

```bash
./scripts/provision.sh
```

*(Set `DEPLOY_SHOWCASE_AGENTS=false` if you only want to deploy the root `Antigravity` agent, or `DEPLOY_CLOUD_RUN_STUDIO=true` with `./scripts/setup_all.sh` to also deploy the Live Studio UI to Cloud Run.)*

### 2. Run Locally (Unified API Gateway + Live DAG Studio UI)

```bash
agents-cli install
uv run pytest tests/unit
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8090
```

Then open **`http://localhost:8090/studio/`** to interact with `Antigravity` and all custom DAG agents with live DAG visualization and per-user/per-conversation token telemetry.

### 3. Query Token Telemetry

```bash
./scripts/query_telemetry.sh
```
