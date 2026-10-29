# Antigravity 10-DAG Custom Agents — End-to-End Token & Verification Report

- **Generated At (UTC)**: `2026-10-29T02:23:10.614758+00:00`
- **GCP Project**: `gemini-enterprise-demo-cb`
- **Service Account**: `gemini-enterprise-admin@gemini-enterprise-demo-cb.iam.gserviceaccount.com`
- **Model**: `gemini-3.7-flash` (Vertex AI `global`) + `veo-3.1-lite-generate-001` (Veo 3.1 Video)
- **Gateway User ID**: `cbribiescas`
- **Scenarios Verified**: `10 / 10`

---

## 1. Executive Token Usage Summary

| Phase | Turns | Prompt Tokens | Cached Tokens | Thoughts Tokens | Candidates Tokens | Subagent Tokens | Total Tokens | Total Latency (s) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Step A: Agent Creation (`antigravity`)** | 10 | 597,798 | 356,462 | 6,245 | 12,975 | 0 | **617,018** | 148.9s |
| **Step B: Custom Agent Missions (`1..10`)** | 10 | 1,404,234 | 926,125 | 23,389 | 48,884 | 134,441 | **1,476,507** | 736.4s |
| **Step C: Multi-Turn Continuity Follow-up** | 1 | 144,019 | 117,750 | 579 | 2,263 | 0 | **146,861** | 49.3s |
| **Grand Total (All Gateway Requests)** | **21** | **2,146,051** | **1,400,337** | **30,213** | **64,122** | **134,441** | **2,240,386** | **934.5s** |

---

## 2. Step A — Custom Agent Creation Token Breakdown (`agent_id="antigravity"`)

| # | Created Agent ID | DAG Topology | Prompt | Cached | Thoughts | Candidates | Subagent | Total Creation Tokens | Latency (s) | Builder Tools Invoked |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | `trailer-director` | `sequential_pipeline` | 29,546 | 10,924 | 818 | 924 | 0 | **31,288** | 10.9s | `build_custom_agent` |
| 2 | `arcade-builder` | `generator_verifier_loop` | 29,730 | 10,931 | 866 | 1,009 | 0 | **31,605** | 10.8s | `build_custom_agent` |
| 3 | `shark-tank-panel` | `parallel_map_reduce` | 29,255 | 10,887 | 0 | 1,183 | 0 | **30,438** | 8.8s | `build_custom_agent` |
| 4 | `supreme-court-debate` | `adversarial_cross_exam` | 29,397 | 10,896 | 57 | 1,188 | 0 | **30,642** | 8.3s | `build_custom_agent` |
| 5 | `bot-gladiator-arena` | `evolutionary_tournament` | 29,767 | 10,925 | 495 | 1,018 | 0 | **31,280** | 9.5s | `build_custom_agent` |
| 6 | `perfectionist-art-director` | `multimodal_vision_critic` | 28,948 | 10,869 | 0 | 1,019 | 0 | **29,967** | 7.3s | `build_custom_agent` |
| 7 | `mythbuster-router` | `conditional_router` | 329,953 | 267,412 | 2,356 | 3,418 | 0 | **335,727** | 60.0s | `create_custom_tool`, `list_registered_agents_and_tools`, `run_command`, `run_command`, `run_command`, `run_command`, `run_command`, `run_command`, `list_registered_agents_and_tools`, `build_custom_agent`, `run_command`, `run_command`, `run_command`, `run_command`, `run_command`, `run_command` |
| 8 | `six-degrees-detective` | `tree_search_prune` | 30,207 | 12,710 | 565 | 1,049 | 0 | **31,821** | 12.7s | `build_custom_agent` |
| 9 | `foodie-hourglass-solver` | `hourglass_gather_solve_publish` | 30,488 | 0 | 540 | 1,027 | 0 | **32,055** | 10.6s | `build_custom_agent` |
| 10 | `corporate-dnd-master` | `stateful_hitl_rng_machine` | 30,507 | 10,908 | 548 | 1,140 | 0 | **32,195** | 10.1s | `build_custom_agent` |

---

## 3. Step B — Custom Agent Fun Mission Execution Token Breakdown (SSE `/api/gateway/chat/stream`)

| # | Custom Agent ID | DAG Pattern | Prompt | Cached | Thoughts | Candidates | Subagent | Total Run Tokens | Latency (s) | Media & Sandbox Deliverables |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | `trailer-director` | Linear Sequential Pipeline DAG | 100,967 | 63,391 | 924 | 2,860 | 0 | **104,751** | 69.3s | `trailer_script.md`, 2 media served (`200 OK`) |
| 2 | `arcade-builder` | Generator-Verifier Self-Healing Loop DAG | 102,615 | 68,438 | 931 | 6,367 | 0 | **109,913** | 52.6s | `kopi_dodge.html`, 2 media served (`200 OK`) |
| 3 | `shark-tank-panel` | Parallel Map-Reduce Fan-Out DAG | 209,211 | 137,018 | 2,665 | 8,557 | 63,107 | **220,433** | 119.9s | `rent_a_retriever_term_sheet.md` |
| 4 | `supreme-court-debate` | Multi-Round Adversarial Cross-Exam DAG | 301,472 | 191,620 | 6,887 | 5,726 | 71,334 | **314,085** | 103.5s | `hotdog_v_taco_opinion.md` |
| 5 | `bot-gladiator-arena` | Evolutionary Tournament Bracket DAG | 74,530 | 37,351 | 1,349 | 2,580 | 0 | **78,459** | 33.2s | `bot_tit_for_tat.py`, `bot_grim_trigger.py`, `bot_omega_adaptive.py`, `tournament_results.json` |
| 6 | `perfectionist-art-director` | Multimodal Producer-Vision Critic Reflection DAG | 108,028 | 75,606 | 2,112 | 3,176 | 0 | **113,316** | 58.6s | `comic_storyboard.md`, `vision_critiques.json`, 2 media served (`200 OK`) |
| 7 | `mythbuster-router` | Conditional Router Branching DAG (+ Dynamic Tool Synthesis) | 141,265 | 93,306 | 2,022 | 3,781 | 0 | **147,068** | 58.7s | `mythbuster_receipt.md`, 1 media served (`200 OK`) |
| 8 | `six-degrees-detective` | Dynamic Tree Search & Prune DAG | 147,904 | 102,958 | 3,214 | 5,014 | 0 | **156,132** | 97.5s | `six_degrees_chain.md`, `pruned_branches.jsonl` |
| 9 | `foodie-hourglass-solver` | Hourglass Gather-Solve-Publish DAG | 176,083 | 134,376 | 2,466 | 9,936 | 0 | **188,485** | 116.0s | `maxwell_crawl.ics`, `maxwell_crawl_card.html`, 3 media served (`200 OK`) |
| 10 | `corporate-dnd-master` | Stateful HITL / Crypto RNG State Machine DAG | 42,159 | 22,061 | 819 | 887 | 0 | **43,865** | 27.0s | `hero_state.json`, 1 media served (`200 OK`) |

---

## 4. Combined End-to-End Token Summary (Creation + Execution per Scenario)

| # | Agent ID | Creation Tokens | Run Tokens | Subagent Tokens (Run) | Combined Tokens | `.md` & `.json` Verified |
| ---: | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | `trailer-director` | 31,288 | 104,751 | 0 | **136,039** | YES |
| 2 | `arcade-builder` | 31,605 | 109,913 | 0 | **141,518** | YES |
| 3 | `shark-tank-panel` | 30,438 | 220,433 | 63,107 | **250,871** | YES |
| 4 | `supreme-court-debate` | 30,642 | 314,085 | 71,334 | **344,727** | YES |
| 5 | `bot-gladiator-arena` | 31,280 | 78,459 | 0 | **109,739** | YES |
| 6 | `perfectionist-art-director` | 29,967 | 113,316 | 0 | **143,283** | YES |
| 7 | `mythbuster-router` | 335,727 | 147,068 | 0 | **482,795** | YES |
| 8 | `six-degrees-detective` | 31,821 | 156,132 | 0 | **187,953** | YES |
| 9 | `foodie-hourglass-solver` | 32,055 | 188,485 | 0 | **220,540** | YES |
| 10 | `corporate-dnd-master` | 32,195 | 43,865 | 0 | **76,060** | YES |

---

## 5. Special Capabilities & Stateful Gateway Proofs

### 5.1 End-to-End Dynamic Tool Synthesis (`create_custom_tool`)
- **Scenario #7 (`mythbuster-router`)**: Antigravity dynamically synthesized `compute_loch_ness_displacement` via `create_custom_tool` -> persisted to `/usr/local/google/home/cbribiescas/workspace/gemini-enterprise-demo/gemini-antigravity-demo/app/dynamic_tools/compute_loch_ness_displacement.py` (`exists=True`).
- Creation Tool Calls: `['create_custom_tool', 'list_registered_agents_and_tools', 'run_command', 'run_command', 'run_command', 'run_command', 'run_command', 'run_command', 'list_registered_agents_and_tools', 'build_custom_agent', 'run_command', 'run_command', 'run_command', 'run_command', 'run_command', 'run_command']`
- Execution Tool Calls (confirming live invocation of synthesized tool): `['search_web', 'emit_dag_step', 'compute_loch_ness_displacement', 'verify_claim_math', 'emit_dag_step', 'generate_image', 'emit_dag_step', 'edit_file', 'emit_dag_step', 'search_web', 'generate_image', 'create_file']`

### 5.2 Multi-Turn Stateful Conversation & Cumulative Token Continuity
- **Agent**: `mythbuster-router` | **Gateway `conversation_id`**: `bc929838-733b-43cf-bb8c-6a6973f6d8d5`
- **Deterministic `antigravity_conversation_id`**: `62ab2e8a426c5982acf0af64e3a524b9` (`same_trajectory=True`)
- **Turn 1 Request Tokens**: `147,068`
- **Turn 2 Request Tokens**: `146,861` (`turn_number=2`, `turns_in_db=2`)
- **Turn 2 Cumulative Conversation Tokens**: `293,929` (`cumulative_exceeds_turn_1=True`)

### 5.3 Pre-Flight & Single API Gateway Ledger Audit
- **Health Endpoint (`/api/gateway/health`)**: HTTP `200`
- **Live Studio UI (`/ui/index.html` & `/studio`)**: HTTP `200` (`34,472` bytes)
- **Per-User Ledger (`/api/gateway/usage/users/cbribiescas`)**: `conversation_count=20`, `turn_count=21`, `total_tokens=2,240,386`
- **Global Summary (`/api/gateway/usage/summary`)**: `agents_tracked=11`, `conversations_tracked=20`
