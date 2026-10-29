#!/usr/bin/env bash
# ==============================================================================
# Deploy Unified Single API Gateway & Live DAG Studio UI to Cloud Run
# (`scripts/deploy_studio_cloud_run.sh`)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-gemini-enterprise-demo-cb}}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${STUDIO_SERVICE_NAME:-antigravity-agent-creator-studio}"
SA_EMAIL="gemini-enterprise-admin@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="${HOME}/.config/gcloud/gemini-enterprise-admin-key.json"
DOMAIN="${DOMAIN:-cbribiescas.altostrat.com}"
EXTRA_USERS="${EXTRA_USERS:-cbribiescas@gcp.altostrat.com}"
TELEMETRY_BUCKET="${TELEMETRY_BUCKET:-${PROJECT_ID}-antigravity-telemetry}"
SHARED_AGENT_BUCKET="${SHARED_AGENT_BUCKET:-${PROJECT_ID}-agents-shared}"
BQ_DATASET="${BQ_DATASET:-antigravity_telemetry}"
BQ_TABLE="${BQ_TABLE:-token_usage}"

gcloud config set project "${PROJECT_ID}" --quiet
if [[ -f "${KEY_FILE}" ]] && grep -q '"type": *"service_account"' "${KEY_FILE}" 2>/dev/null; then
  gcloud config unset auth/impersonate_service_account --quiet >/dev/null 2>&1 || true
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_FILE}" --project="${PROJECT_ID}" --quiet
else
  gcloud config set auth/impersonate_service_account "${SA_EMAIL}" --quiet
fi

echo "=============================================================================="
echo " Deploying Antigravity Live DAG Studio UI & Single API Gateway to Cloud Run"
echo " Service: ${SERVICE_NAME} | Project: ${PROJECT_ID} | Region: ${REGION}"
echo "=============================================================================="

cd "${DEMO_DIR}"
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service-account "${SA_EMAIL}" \
  --memory "4Gi" \
  --cpu "2" \
  --timeout "900" \
  --min-instances "0" \
  --max-instances "10" \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,GOOGLE_API_USE_CLIENT_CERTIFICATE=false,ANTIGRAVITY_TELEMETRY_BUCKET=${TELEMETRY_BUCKET},SHARED_AGENT_BUCKET=${SHARED_AGENT_BUCKET},ANTIGRAVITY_BQ_DATASET=${BQ_DATASET},ANTIGRAVITY_BQ_TABLE=${BQ_TABLE}" \
  --quiet

for EXTRA_USER in ${EXTRA_USERS}; do
  gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --member="user:${EXTRA_USER}" \
    --role="roles/run.invoker" \
    --quiet >/dev/null || true
done

gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --member="domain:${DOMAIN}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null || true

STUDIO_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo "=============================================================================="
echo " ✅ Live DAG Studio UI & API Gateway Deployed: ${STUDIO_URL}/studio/"
echo "=============================================================================="
