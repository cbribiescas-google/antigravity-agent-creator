#!/usr/bin/env bash
# ==============================================================================
# Enable Google Antigravity (Vertex AI API & roles/aiplatform.user IAM binding)
# (`scripts/enable_antigravity.sh`)
# ==============================================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo 'gemini-enterprise-demo-cb')}"
SA_EMAIL="${SA_EMAIL:-gemini-enterprise-admin@${PROJECT_ID}.iam.gserviceaccount.com}"
USER_ACCOUNT="${USER_ACCOUNT:-$(gcloud config get-value account 2>/dev/null || true)}"

echo "=== 1. Enabling Vertex AI API (aiplatform.googleapis.com) on ${PROJECT_ID} ==="
gcloud services enable aiplatform.googleapis.com --project="${PROJECT_ID}" --quiet

echo "=== 2. Granting roles/aiplatform.user to Service Account (${SA_EMAIL}) ==="
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None \
  --quiet >/dev/null
echo "Granted roles/aiplatform.user to serviceAccount:${SA_EMAIL}"

if [[ -n "${USER_ACCOUNT}" && "${USER_ACCOUNT}" != *"gserviceaccount.com"* ]]; then
  echo "=== 3. Granting roles/aiplatform.user to User Account (${USER_ACCOUNT}) ==="
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="user:${USER_ACCOUNT}" \
    --role="roles/aiplatform.user" \
    --condition=None \
    --quiet >/dev/null
  echo "Granted roles/aiplatform.user to user:${USER_ACCOUNT}"
fi

# Accepts optional additional members (e.g., user:someone@example.com or domain:example.com)
if [[ $# -gt 0 ]]; then
  for EXTRA_MEMBER in "$@"; do
    if [[ "${EXTRA_MEMBER}" != *":"* ]]; then
      EXTRA_MEMBER="user:${EXTRA_MEMBER}"
    fi
    echo "=== Granting roles/aiplatform.user to ${EXTRA_MEMBER} ==="
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="${EXTRA_MEMBER}" \
      --role="roles/aiplatform.user" \
      --condition=None \
      --quiet >/dev/null || true
    echo "Granted roles/aiplatform.user to ${EXTRA_MEMBER}"
  done
fi

echo "=== Done! Antigravity (aiplatform.googleapis.com + roles/aiplatform.user) is enabled on ${PROJECT_ID}. ==="
