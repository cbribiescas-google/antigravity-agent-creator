#!/usr/bin/env bash
# ==============================================================================
# Provision Private Shared GCS Bucket Accessible by All Agents
# (`scripts/provision_shared_agent_bucket.sh`)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-gemini-enterprise-demo-cb}}"
BUCKET_LOCATION="${BUCKET_LOCATION:-us-central1}"
SHARED_BUCKET_NAME="${SHARED_AGENT_BUCKET:-${PROJECT_ID}-agents-shared}"
BUCKET_URI="gs://${SHARED_BUCKET_NAME}"
SA_EMAIL="gemini-enterprise-admin@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="${HOME}/.config/gcloud/gemini-enterprise-admin-key.json"

echo "=============================================================================="
echo " Provisioning Private Shared Agent Bucket: ${BUCKET_URI}"
echo " Project: ${PROJECT_ID} | Location: ${BUCKET_LOCATION}"
echo "=============================================================================="

gcloud config set project "${PROJECT_ID}" --quiet
if [[ -f "${KEY_FILE}" ]] && grep -q '"type": *"service_account"' "${KEY_FILE}" 2>/dev/null; then
  gcloud config unset auth/impersonate_service_account --quiet >/dev/null 2>&1 || true
  gcloud auth activate-service-account "${SA_EMAIL}" --key-file="${KEY_FILE}" --project="${PROJECT_ID}" --quiet
else
  gcloud config set auth/impersonate_service_account "${SA_EMAIL}" --quiet
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

echo ">>> [1/3] Creating/verifying bucket ${BUCKET_URI} with enforced Public Access Prevention..."
if ! gcloud storage buckets describe "${BUCKET_URI}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "${BUCKET_URI}" \
    --project="${PROJECT_ID}" \
    --location="${BUCKET_LOCATION}" \
    --uniform-bucket-level-access \
    --public-access-prevention \
    --quiet
  echo "  -> Created private bucket ${BUCKET_URI}."
else
  echo "  -> Bucket ${BUCKET_URI} already exists; enforcing security settings..."
  gcloud storage buckets update "${BUCKET_URI}" \
    --project="${PROJECT_ID}" \
    --uniform-bucket-level-access \
    --public-access-prevention \
    --quiet
fi

for PUBLIC_MEMBER in "allUsers" "allAuthenticatedUsers"; do
  gcloud storage buckets remove-iam-policy-binding "${BUCKET_URI}" \
    --member="${PUBLIC_MEMBER}" \
    --role="roles/storage.objectViewer" \
    --quiet >/dev/null 2>&1 || true
  gcloud storage buckets remove-iam-policy-binding "${BUCKET_URI}" \
    --member="${PUBLIC_MEMBER}" \
    --role="roles/storage.objectAdmin" \
    --quiet >/dev/null 2>&1 || true
done

echo ">>> [2/3] Granting bucket IAM access to all Agent Service Accounts..."
AGENT_PRINCIPALS=(
  "serviceAccount:${SA_EMAIL}"
  "serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  "serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
  "serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"
  "serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
  "user:admin@cbribiescas.altostrat.com"
  "user:cbribiescas@gcp.altostrat.com"
)

for PRINCIPAL in "${AGENT_PRINCIPALS[@]}"; do
  for ROLE in "roles/storage.objectAdmin" "roles/storage.legacyBucketReader"; do
    if gcloud storage buckets add-iam-policy-binding "${BUCKET_URI}" \
      --member="${PRINCIPAL}" \
      --role="${ROLE}" \
      --quiet >/dev/null 2>&1; then
      echo "  -> Granted ${ROLE} to ${PRINCIPAL}"
    else
      echo "  -> (Skipped ${PRINCIPAL} — service agent not yet initialized or already bound)"
    fi
  done
done

echo ">>> [3/3] Verifying bucket security configuration..."
gcloud storage buckets describe "${BUCKET_URI}" \
  --project="${PROJECT_ID}" \
  --format="yaml(name,location,public_access_prevention,uniform_bucket_level_access)"

echo "=============================================================================="
echo " ✅ Private Shared Agent Bucket Ready: ${BUCKET_URI}"
echo "=============================================================================="
