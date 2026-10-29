#!/usr/bin/env bash
# ==============================================================================
# Programmatically Pin Antigravity & Showcase Agents on Gemini Enterprise LHS
# (`scripts/pin_agents_lhs.sh`)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-gemini-enterprise-demo-cb}"
LOCATION="${LOCATION:-global}"
ENGINE_ID="${ENGINE_ID:-prudential-agency-engine}"
SA_EMAIL="gemini-enterprise-admin@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="${HOME}/.config/gcloud/gemini-enterprise-admin-key.json"

if [[ -f "${KEY_FILE}" ]] && grep -q '"type": *"service_account"' "${KEY_FILE}" 2>/dev/null; then
  gcloud config unset auth/impersonate_service_account --quiet >/dev/null 2>&1 || true
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_FILE}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
else
  gcloud config set auth/impersonate_service_account "${SA_EMAIL}" --quiet >/dev/null 2>&1 || true
fi

PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')}"
ENGINE_NAME="projects/${PROJECT_NUMBER}/locations/${LOCATION}/collections/default_collection/engines/${ENGINE_ID}"

if [[ "${LOCATION}" == "global" ]]; then
  DE_API_BASE="https://discoveryengine.googleapis.com/v1alpha"
else
  DE_API_BASE="https://${LOCATION}-discoveryengine.googleapis.com/v1alpha"
fi

SA_TOKEN="$(gcloud auth print-access-token --quiet)"

echo ">>> Fetching registered agents from ${ENGINE_ID}..."
AGENTS_JSON="$(curl -s "${DE_API_BASE}/${ENGINE_NAME}/assistants/default_assistant/agents" \
  -H "Authorization: Bearer ${SA_TOKEN}" \
  -H "X-Goog-User-Project: ${PROJECT_ID}")"

# Order so that the LAST :addUserAnnotation call gets the newest UpdateTime (top of LHS):
# Top-to-bottom desired order:
#   1. Antigravity
#   2. 🎬 Trailer Director
#   3. 🦈 Shark Tank Panel
#   4. 🍜 Food Crawl Planner
#   5. 🕹️ Arcade Builder
#   6. 🧭 Six Degrees Detective
REVERSE_AGENTS_JS="$(python3 -c '
import json, sys

data = json.loads(sys.argv[1]) if sys.argv[1].strip() else {}
priority = {
    "Antigravity": 0,
    "🎬 Trailer Director": 1,
    "🦈 Shark Tank Panel": 2,
    "🍜 Food Crawl Planner": 3,
    "🕹️ Arcade Builder": 4,
    "🧭 Six Degrees Detective": 5,
}
items = []
for ag in data.get("agents", []):
    is_custom = any(k in ag for k in ("adkAgentDefinition", "a2aAgentDefinition", "lowCodeAgentDefinition"))
    disp = ag.get("displayName", "")
    if is_custom or disp == "Antigravity":
        items.append({"name": ag["name"], "displayName": disp})

items.sort(key=lambda x: (priority.get(x["displayName"], 99), x["displayName"]), reverse=True)
print(json.dumps(items))
' "${AGENTS_JSON}")"

echo ">>> Target agents to pin on LHS nav panel (bottom -> top pin order):"
echo "${REVERSE_AGENTS_JS}" | jq -r '.[] | "  - \(.displayName) (\(.name))"'

if [[ $# -gt 0 ]]; then
  TARGET_USERS=("$@")
else
  TARGET_USERS=(
    "admin@cbribiescas.altostrat.com"
    "cbribiescas@gcp.altostrat.com"
    "carlos@cbribiescas.altostrat.com"
    "indrajit@cbribiescas.altostrat.com"
    "jye@cbribiescas.altostrat.com"
    "satish@cbribiescas.altostrat.com"
    "vivek@cbribiescas.altostrat.com"
  )
fi

for USER_EMAIL in "${TARGET_USERS[@]}"; do
  echo ""
  echo ">>> Attempting programmatic LHS pin for user: ${USER_EMAIL}..."
  gcloud config unset auth/impersonate_service_account --quiet >/dev/null 2>&1 || true
  USER_TOKEN="$(timeout 5s gcloud auth print-access-token "${USER_EMAIL}" --quiet 2>/dev/null || true)"
  if [[ -z "${USER_TOKEN}" ]]; then
    echo "  -> [SKIPPED] No active local gcloud token for ${USER_EMAIL}."
    continue
  fi

  EXISTING_PINS="$(curl -s \
    -H "Authorization: Bearer ${USER_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    "${DE_API_BASE}/managed/${ENGINE_NAME}/userAnnotations?filter=annotationType%3D%22ANNOTATION_TYPE_PIN%22")"

  if [[ "$(echo "${EXISTING_PINS}" | jq -r '.userAnnotations | length')" == "0" ]]; then
    curl -s -X POST \
      -H "Authorization: Bearer ${USER_TOKEN}" \
      -H "X-Goog-User-Project: ${PROJECT_ID}" \
      -H "Content-Type: application/json" \
      "${DE_API_BASE}/${ENGINE_NAME}/assistants/default_assistant:streamAssist" \
      -d '{"query":{"text":"hi"}}' >/dev/null 2>&1 || true
  fi

  while IFS= read -r PIN_ITEM; do
    [[ -z "${PIN_ITEM}" ]] && continue
    curl -s -X POST \
      -H "Authorization: Bearer ${USER_TOKEN}" \
      -H "X-Goog-User-Project: ${PROJECT_ID}" \
      -H "Content-Type: application/json" \
      "${DE_API_BASE}/managed/${ENGINE_NAME}:removeUserAnnotation" \
      -d "${PIN_ITEM}" >/dev/null 2>&1 || true
  done < <(echo "${EXISTING_PINS}" | jq -c '.userAnnotations[]? | {annotatedResourceType, annotatedResourceName, annotationType, pinnedAnnotation}')

  while IFS= read -r AGENT_ITEM; do
    [[ -z "${AGENT_ITEM}" ]] && continue
    AG_NAME="$(echo "${AGENT_ITEM}" | jq -r '.name')"
    AG_DISP="$(echo "${AGENT_ITEM}" | jq -r '.displayName')"
    PIN_RESP="$(curl -s -X POST \
      -H "Authorization: Bearer ${USER_TOKEN}" \
      -H "X-Goog-User-Project: ${PROJECT_ID}" \
      -H "Content-Type: application/json" \
      "${DE_API_BASE}/managed/${ENGINE_NAME}:addUserAnnotation" \
      -d '{
        "annotatedResourceType": "projects/locations/collections/engines/assistants/agents",
        "annotatedResourceName": "'"${AG_NAME}"'",
        "annotationType": "ANNOTATION_TYPE_PIN",
        "pinnedAnnotation": {
          "displayName": "'"${AG_DISP}"'"
        }
      }')"
    if echo "${PIN_RESP}" | jq -e '.annotatedResourceName' >/dev/null 2>&1; then
      echo "  -> [PINNED] ${AG_DISP} for ${USER_EMAIL}"
    else
      echo "  -> [WARN] Failed to pin ${AG_DISP} for ${USER_EMAIL}: ${PIN_RESP}"
    fi
  done < <(echo "${REVERSE_AGENTS_JS}" | jq -c '.[]')
done

if [[ -f "${KEY_FILE}" ]] && grep -q '"type": *"service_account"' "${KEY_FILE}" 2>/dev/null; then
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_FILE}" --project="${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
else
  gcloud config set auth/impersonate_service_account "${SA_EMAIL}" --quiet >/dev/null 2>&1 || true
fi

cat <<EOF

==============================================================================
 BROWSER FALLBACK (DevTools Console 1-Liner on the open Gemini Enterprise tab):
==============================================================================
(async () => {
  const app = document.querySelector('ucs-standalone-app');
  const auth = app.authService;
  const agents = ${REVERSE_AGENTS_JS};
  for (const a of agents) {
    await auth.widgetCreateUserAnnotation({
      annotatedResourceType: 'projects/locations/collections/engines/assistants/agents',
      annotationType: 'ANNOTATION_TYPE_PIN',
      annotatedResourceName: a.name,
      pinnedAnnotation: { displayName: a.displayName }
    });
  }
  await app.agentService.refreshPinnedAgents();
  console.log('Pinned Antigravity & Showcase Agents on the LHS!');
})();
==============================================================================
EOF
