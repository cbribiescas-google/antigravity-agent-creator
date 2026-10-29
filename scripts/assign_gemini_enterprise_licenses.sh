#!/usr/bin/env bash
# ==============================================================================
# Assign Gemini Enterprise user licenses to every active user in a Cloud
# Identity / Workspace domain (idempotent).
# (`scripts/assign_gemini_enterprise_licenses.sh`)
#
# Usage:
#   ./scripts/assign_gemini_enterprise_licenses.sh [DOMAIN]
# Env overrides:
#   PROJECT_ID, LOCATION (default: global), LICENSE_CONFIG (default:
#   internal_gemini_ent_plus), EXTRA_USERS (space-separated extra principals)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-gemini-enterprise-demo-cb}"
LOCATION="${LOCATION:-global}"
LICENSE_CONFIG="${LICENSE_CONFIG:-internal_gemini_ent_plus}"
DOMAIN="${1:-cbribiescas.altostrat.com}"
EXTRA_USERS="${EXTRA_USERS:-cbribiescas@gcp.altostrat.com}"
USER_STORE="default_user_store"

if [[ "${LOCATION}" == "global" ]]; then
  DE_HOST="discoveryengine.googleapis.com"
else
  DE_HOST="${LOCATION}-discoveryengine.googleapis.com"
fi
BASE="https://${DE_HOST}/v1alpha/projects/${PROJECT_ID}/locations/${LOCATION}"
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
LICENSE_CONFIG_NAME="projects/${PROJECT_NUMBER}/locations/${LOCATION}/licenseConfigs/${LICENSE_CONFIG}"

echo ">>> Enabling Admin SDK API (for directory listing)..."
gcloud services enable admin.googleapis.com --project "${PROJECT_ID}" --quiet

ADMIN_TOKEN="$(CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT= gcloud auth print-access-token 2>/dev/null || true)"
SA_TOKEN="$(gcloud auth print-access-token 2>/dev/null)"

echo ">>> Listing active users in ${DOMAIN} (with fallback if not logged in as domain super-admin)..."
FALLBACK_USERS="admin@${DOMAIN} carlos@${DOMAIN} indrajit@${DOMAIN} jye@${DOMAIN} satish@${DOMAIN} vivek@${DOMAIN}"
USERS=""
if [[ -n "${ADMIN_TOKEN}" ]]; then
  USERS="$(curl -sf -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    "https://admin.googleapis.com/admin/directory/v1/users?domain=${DOMAIN}&maxResults=500&fields=users(primaryEmail,suspended)" 2>/dev/null \
    | python3 -c 'import sys,json; [print(u["primaryEmail"]) for u in json.load(sys.stdin).get("users",[]) if not u.get("suspended")]' 2>/dev/null || true)"
fi
if [[ -z "${USERS}" ]]; then
  echo "    (Directory API unavailable for current token; using known ${DOMAIN} user list)"
  USERS="${FALLBACK_USERS// /$'\n'}"
fi
USERS="$(printf '%s\n%s\n' "${USERS}" "${EXTRA_USERS// /$'\n'}" | sed '/^$/d' | sort -u)"

if [[ -z "${USERS}" ]]; then
  echo "!!! No users found for ${DOMAIN}; aborting." >&2
  exit 1
fi
echo "    Users: $(echo "${USERS}" | tr '\n' ' ')"

echo ">>> Configuring Identity Provider (GSUITE / Google Identity) in ${LOCATION}..."
curl -sf -X PATCH -H "Authorization: Bearer ${SA_TOKEN}" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" -H "Content-Type: application/json" \
  "${BASE}/aclConfig" \
  -d "{\"name\":\"projects/${PROJECT_ID}/locations/${LOCATION}/aclConfig\",\"idpConfig\":{\"idpType\":\"GSUITE\"}}" >/dev/null

echo ">>> Granting Gemini Enterprise & Vertex AI IAM roles to domain:${DOMAIN} and EXTRA_USERS..."
for ROLE in \
  roles/discoveryengine.agentspaceUser \
  roles/discoveryengine.user \
  roles/discoveryengine.viewer \
  roles/discoveryengine.notebookLmUser \
  roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="domain:${DOMAIN}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null || true
  for EXTRA_USER in ${EXTRA_USERS}; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="user:${EXTRA_USER}" \
      --role="${ROLE}" \
      --condition=None --quiet >/dev/null || true
  done
done

echo ">>> Verifying license config ${LICENSE_CONFIG_NAME}..."
curl -sf -H "Authorization: Bearer ${SA_TOKEN}" -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${BASE}/licenseConfigs/${LICENSE_CONFIG}" >/dev/null \
  || { echo "!!! License config not found in ${LOCATION}." >&2; exit 1; }

BODY="$(echo "${USERS}" | python3 -c '
import sys, json
cfg = sys.argv[1]
users = [u.strip() for u in sys.stdin if u.strip()]
print(json.dumps({
  "inlineSource": {
    "userLicenses": [{"userPrincipal": u, "licenseConfig": cfg} for u in users],
    "updateMask": "licenseConfig",
  }
}))' "${LICENSE_CONFIG_NAME}")"

echo ">>> Assigning ${LICENSE_CONFIG} licenses in ${LOCATION}..."
RESP="$(curl -s -X POST -H "Authorization: Bearer ${SA_TOKEN}" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" -H "Content-Type: application/json" \
  "${BASE}/userStores/${USER_STORE}:batchUpdateUserLicenses" -d "${BODY}")"
if echo "${RESP}" | grep -q '"error"'; then
  echo "!!! batchUpdateUserLicenses failed:" >&2
  echo "${RESP}" >&2
  exit 1
fi

echo ">>> Pruning duplicate non-${DOMAIN} user licenses..."
PRUNE_BODY="$(curl -sf -H "Authorization: Bearer ${SA_TOKEN}" -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${BASE}/userStores/${USER_STORE}/userLicenses?pageSize=200" \
  | python3 -c '
import sys, json
domain = sys.argv[1].lower()
extra = {u.strip().lower() for u in sys.argv[2].split() if u.strip()}
licenses = json.load(sys.stdin).get("userLicenses", [])
to_remove = []
for u in licenses:
    p = u.get("userPrincipal", "")
    pl = p.lower()
    if pl.endswith("@" + domain) or pl.endswith(".gserviceaccount.com") or pl in extra:
        continue
    to_remove.append({"userPrincipal": p, "licenseAssignmentState": "UNASSIGNED"})
if to_remove:
    print(json.dumps({
        "deleteUnassignedUserLicenses": True,
        "inlineSource": {
            "userLicenses": to_remove,
            "updateMask": "licenseAssignmentState",
        }
    }))
' "${DOMAIN}" "${EXTRA_USERS}")"

if [[ -n "${PRUNE_BODY}" ]]; then
  curl -sf -X POST -H "Authorization: Bearer ${SA_TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" -H "Content-Type: application/json" \
    "${BASE}/userStores/${USER_STORE}:batchUpdateUserLicenses" -d "${PRUNE_BODY}" >/dev/null
  echo "    Removed non-${DOMAIN} duplicate license assignments."
else
  echo "    No non-${DOMAIN} duplicate licenses found."
fi

echo ">>> Current license assignments (${LOCATION}):"
curl -sf -H "Authorization: Bearer ${SA_TOKEN}" -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "${BASE}/userStores/${USER_STORE}/userLicenses?pageSize=200" \
  | python3 -c 'import sys,json
for u in json.load(sys.stdin).get("userLicenses",[]):
    print("    %-45s %s" % (u.get("userPrincipal"), u.get("licenseAssignmentState")))'
echo ">>> Done."
