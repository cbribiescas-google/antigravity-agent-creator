#!/usr/bin/env bash
# ==============================================================================
# Master Infrastructure-as-Code (IaC) Setup Script (`scripts/setup_all.sh`)
# ==============================================================================
# Reproduces the entire Antigravity Agent Creator environment from scratch:
#   1. GCP Project, Billing, Core APIs & Automation Service Account
#   2. Vertex AI Antigravity IAM (`roles/aiplatform.user`)
#   3. Gemini Enterprise Identity Provider (`aclConfig`) & Plus User Licenses
#   4. Private Shared Agent GCS Bucket (`gs://<PROJECT_ID>-agents-shared`)
#   5. BigQuery Token Telemetry + Trajectory Store + Gemini Enterprise Engine +
#      Vertex AI Agent Runtime Fleet (`Antigravity` + 5 Showcase DAG Agents) +
#      `ALL_USERS` Sharing + Programmatic LHS Nav Panel Pinning
#   6. (Optional) Standalone Cloud Run Live DAG Studio UI (`DEPLOY_CLOUD_RUN_STUDIO=true`)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ID="${PROJECT_ID:-gemini-enterprise-demo-cb}"
export DOMAIN="${DOMAIN:-cbribiescas.altostrat.com}"
export EXTRA_USERS="${EXTRA_USERS:-cbribiescas@gcp.altostrat.com}"
export DEPLOY_SHOWCASE_AGENTS="${DEPLOY_SHOWCASE_AGENTS:-true}"
export DEPLOY_CLOUD_RUN_STUDIO="${DEPLOY_CLOUD_RUN_STUDIO:-false}"

echo "=============================================================================="
echo " Starting Full IaC Provisioning for Antigravity Agent Creator (${PROJECT_ID})"
echo "=============================================================================="

echo ">>> [Step 1/5] Bootstrapping GCP Project, APIs & Automation Service Account..."
"${SCRIPT_DIR}/bootstrap_project_and_sa.sh"

echo ">>> [Step 2/5] Enabling Google Antigravity IAM (aiplatform.googleapis.com)..."
"${SCRIPT_DIR}/enable_antigravity.sh" "domain:${DOMAIN}" ${EXTRA_USERS}

echo ">>> [Step 3/5] Assigning Gemini Enterprise User Licenses (${DOMAIN})..."
"${SCRIPT_DIR}/assign_gemini_enterprise_licenses.sh" "${DOMAIN}"

echo ">>> [Step 4/5] Provisioning Private Shared Agent GCS Bucket..."
"${SCRIPT_DIR}/provision_shared_agent_bucket.sh"

echo ">>> [Step 5/5] Deploying Antigravity + Showcase Agents & Registering in Gemini Enterprise..."
"${SCRIPT_DIR}/provision.sh"

if [[ "${DEPLOY_CLOUD_RUN_STUDIO}" == "true" ]]; then
  echo ">>> [Optional] Deploying Standalone Live DAG Studio UI & Gateway to Cloud Run..."
  "${SCRIPT_DIR}/deploy_studio_cloud_run.sh"
fi

echo "=============================================================================="
echo " ✅ Full Antigravity Agent Creator IaC Setup Complete for Project: ${PROJECT_ID}"
echo "=============================================================================="
