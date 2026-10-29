#!/usr/bin/env bash
# ==============================================================================
# Query Per-Conversation & Per-Request Token Usage Telemetry
# (`gemini-antigravity-demo/scripts/query_telemetry.sh`)
# ==============================================================================
set -euo pipefail

export CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE=false
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gemini-enterprise-demo-cb}"
BQ_DATASET="${ANTIGRAVITY_BQ_DATASET:-antigravity_telemetry}"
BQ_TABLE="${ANTIGRAVITY_BQ_TABLE:-token_usage}"
TOKEN="$(gcloud auth print-access-token --quiet)"

run_bq_query() {
  local sql="$1"
  local resp
  resp="$(curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    "https://bigquery.googleapis.com/bigquery/v2/projects/${PROJECT_ID}/queries" \
    -d "$(python3 -c 'import json, sys; print(json.dumps({"query": sys.argv[1], "useLegacySql": False}))' "${sql}")")"

  python3 -c '
import json, sys
data = json.loads(sys.argv[1])
if "error" in data:
    print("BigQuery error:", data["error"].get("message", data["error"]))
    sys.exit(1)
fields = [f["name"] for f in data.get("schema", {}).get("fields", [])]
rows = []
for r in data.get("rows", []):
    rows.append([str(cell.get("v", "")) if cell.get("v") is not None else "" for cell in r.get("f", [])])
if not rows:
    print("(0 rows returned)")
    sys.exit(0)
widths = [max(len(fields[i]), max(len(row[i]) for row in rows)) for i in range(len(fields))]
header = " | ".join(fields[i].ljust(widths[i]) for i in range(len(fields)))
sep = "-+-".join("-" * widths[i] for i in range(len(fields)))
print(header)
print(sep)
for row in rows:
    print(" | ".join(row[i].ljust(widths[i]) for i in range(len(fields))))
' "${resp}"
}

echo "=============================================================================="
echo " 1. PER-CONVERSATION TOKEN SUMMARY (Aligned 1:1 with GE App Conversations)"
echo "=============================================================================="
run_bq_query "
SELECT
  ge_conversation_id,
  antigravity_conversation_id,
  user_id,
  COUNT(*) AS turns,
  MAX(turn_number) AS max_turn,
  SUM(request_prompt_tokens) AS sum_prompt,
  SUM(request_cached_tokens) AS sum_cached,
  SUM(request_candidates_tokens) AS sum_output,
  SUM(request_thoughts_tokens) AS sum_thoughts,
  MAX(conversation_total_tokens) AS conv_total_tokens,
  ROUND(SUM(latency_ms) / 1000.0, 2) AS latency_s
FROM \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`
GROUP BY ge_conversation_id, antigravity_conversation_id, user_id
ORDER BY MAX(timestamp) DESC
LIMIT 25
"

echo ""
echo "=============================================================================="
echo " 2. PER-REQUEST (TURN-BY-TURN) TOKEN BREAKDOWN"
echo "=============================================================================="
run_bq_query "
SELECT
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', timestamp) AS ts_utc,
  ge_conversation_id,
  turn_number AS turn,
  SUBSTR(prompt_preview, 1, 40) AS prompt_preview,
  request_prompt_tokens AS req_in,
  request_cached_tokens AS req_cache,
  request_candidates_tokens AS req_out,
  request_thoughts_tokens AS req_think,
  request_total_tokens AS req_total,
  conversation_total_tokens AS conv_cum_total,
  CAST(ROUND(latency_ms, 0) AS INT64) AS ms
FROM \`${PROJECT_ID}.${BQ_DATASET}.${BQ_TABLE}\`
ORDER BY timestamp DESC
LIMIT 50
"
