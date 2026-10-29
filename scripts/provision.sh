#!/usr/bin/env bash
# ==============================================================================
# Antigravity Agent Creator: Self-Contained Provisioning & Multi-Agent Deployment
# (`scripts/provision.sh`)
# ==============================================================================
# Provisions:
# 1. Required GCP APIs, Vertex AI Antigravity IAM, Gemini Enterprise User Licenses
# 2. Telemetry & Trajectory Storage:
#    - Private Shared Agent Bucket (`gs://<PROJECT_ID>-agents-shared`)
#    - GCS Trajectory Bucket (`gs://<PROJECT_ID>-antigravity-telemetry`)
#    - BigQuery Dataset & Table (`antigravity_telemetry.token_usage`)
# 3. Discovery Engine Companion DataStore (`prudential_companion_ds`)
# 4. Gemini Enterprise Engine (`prudential-agency-engine`) in `locations/global`
# 5. Concurrent Vertex AI Agent Runtime Deployment (`us-central1`) for:
#    - `Antigravity` (`gemini-antigravity-demo`, root autonomous builder + BRD coach)
#    - Plus (when DEPLOY_SHOWCASE_AGENTS=true, default) the 5 Showcase DAG Agents:
#      * `🎬 Trailer Director` (`antigravity-trailer-director`)
#      * `🦈 Shark Tank Panel` (`antigravity-shark-tank-panel`)
#      * `🍜 Food Crawl Planner` (`antigravity-food-crawl-planner`)
#      * `🕹️ Arcade Builder` (`antigravity-arcade-builder`)
#      * `🧭 Six Degrees Detective` (`antigravity-six-degrees-detective`)
# 6. Gemini Enterprise ADK Registration + Custom SVG Branding + `ALL_USERS` Sharing
# 7. Programmatic LHS Nav Panel Pinning (`scripts/pin_agents_lhs.sh`)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-gemini-enterprise-demo-cb}}"
SA_EMAIL="gemini-enterprise-admin@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="${HOME}/.config/gcloud/gemini-enterprise-admin-key.json"
DE_LOCATION="${DE_LOCATION:-global}"
RUNTIME_REGION="${RUNTIME_REGION:-us-central1}"
DS_ID="${DS_ID:-prudential_companion_ds}"
ENGINE_ID="${ENGINE_ID:-prudential-agency-engine}"
DOMAIN="${DOMAIN:-cbribiescas.altostrat.com}"
EXTRA_USERS="${EXTRA_USERS:-cbribiescas@gcp.altostrat.com}"
TELEMETRY_BUCKET="${TELEMETRY_BUCKET:-${PROJECT_ID}-antigravity-telemetry}"
SHARED_AGENT_BUCKET="${SHARED_AGENT_BUCKET:-${PROJECT_ID}-agents-shared}"
BQ_DATASET="${BQ_DATASET:-antigravity_telemetry}"
BQ_TABLE="${BQ_TABLE:-token_usage}"
DEPLOY_SHOWCASE_AGENTS="${DEPLOY_SHOWCASE_AGENTS:-true}"
PURGE_OTHER_AGENTS="${PURGE_OTHER_AGENTS:-false}"

echo "=============================================================================="
echo "Provisioning Antigravity Agent Creator Fleet"
echo "Project: ${PROJECT_ID} | DE Location: ${DE_LOCATION} | Runtime Region: ${RUNTIME_REGION}"
echo "Deploy 5 Showcase Agents: ${DEPLOY_SHOWCASE_AGENTS}"
echo "=============================================================================="

# 1. Authenticate as the automation Service Account (key file or impersonation)
gcloud config set project "${PROJECT_ID}" --quiet
gcloud config set context_aware/use_client_certificate false --quiet >/dev/null 2>&1 || true
if [[ -f "${KEY_FILE}" ]] && grep -q '"type": *"service_account"' "${KEY_FILE}" 2>/dev/null; then
  gcloud config unset auth/impersonate_service_account --quiet >/dev/null 2>&1 || true
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_FILE}" --project="${PROJECT_ID}" --quiet
  export GOOGLE_APPLICATION_CREDENTIALS="${KEY_FILE}"
else
  gcloud config set auth/impersonate_service_account "${SA_EMAIL}" --quiet
  if [[ -f "${HOME}/.config/gcloud/application_default_credentials.json" ]]; then
    cp -f "${HOME}/.config/gcloud/application_default_credentials.json" "${KEY_FILE}"
    export GOOGLE_APPLICATION_CREDENTIALS="${KEY_FILE}"
  fi
fi
export GOOGLE_CLOUD_PROJECT="${PROJECT_ID}"
export GOOGLE_API_USE_CLIENT_CERTIFICATE="false"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")"
TOKEN="$(gcloud auth print-access-token --quiet)"

if [[ "${DE_LOCATION}" == "global" ]]; then
  DE_API_BASE="https://discoveryengine.googleapis.com/v1alpha"
else
  DE_API_BASE="https://${DE_LOCATION}-discoveryengine.googleapis.com/v1alpha"
fi

# 2. Ensure Antigravity IAM, User Licenses, and Telemetry APIs/IAM
echo "[1/8] Ensuring Antigravity, Telemetry, User Licenses & Discovery Engine IAM permissions..."
"${SCRIPT_DIR}/enable_antigravity.sh" "domain:${DOMAIN}" ${EXTRA_USERS}
"${SCRIPT_DIR}/assign_gemini_enterprise_licenses.sh" "${DOMAIN}"
gcloud services enable \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  --project="${PROJECT_ID}" --quiet

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user" \
  --condition=None --quiet >/dev/null

for ROLE in \
  "roles/cloudtrace.agent" \
  "roles/logging.logWriter" \
  "roles/bigquery.dataEditor" \
  "roles/bigquery.jobUser" \
  "roles/storage.objectAdmin"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None --quiet >/dev/null
done

# 3. Provision Shared Agent Bucket, Trajectory Bucket & BigQuery Telemetry Table
echo "[2/8] Provisioning Shared Agent Bucket (${SHARED_AGENT_BUCKET}), Trajectory Bucket (${TELEMETRY_BUCKET}) & BigQuery Telemetry (${BQ_DATASET}.${BQ_TABLE})..."
"${SCRIPT_DIR}/provision_shared_agent_bucket.sh"
if ! gcloud storage buckets describe "gs://${TELEMETRY_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${TELEMETRY_BUCKET}" \
    --project="${PROJECT_ID}" \
    --location="${RUNTIME_REGION}" \
    --uniform-bucket-level-access \
    --public-access-prevention --quiet
  echo "  -> Created GCS bucket gs://${TELEMETRY_BUCKET}"
else
  echo "  -> GCS bucket gs://${TELEMETRY_BUCKET} already exists."
fi

TOKEN="$(gcloud auth print-access-token --quiet)"
BQ_DS_HTTP="$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://bigquery.googleapis.com/bigquery/v2/projects/${PROJECT_ID}/datasets/${BQ_DATASET}")"
if [[ "${BQ_DS_HTTP}" != "200" ]]; then
  curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    "https://bigquery.googleapis.com/bigquery/v2/projects/${PROJECT_ID}/datasets" \
    -d '{
      "datasetReference": {
        "projectId": "'"${PROJECT_ID}"'",
        "datasetId": "'"${BQ_DATASET}"'"
      },
      "location": "US",
      "description": "Token usage telemetry per request and per Gemini Enterprise conversation for Antigravity Agents"
    }' >/dev/null
  echo "  -> Created BigQuery dataset ${PROJECT_ID}:${BQ_DATASET}"
else
  echo "  -> BigQuery dataset ${PROJECT_ID}:${BQ_DATASET} already exists."
fi

BQ_TBL_HTTP="$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://bigquery.googleapis.com/bigquery/v2/projects/${PROJECT_ID}/datasets/${BQ_DATASET}/tables/${BQ_TABLE}")"
if [[ "${BQ_TBL_HTTP}" != "200" ]]; then
  curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    "https://bigquery.googleapis.com/bigquery/v2/projects/${PROJECT_ID}/datasets/${BQ_DATASET}/tables" \
    -d '{
      "tableReference": {
        "projectId": "'"${PROJECT_ID}"'",
        "datasetId": "'"${BQ_DATASET}"'",
        "tableId": "'"${BQ_TABLE}"'"
      },
      "timePartitioning": {
        "type": "DAY",
        "field": "timestamp"
      },
      "clustering": {
        "fields": ["ge_conversation_id", "antigravity_conversation_id"]
      },
      "schema": {
        "fields": [
          {"name": "timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
          {"name": "ge_conversation_id", "type": "STRING", "mode": "NULLABLE"},
          {"name": "antigravity_conversation_id", "type": "STRING", "mode": "NULLABLE"},
          {"name": "request_invocation_id", "type": "STRING", "mode": "NULLABLE"},
          {"name": "user_id", "type": "STRING", "mode": "NULLABLE"},
          {"name": "turn_number", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "model", "type": "STRING", "mode": "NULLABLE"},
          {"name": "prompt_preview", "type": "STRING", "mode": "NULLABLE"},
          {"name": "request_prompt_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "request_cached_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "request_candidates_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "request_thoughts_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "request_total_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "conversation_prompt_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "conversation_cached_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "conversation_candidates_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "conversation_thoughts_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "conversation_total_tokens", "type": "INTEGER", "mode": "NULLABLE"},
          {"name": "subagent_usage_json", "type": "STRING", "mode": "NULLABLE"},
          {"name": "latency_ms", "type": "FLOAT", "mode": "NULLABLE"}
        ]
      }
    }' >/dev/null
  echo "  -> Created BigQuery table ${PROJECT_ID}:${BQ_DATASET}.${BQ_TABLE}"
else
  echo "  -> BigQuery table ${PROJECT_ID}:${BQ_DATASET}.${BQ_TABLE} already exists."
fi

# 4. Ensure Companion DataStore exists in Discovery Engine
echo "[3/8] Checking/creating Companion DataStore (${DS_ID})..."
DS_URL="${DE_API_BASE}/projects/${PROJECT_NUMBER}/locations/${DE_LOCATION}/collections/default_collection/dataStores/${DS_ID}"
DS_HTTP="$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${TOKEN}" -H "X-Goog-User-Project: ${PROJECT_ID}" "${DS_URL}")"
if [[ "${DS_HTTP}" != "200" ]]; then
  curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    "${DE_API_BASE}/projects/${PROJECT_NUMBER}/locations/${DE_LOCATION}/collections/default_collection/dataStores?dataStoreId=${DS_ID}" \
    -d '{
      "displayName": "Gemini Enterprise Companion DataStore",
      "industryVertical": "GENERIC",
      "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
      "contentConfig": "NO_CONTENT"
    }' >/dev/null
  echo "  -> Created DataStore ${DS_ID}."
else
  echo "  -> DataStore ${DS_ID} already exists."
fi

# 5. Ensure Gemini Enterprise Engine exists
echo "[4/8] Checking/creating Gemini Enterprise Engine (${ENGINE_ID})..."
ENG_URL="${DE_API_BASE}/projects/${PROJECT_NUMBER}/locations/${DE_LOCATION}/collections/default_collection/engines/${ENGINE_ID}"
ENG_HTTP="$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${TOKEN}" -H "X-Goog-User-Project: ${PROJECT_ID}" "${ENG_URL}")"
if [[ "${ENG_HTTP}" != "200" ]]; then
  curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    "${DE_API_BASE}/projects/${PROJECT_NUMBER}/locations/${DE_LOCATION}/collections/default_collection/engines?engineId=${ENGINE_ID}" \
    -d '{
      "displayName": "Gemini Enterprise AI Workspace",
      "solutionType": "SOLUTION_TYPE_SEARCH",
      "industryVertical": "GENERIC",
      "appType": "APP_TYPE_INTRANET",
      "dataStoreIds": ["'"${DS_ID}"'"],
      "searchEngineConfig": {
        "searchTier": "SEARCH_TIER_ENTERPRISE",
        "searchAddOns": ["SEARCH_ADD_ON_LLM"]
      },
      "features": {
        "model-selector": "FEATURE_STATE_ON",
        "agent-gallery": "FEATURE_STATE_ON",
        "agent-sharing-without-admin-approval": "FEATURE_STATE_ON",
        "disable-agent-sharing": "FEATURE_STATE_OFF",
        "no-code-agent-builder": "FEATURE_STATE_ON",
        "enable-end-user-sharing-with-groups": "FEATURE_STATE_OFF"
      },
      "observabilityConfig": {
        "observabilityEnabled": true
      },
      "marketplaceAgentVisibility": "SHOW_ALL_AGENTS"
    }' >/dev/null
  echo "  -> Created Gemini Enterprise Engine ${ENGINE_ID}."
else
  echo "  -> Gemini Enterprise Engine ${ENGINE_ID} already exists."
fi

# Define Target Agent Fleet (format: AGENT_ID|SERVICE_NAME|DISPLAY_NAME|DESCRIPTION|ICON_KEY)
FLEET_SPECS=(
  "antigravity|gemini-antigravity-demo|Antigravity|Autonomous AI software engineer, interactive BRD agent designer (Options 1/2/3), and dynamic tool synthesizer powered by the Google Antigravity SDK harness inside ADK — with workspace file tools, shell execution, web search, sub-agents, image generation, and Veo 3.1 video generation.|antigravity"
)
if [[ "${DEPLOY_SHOWCASE_AGENTS}" == "true" ]]; then
  FLEET_SPECS+=(
    "trailer-director|antigravity-trailer-director|🎬 Trailer Director|Linear 3-stage movie trailer studio: writes a dramatic 3-beat script & voiceover, generates high-contrast cinema poster art, and renders a 4-second 16:9 Veo 3.1 trailer video clip.|trailer"
    "shark-tank-panel|antigravity-shark-tank-panel|🦈 Shark Tank Panel|Parallel 3-investor VC pitch panel: fans out simultaneously to Numbers Hawk (CFO), Hype Visionary (Brand VC), and Skeptical Customer, then synthesizes a weighted Deal or No-Deal term sheet.|shark"
    "food-crawl-planner|antigravity-food-crawl-planner|🍜 Food Crawl Planner|Hourglass street-food crawl planner: researches live neighborhood spots, runs a deterministic constraint solver on walking route & budget, and publishes an .ics calendar, interactive map, and watercolor postcard.|food"
    "arcade-builder|antigravity-arcade-builder|🕹️ Arcade Builder|Self-healing HTML5 retro arcade studio: writes a playable single-file HTML5 canvas game, validates DOM/JS/controls in a generator-verifier loop until 0 errors, and paints 16-bit box art.|arcade"
    "six-degrees-detective|antigravity-six-degrees-detective|🧭 Six Degrees Detective|Dynamic tree-search pop-culture detective: explores multi-hop factual links between any two topics via live web search, prunes dead-end branches, and verifies the shortest real-world chain.|detective"
  )
fi

ALLOWED_DISPLAY_NAMES_JSON="$(printf '%s\n' "${FLEET_SPECS[@]}" | python3 -c '
import json, sys
names = [line.strip().split("|")[2] for line in sys.stdin if line.strip()]
print(json.dumps(names))
')"

# 6. Optionally clean up stale custom agents in Gemini Enterprise if PURGE_OTHER_AGENTS=true
GEMINI_ENTERPRISE_APP_ID="projects/${PROJECT_NUMBER}/locations/${DE_LOCATION}/collections/default_collection/engines/${ENGINE_ID}"
if [[ "${PURGE_OTHER_AGENTS}" == "true" ]]; then
  echo "[5/8] Cleaning up stale registered agents in Gemini Enterprise (${ENGINE_ID})..."
  TOKEN="$(gcloud auth print-access-token --quiet)"
  EXISTING_AGENTS_JSON="$(curl -s \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    "${DE_API_BASE}/${GEMINI_ENTERPRISE_APP_ID}/assistants/default_assistant/agents")"

  OTHER_AGENT_NAMES="$(python3 -c '
import json, sys
data = json.loads(sys.argv[1]) if sys.argv[1].strip() else {}
allowed = set(json.loads(sys.argv[2]))
for ag in data.get("agents", []):
    disp = ag.get("displayName", "")
    name = ag.get("name", "")
    is_custom = any(k in ag for k in ("adkAgentDefinition", "a2aAgentDefinition", "lowCodeAgentDefinition"))
    if name and disp not in allowed and (is_custom or disp.startswith("Demo ")):
        print(f"{name}|{disp}")
' "${EXISTING_AGENTS_JSON}" "${ALLOWED_DISPLAY_NAMES_JSON}")"

  if [[ -n "${OTHER_AGENT_NAMES}" ]]; then
    while IFS='|' read -r AG_NAME AG_DISP; do
      [[ -z "${AG_NAME}" ]] && continue
      echo "  -> Deleting stale registered agent: ${AG_DISP} (${AG_NAME})..."
      DEL_HTTP="$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "X-Goog-User-Project: ${PROJECT_ID}" \
        "${DE_API_BASE}/${AG_NAME}")"
      echo "     HTTP ${DEL_HTTP}"
    done <<< "${OTHER_AGENT_NAMES}"
  else
    echo "  -> No stale registered agents found."
  fi
else
  echo "[5/8] Preserving existing registered agents in ${ENGINE_ID} (PURGE_OTHER_AGENTS=false)..."
fi

# Ensure built-in 1P Google agents ('Deep Research' & 'Idea Generation') exist so
# the Gemini Enterprise left sidebar fallback & 'Made by Google' gallery are populated.
echo "  -> Verifying built-in 1P Google agents (deep_research & default_idea_generation)..."
TOKEN="$(gcloud auth print-access-token --quiet)"
python3 -c '
import json, sys, urllib.request, urllib.error

api_base, app_id, project_id, token = sys.argv[1:5]
base = f"{api_base}/{app_id}/assistants/default_assistant"
headers = {
    "Authorization": f"Bearer {token}",
    "X-Goog-User-Project": project_id,
    "Content-Type": "application/json",
}

dr_desc = (
    "This agent is a specialized agent that gathers, analyzes, and understands "
    "information from internal and external sources. It generates a plan, an "
    "in-depth report, and a summary."
)
ig_desc = (
    "This agent is a specialized agent that helps with innovation and "
    "problem-solving for enterprise users by combining advanced AI with a "
    "unique tournament-style competition framework to generate and rank ideas"
)

builtin_specs = [
    ("deep_research", {
        "displayName": "Deep Research",
        "description": dr_desc,
        "managedAgentDefinition": {
            "toolSettings": {"toolDescription": dr_desc},
            "researchAssistantAgentConfig": {"supportLroQueries": True},
        },
        "longRunningOperationsEnabled": True,
        "sharingConfig": {"scope": "ALL_USERS"},
        "observabilityConfig": {"observabilityEnabled": True},
    }),
    ("default_idea_generation", {
        "displayName": "Idea Generation",
        "description": ig_desc,
        "managedAgentDefinition": {
            "toolSettings": {"toolDescription": ig_desc},
            "ideaGenerationAgentConfig": {},
        },
        "sharingConfig": {"scope": "ALL_USERS"},
    }),
]

for agent_id, payload in builtin_specs:
    get_req = urllib.request.Request(f"{base}/agents/{agent_id}", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(get_req, timeout=10):
            print(f"     [OK] Built-in 1P agent {agent_id} exists.")
            continue
    except urllib.error.HTTPError as e:
        if e.code != 404:
            continue
    create_req = urllib.request.Request(
        f"{base}/agents?agentId={agent_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(create_req, timeout=15):
            disp = payload["displayName"]
            print(f"     [RESTORED] Built-in 1P agent {agent_id} ({disp}).")
    except urllib.error.HTTPError as e:
        print(f"     [WARN] Could not create {agent_id}: HTTP {e.code}")
' "${DE_API_BASE}" "${GEMINI_ENTERPRISE_APP_ID}" "${PROJECT_ID}" "${TOKEN}"

# 7. Install dependencies & deploy ADK >2.0 Agent Fleet concurrently to Vertex AI Agent Runtime
echo "[6/8] Deploying ${#FLEET_SPECS[@]} Agent(s) concurrently to Vertex AI Agent Runtime (${RUNTIME_REGION})..."
cd "${DEMO_DIR}"
export UV_DEFAULT_INDEX="https://pypi.org/simple"

run_agents_cli() {
  local AGENTS_PY
  AGENTS_PY="$(head -n1 "$(command -v agents-cli)" | sed 's/^#!//')"
  "${AGENTS_PY}" -c '
import datetime, os, subprocess, sys, google.auth
from google.oauth2.credentials import Credentials

class _GcloudImpersonatedCredentials(Credentials):
    def __init__(self, quota_project_id="gemini-enterprise-demo-cb"):
        tok = subprocess.check_output(["gcloud", "auth", "print-access-token", "--quiet"], text=True).strip()
        exp = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(minutes=55)
        super().__init__(token=tok, quota_project_id=quota_project_id, expiry=exp)

    def refresh(self, request):
        self.token = subprocess.check_output(["gcloud", "auth", "print-access-token", "--quiet"], text=True).strip()
        self.expiry = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(minutes=55)

def _patched_default(scopes=None, request=None, quota_project_id=None, default_scopes=None):
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT", "gemini-enterprise-demo-cb")
    return _GcloudImpersonatedCredentials(quota_project_id=quota_project_id or proj), proj

google.auth.default = _patched_default
google.auth._default.default = _patched_default

from google.agents.cli.main import main
sys.argv = ["agents-cli"] + sys.argv[1:]
sys.exit(main())
' "$@"
}

agents-cli install

declare -a OP_RECORDS=()
for SPEC in "${FLEET_SPECS[@]}"; do
  IFS='|' read -r AG_ID SVC_NAME DISP_NAME DESC ICON_KEY <<< "${SPEC}"
  # Reuse an in-flight LRO if one is already running for SVC_NAME
  EXISTING_OP="$(python3 -c '
import json, subprocess, sys, urllib.request
region, project_id, project_number, svc_name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
tok = subprocess.check_output(["gcloud", "auth", "print-access-token", "--quiet"], text=True).strip()
headers = {"Authorization": f"Bearer {tok}", "X-Goog-User-Project": project_id}
url = f"https://{region}-aiplatform.googleapis.com/v1beta1/projects/{project_number}/locations/{region}/reasoningEngines"
try:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        engines = json.loads(r.read().decode("utf-8")).get("reasoningEngines", [])
    for eng in engines:
        if eng.get("displayName") == svc_name:
            re_name = eng["name"]
            ops_url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{re_name}/operations"
            with urllib.request.urlopen(urllib.request.Request(ops_url, headers=headers), timeout=20) as r2:
                ops = json.loads(r2.read().decode("utf-8")).get("operations", [])
            for op in ops:
                if not op.get("done", False):
                    print(op["name"])
                    sys.exit(0)
except Exception:
    pass
' "${RUNTIME_REGION}" "${PROJECT_ID}" "${PROJECT_NUMBER}" "${SVC_NAME}")"

  if [[ -n "${EXISTING_OP}" ]]; then
    echo "  -> Adopting in-flight Agent Runtime LRO for ${DISP_NAME} (${SVC_NAME}): ${EXISTING_OP}"
    OP_RECORDS+=("${AG_ID}|${SVC_NAME}|${EXISTING_OP}")
    continue
  fi

  if [[ "${SKIP_RUNTIME_DEPLOY:-false}" == "true" ]]; then
    EXISTING_RE="$(python3 -c '
import json, subprocess, sys, urllib.request
region, project_id, project_number, svc_name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
tok = subprocess.check_output(["gcloud", "auth", "print-access-token", "--quiet"], text=True).strip()
headers = {"Authorization": f"Bearer {tok}", "X-Goog-User-Project": project_id}
url = f"https://{region}-aiplatform.googleapis.com/v1beta1/projects/{project_number}/locations/{region}/reasoningEngines"
with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
    engines = json.loads(r.read().decode("utf-8")).get("reasoningEngines", [])
for eng in engines:
    if eng.get("displayName") == svc_name:
        print(eng["name"])
        sys.exit(0)
' "${RUNTIME_REGION}" "${PROJECT_ID}" "${PROJECT_NUMBER}" "${SVC_NAME}")"
    if [[ -n "${EXISTING_RE}" ]]; then
      echo "  -> Reusing ready ReasoningEngine for ${DISP_NAME}: ${EXISTING_RE}"
      OP_RECORDS+=("${AG_ID}|${SVC_NAME}|READY:${EXISTING_RE}")
      continue
    fi
  fi

  echo "  -> Starting async Agent Runtime deploy for ${DISP_NAME} (service=${SVC_NAME}, target=${AG_ID})..."
  python3 -c '
import json, os, sys
p = sys.argv[1]
if os.path.isfile(p):
    d = json.load(open(p))
    d.pop("pending_operation", None)
    json.dump(d, open(p, "w"), indent=2)
' "${DEMO_DIR}/deployment_metadata.json"
  DEPLOY_OUT="$(run_agents_cli deploy \
    --project "${PROJECT_ID}" \
    --region "${RUNTIME_REGION}" \
    --service-name "${SVC_NAME}" \
    --service-account "${SA_EMAIL}" \
    --min-instances 1 \
    --no-wait \
    --update-env-vars "ANTIGRAVITY_TARGET_AGENT_ID=${AG_ID},GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true,ANTIGRAVITY_TELEMETRY_BUCKET=${TELEMETRY_BUCKET},LOGS_BUCKET_NAME=${TELEMETRY_BUCKET},SHARED_AGENT_BUCKET=${SHARED_AGENT_BUCKET},ANTIGRAVITY_BQ_DATASET=${BQ_DATASET},ANTIGRAVITY_BQ_TABLE=${BQ_TABLE}" \
    --no-confirm-project 2>&1)"
  OP_NAME="$(python3 -c '
import json, os, re, sys
meta_file = sys.argv[1]
out = sys.argv[2]
if os.path.isfile(meta_file):
    try:
        data = json.load(open(meta_file))
        op = (data.get("pending_operation") or {}).get("operation_name")
        if op:
            print(op)
            sys.exit(0)
    except Exception:
        pass
m = re.search(r"(projects/[^/\s\"]+/locations/[^/\s\"]+(?:/reasoningEngines/[0-9]+)?/operations/[0-9]+)", out)
if m:
    print(m.group(1))
' "${DEMO_DIR}/deployment_metadata.json" "${DEPLOY_OUT}")"
  if [[ -z "${OP_NAME}" ]]; then
    echo "ERROR: Failed to extract Agent Runtime LRO name for ${SVC_NAME}:" >&2
    echo "${DEPLOY_OUT}" >&2
    exit 1
  fi
  echo "     Started LRO: ${OP_NAME}"
  OP_RECORDS+=("${AG_ID}|${SVC_NAME}|${OP_NAME}")
done

echo "  -> Polling ${#OP_RECORDS[@]} concurrent Vertex AI Agent Runtime build/deploy operations..."
DEPLOYED_MAP_JSON="$(python3 -c '
import json, re, subprocess, sys, time, urllib.request

region = sys.argv[1]
project_id = sys.argv[2]
project_number = sys.argv[3]
records = [r.split("|", 2) for r in sys.argv[4:]]

def get_token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token", "--quiet"], text=True).strip()

token = get_token()
last_tok_refresh = time.monotonic()
pending = {}
completed = {}
for ag_id, svc, op in records:
    if op.startswith("READY:"):
        re_name = re.sub(r"^projects/[^/]+/", f"projects/{project_number}/", op[len("READY:"):])
        completed[ag_id] = re_name
    else:
        pending[ag_id] = (svc, op)

deadline = time.monotonic() + 1200.0

while pending and time.monotonic() < deadline:
    if time.monotonic() - last_tok_refresh > 240.0:
        token = get_token()
        last_tok_refresh = time.monotonic()
    for ag_id, (svc, op) in list(pending.items()):
        url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{op}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "X-Goog-User-Project": project_id,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("done"):
            if "error" in data:
                err_str = json.dumps(data["error"])
                sys.stderr.write(f"ERROR deploying {svc} ({ag_id}): {err_str}\n")
                sys.exit(1)
            re_name = data.get("response", {}).get("name") or op.split("/operations/")[0]
            re_name = re.sub(r"^projects/[^/]+/", f"projects/{project_number}/", re_name)
            sys.stderr.write(f"     [READY] {svc} -> {re_name}\n")
            completed[ag_id] = re_name
            del pending[ag_id]
    if pending:
        rem = ", ".join(pending.keys())
        sys.stderr.write(f"     ... waiting on {len(pending)} operation(s): {rem}\n")
        time.sleep(12.0)

if pending:
    sys.stderr.write(f"ERROR: Timed out waiting for operations: {pending}\n")
    sys.exit(1)

print(json.dumps(completed))
' "${RUNTIME_REGION}" "${PROJECT_ID}" "${PROJECT_NUMBER}" "${OP_RECORDS[@]}")"

# Persist root Antigravity reasoning engine ID back to deployment_metadata.json
python3 -c '
import datetime, json, sys
meta_path, deployed_json = sys.argv[1], sys.argv[2]
deployed = json.loads(deployed_json)
root_re = deployed.get("antigravity")
if root_re:
    meta = {
        "remote_agent_runtime_id": root_re,
        "deployment_target": "agent_runtime",
        "is_a2a": True,
        "language": "python",
        "agent_directory": "app",
        "deployment_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
' "${DEMO_DIR}/deployment_metadata.json" "${DEPLOYED_MAP_JSON}"

# 8. Publish All Deployed Agents to Gemini Enterprise & Share with ALL_USERS
echo "[7/8] Publishing ${#FLEET_SPECS[@]} Agent(s) to Gemini Enterprise (${ENGINE_ID})..."
for SPEC in "${FLEET_SPECS[@]}"; do
  IFS='|' read -r AG_ID SVC_NAME DISP_NAME DESC ICON_KEY <<< "${SPEC}"
  RE_RESOURCE="$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "${DEPLOYED_MAP_JSON}" "${AG_ID}")"
  echo "  -> Publishing ${DISP_NAME} (${RE_RESOURCE})..."
  run_agents_cli publish gemini-enterprise \
    --registration-type adk \
    --agent-runtime-id "${RE_RESOURCE}" \
    --gemini-enterprise-app-id "${GEMINI_ENTERPRISE_APP_ID}" \
    --display-name "${DISP_NAME}" \
    --description "${DESC}" \
    --tool-description "${DESC}" \
    --project-id "${PROJECT_ID}" \
    --project-number "${PROJECT_NUMBER}"
done

echo "[8/8] Applying SVG branding & sharingConfig.scope=ALL_USERS across all ${#FLEET_SPECS[@]} Agent(s)..."
TOKEN="$(gcloud auth print-access-token --quiet)"
AGENTS_LIST_JSON="$(curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${DE_API_BASE}/${GEMINI_ENTERPRISE_APP_ID}/assistants/default_assistant/agents")"

get_icon_data_uri() {
  local key="$1"
  python3 -c '
import base64, sys
key = sys.argv[1]
svgs = {
    "antigravity": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" fill="none" viewBox="-8 -8 56 56"><rect x="-8" y="-8" width="56" height="56" rx="28" fill="#202124"/><mask id="a" width="32" height="32" x="4" y="4" maskUnits="userSpaceOnUse" style="mask-type:alpha"><path fill="#000" d="M33.002 34.73c1.786 1.429 4.466.476 2.01-2.145C27.641 24.963 29.204 4 20.048 4S12.456 24.963 5.086 32.585c-2.68 2.859.224 3.574 2.01 2.144 6.923-5.002 6.477-13.816 12.953-13.816s6.03 8.814 12.953 13.816"/></mask><g mask="url(#a)"><circle cx="14" cy="10" r="14" fill="#3186FF"/><circle cx="28" cy="14" r="13" fill="#FC413D"/><circle cx="8" cy="24" r="13" fill="#00B95C"/><circle cx="20" cy="6" r="11" fill="#FBBC04"/></g></svg>""",
    "trailer": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#1E1B4B"/><rect x="14" y="24" width="36" height="24" rx="4" fill="#F43F5E"/><path d="M14 20h36l-4-6H18z" fill="#FDA4AF"/><polygon points="29,30 29,42 40,36" fill="#FFFFFF"/></svg>""",
    "shark": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#0C4A6E"/><path d="M14 44c10-2 14-14 22-24 0 10 4 18 14 24H14z" fill="#38BDF8"/><path d="M12 48h40" stroke="#BAE6FD" stroke-width="4" stroke-linecap="round"/></svg>""",
    "food": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#7C2D12"/><path d="M14 32h36c0 11-8 18-18 18S14 43 14 32z" fill="#FBBF24"/><path d="M22 26c0-4 3-4 3-8M32 26c0-4 3-4 3-8M42 26c0-4 3-4 3-8" stroke="#FDE68A" stroke-width="3" stroke-linecap="round" fill="none"/></svg>""",
    "arcade": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#3B0764"/><rect x="14" y="22" width="36" height="22" rx="8" fill="#A855F7"/><path d="M24 29v8M20 33h8" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/><circle cx="39" cy="31" r="2.8" fill="#FDE047"/><circle cx="44" cy="35" r="2.8" fill="#4ADE80"/></svg>""",
    "detective": """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#064E3B"/><circle cx="32" cy="32" r="18" stroke="#34D399" stroke-width="3.5" fill="#065F46"/><polygon points="32,18 37,32 32,46 27,32" fill="#6EE7B7"/><polygon points="32,18 37,32 27,32" fill="#F87171"/></svg>""",
}
svg = svgs.get(key, svgs["antigravity"])
print("data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii"))
' "${key}"
}

for SPEC in "${FLEET_SPECS[@]}"; do
  IFS='|' read -r AG_ID SVC_NAME DISP_NAME DESC ICON_KEY <<< "${SPEC}"
  RE_RESOURCE="$(python3 -c 'import json, sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "${DEPLOYED_MAP_JSON}" "${AG_ID}")"
  AGENT_RESOURCE_NAME="$(python3 -c '
import json, sys
data = json.loads(sys.argv[1]) if sys.argv[1].strip() else {}
disp, re_res = sys.argv[2], sys.argv[3]
for ag in data.get("agents", []):
    re_cfg = ag.get("adkAgentDefinition", {}).get("provisionedReasoningEngine", {}).get("reasoningEngine", "")
    if re_cfg == re_res or ag.get("displayName") == disp:
        print(ag["name"])
        break
' "${AGENTS_LIST_JSON}" "${DISP_NAME}" "${RE_RESOURCE}")"

  if [[ -n "${AGENT_RESOURCE_NAME}" ]]; then
    ICON_URI="$(get_icon_data_uri "${ICON_KEY}")"
    PATCH_BODY="$(python3 -c '
import json, sys
print(json.dumps({
    "displayName": sys.argv[1],
    "description": sys.argv[2],
    "icon": {"content": sys.argv[3]},
    "sharingConfig": {"scope": "ALL_USERS"},
}))
' "${DISP_NAME}" "${DESC}" "${ICON_URI}")"
    curl -s -X PATCH \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "X-Goog-User-Project: ${PROJECT_ID}" \
      -H "Content-Type: application/json" \
      "${DE_API_BASE}/${AGENT_RESOURCE_NAME}?updateMask=displayName,description,icon,sharingConfig" \
      -d "${PATCH_BODY}" >/dev/null
    echo "  -> Shared ${DISP_NAME} (${AGENT_RESOURCE_NAME}) with ALL_USERS."
  else
    echo "  -> WARNING: Could not locate registered agent for ${DISP_NAME} in list response."
  fi
done

"${SCRIPT_DIR}/pin_agents_lhs.sh" || true

echo "=============================================================================="
echo "✅ Antigravity Agent Creator Fleet Provisioning Complete!"
echo "   Query token usage anytime with: ./scripts/query_telemetry.sh"
echo "=============================================================================="
