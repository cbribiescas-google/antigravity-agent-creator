#!/usr/bin/env bash
# ==============================================================================
# Bootstrap GCP Project & Full-Rights Service Account for Antigravity Agent Creator
# (`scripts/bootstrap_project_and_sa.sh`)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-gemini-enterprise-demo-cb}"
PROJECT_NAME="${PROJECT_NAME:-Gemini Enterprise Demo}"
SA_NAME="${SA_NAME:-gemini-enterprise-admin}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_PATH="${KEY_PATH:-$HOME/.config/gcloud/${SA_NAME}-key.json}"
DOMAIN="${DOMAIN:-cbribiescas.altostrat.com}"
ADMIN_USERS="${ADMIN_USERS:-admin@cbribiescas.altostrat.com cbribiescas@gcp.altostrat.com}"

echo "=== 1. Verifying active gcloud authentication ==="
ACTIVE_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
echo "Current account: ${ACTIVE_ACCOUNT}"

if ! gcloud auth print-access-token >/dev/null 2>&1; then
  echo "Session expired. Launching gcloud auth login..."
  gcloud auth login
fi

echo "=== 2. Creating or Verifying GCP Project: ${PROJECT_ID} ==="
if gcloud projects describe "${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Project ${PROJECT_ID} already exists."
else
  echo "Creating project ${PROJECT_ID}..."
  ORG_ID="$(gcloud organizations list --format='value(ID)' --limit=1 2>/dev/null || true)"
  if [[ -n "${ORG_ID}" ]]; then
    gcloud projects create "${PROJECT_ID}" --name="${PROJECT_NAME}" --organization="${ORG_ID}"
  else
    gcloud projects create "${PROJECT_ID}" --name="${PROJECT_NAME}"
  fi
fi

gcloud config set project "${PROJECT_ID}"

echo "=== 3. Linking Billing Account (if not already linked) ==="
BILLING_ENABLED="$(gcloud beta billing projects describe "${PROJECT_ID}" --format='value(billingEnabled)' 2>/dev/null || echo 'false')"
if [[ "${BILLING_ENABLED}" != "True" && "${BILLING_ENABLED}" != "true" ]]; then
  BILLING_ACCOUNT="$(gcloud beta billing accounts list --filter='open=true' --format='value(ACCOUNT_ID)' --limit=1 2>/dev/null || true)"
  if [[ -n "${BILLING_ACCOUNT}" ]]; then
    echo "Linking billing account ${BILLING_ACCOUNT} to ${PROJECT_ID}..."
    gcloud beta billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT}"
  else
    echo "WARNING: No open billing account found automatically. Link billing manually if needed."
  fi
fi

echo "=== 4. Enabling Core APIs for Gemini Enterprise, Vertex AI Agent Runtime, Telemetry & Cloud Run ==="
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  discoveryengine.googleapis.com \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

echo "=== 5. Creating Service Account: ${SA_EMAIL} ==="
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Service account ${SA_EMAIL} already exists."
else
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Gemini Enterprise & Antigravity Full Admin SA" \
    --description="Full-rights automation service account for Antigravity Agent Creator and Gemini Enterprise" \
    --project="${PROJECT_ID}"
  sleep 5
fi

echo "=== 6. Granting Full Rights to ${SA_EMAIL} on ${PROJECT_ID} ==="
for ROLE in \
  "roles/owner" \
  "roles/editor" \
  "roles/resourcemanager.projectIamAdmin" \
  "roles/serviceusage.serviceUsageAdmin" \
  "roles/discoveryengine.admin" \
  "roles/aiplatform.admin" \
  "roles/aiplatform.user" \
  "roles/run.admin" \
  "roles/iam.serviceAccountUser" \
  "roles/iam.serviceAccountTokenCreator" \
  "roles/bigquery.admin" \
  "roles/bigquery.dataEditor" \
  "roles/bigquery.jobUser" \
  "roles/storage.admin" \
  "roles/storage.objectAdmin" \
  "roles/cloudbuild.builds.builder" \
  "roles/artifactregistry.admin" \
  "roles/cloudtrace.agent" \
  "roles/logging.logWriter"; do
  echo "Binding ${ROLE}..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null
done

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for ROLE in "roles/storage.admin" "roles/artifactregistry.writer" "roles/logging.logWriter"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null || true
done

for USER_EMAIL in "${ACTIVE_ACCOUNT}" ${ADMIN_USERS} "cbribiescas@google.com"; do
  [[ -z "${USER_EMAIL}" || "${USER_EMAIL}" == *"gserviceaccount.com"* ]] && continue
  gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --member="user:${USER_EMAIL}" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project="${PROJECT_ID}" \
    --quiet >/dev/null || true
  gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --member="user:${USER_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --project="${PROJECT_ID}" \
    --quiet >/dev/null || true
done

for USER_EMAIL in ${ADMIN_USERS}; do
  for ROLE in \
    "roles/discoveryengine.agentspaceUser" \
    "roles/discoveryengine.user" \
    "roles/discoveryengine.viewer" \
    "roles/aiplatform.user"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="user:${USER_EMAIL}" \
      --role="${ROLE}" \
      --condition=None \
      --quiet >/dev/null || true
  done
done

echo "=== 7. Configuring Persistent Authentication for ${SA_EMAIL} ==="
if [[ -s "${KEY_PATH}" ]] && grep -q '"type": *"service_account"' "${KEY_PATH}" 2>/dev/null; then
  echo "Service account key already exists at ${KEY_PATH}"
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_PATH}" --project="${PROJECT_ID}"
  cp "${KEY_PATH}" "$HOME/.config/gcloud/application_default_credentials.json"
elif gcloud iam service-accounts keys create "${KEY_PATH}" \
  --iam-account="${SA_EMAIL}" \
  --project="${PROJECT_ID}" 2>/dev/null; then
  chmod 600 "${KEY_PATH}"
  echo "Created service account key at ${KEY_PATH}"
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_PATH}" --project="${PROJECT_ID}"
  cp "${KEY_PATH}" "$HOME/.config/gcloud/application_default_credentials.json"
  echo "Activated ${SA_EMAIL} as default gcloud account and ADC credentials!"
else
  rm -f "${KEY_PATH}"
  echo "Key creation restricted by org policy; configuring service account impersonation for ${SA_EMAIL}..."
  gcloud config set auth/impersonate_service_account "${SA_EMAIL}"
fi

echo "=== Done! Active gcloud config: ==="
gcloud config list
