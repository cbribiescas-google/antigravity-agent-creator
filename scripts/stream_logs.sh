#!/usr/bin/env bash
# ==============================================================================
# Live Log Streamer for Antigravity Agent on Vertex AI Agent Runtime
# (`gemini-antigravity-demo/scripts/stream_logs.sh`)
# ==============================================================================
set -euo pipefail

export CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gemini-enterprise-demo-cb}"
REASONING_ENGINE_ID="${REASONING_ENGINE_ID:-3019630839680991232}"

echo "Streaming live logs for Antigravity ReasoningEngine (${REASONING_ENGINE_ID}) in ${PROJECT_ID}..."
echo "(Press Ctrl+C to stop)"
echo "------------------------------------------------------------------------------"

exec gcloud alpha logging tail \
  "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\" AND resource.labels.reasoning_engine_id=\"${REASONING_ENGINE_ID}\"" \
  --project="${PROJECT_ID}" \
  --format="yaml(timestamp, severity, textPayload, jsonPayload)"
