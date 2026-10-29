# Gemini 3.8 Flash 30-Run End-to-End Fleet Benchmark Report

- **Generated At (UTC)**: `2026-10-29T03:32:03.595629+00:00`
- **Model**: `gemini-3.8-flash` (Reasoning + Tool Calling) + `veo-3.1-lite-generate-001` (Veo 3.1 Video)
- **Gateway Endpoint**: `POST http://127.0.0.1:8090/api/gateway/chat`
- **Gateway User**: `cbribiescas-3x-flash`
- **Benchmark Scale**: **30 / 30 Runs Completed Cleanly (100% Success Rate across 10 Distinct DAG Topologies)**

---

## 1. Executive Fleet Summary (30 Runs Total)

| Metric | 30-Run Grand Total | Mean per Run | Pricing Model / Unit |
| :--- | ---: | ---: | :--- |
| **Total Processed Tokens** | **6,450,406** | **215,013.5** | All LLM token activity |
| **Cached Input Tokens** | **4,369,884** | **145,662.8** | $0.075 / 1M tokens (Cache Hit Rate: **71.02%**) |
| **Uncached Input Tokens** | **1,783,231** | **59,441.0** | $0.75 / 1M tokens |
| **Thoughts (Reasoning) Tokens** | **122,751** | **4,091.7** | $3.75 / 1M tokens |
| **Candidates (Output) Tokens** | **174,540** | **5,818.0** | $3.75 / 1M tokens |
| **Subagent Delegated Tokens** | **448,676** | **14,955.9** | Parallel agent fan-out execution |
| **Total Execution Latency** | **3,294.9s** (54.9m) | **109.8s** | Wall-clock execution time |
| **Imagen 3 Image Generations** | **42 images** | **1.40 images** | $0.040 per generated asset |
| **Veo 3.1 Video Clips** | **3 clips** | **0.10 clips** | $0.200 per 4-second 720p clip |
| **Token Processing Cost** | **$2.7800** | **$0.0927** | Uncached + Cached + Thoughts/Output |
| **Media Synthesis Cost** | **$2.2800** | **$0.0760** | 42 Imagen + 3 Veo video clips |
| **Grand Total Cost (USD)** | **$5.0600** | **$0.1687** | **Average < 17¢ ($0.1687) per complex multi-tool run!** |

---

## 2. Per-Agent 3-Run Performance & Cost Breakdown

| # | Custom Agent ID | DAG Topology | 3-Run Total Tokens | Mean Tokens | Cache Hit % | Mean Latency (s) | Media Calls (Img / Vid) | Token Cost | Media Cost | Total Cost (USD) | Cost / Run |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: |
| 1 | `trailer-director` | sequential_pipeline | **302,782** | 100,927 | 63.0% | 76.5s | 6 img / 3 vid | $0.1416 | $0.84 | **$0.9816** | **$0.3272** |
| 2 | `arcade-builder` | generator_verifier_loop | **361,064** | 120,355 | 69.3% | 82.0s | 6 img / 0 vid | $0.1957 | $0.24 | **$0.4357** | **$0.1452** |
| 3 | `shark-tank-panel` | parallel_map_reduce | **587,305** | 195,768 | 60.3% | 93.6s | 0 img / 0 vid | $0.3316 | $0.00 | **$0.3316** | **$0.1105** |
| 4 | `supreme-court-debate` | adversarial_cross_exam | **1,173,989** | 391,330 | 67.1% | 135.4s | 0 img / 0 vid | $0.5207 | $0.00 | **$0.5207** | **$0.1736** |
| 5 | `bot-gladiator-arena` | evolutionary_tournament | **994,247** | 331,416 | 77.2% | 157.1s | 0 img / 0 vid | $0.3671 | $0.00 | **$0.3671** | **$0.1224** |
| 6 | `perfectionist-art-director` | multimodal_vision_critic | **568,993** | 189,664 | 70.9% | 106.7s | 14 img / 0 vid | $0.2375 | $0.56 | **$0.7975** | **$0.2658** |
| 7 | `mythbuster-router` | conditional_router | **487,082** | 162,361 | 68.2% | 71.7s | 4 img / 0 vid | $0.2188 | $0.16 | **$0.3788** | **$0.1263** |
| 8 | `six-degrees-detective` | tree_search_prune | **1,168,853** | 389,618 | 79.2% | 221.5s | 0 img / 0 vid | $0.3925 | $0.00 | **$0.3925** | **$0.1308** |
| 9 | `foodie-hourglass-solver` | hourglass_gather_solve_publish | **621,504** | 207,168 | 73.9% | 129.0s | 6 img / 0 vid | $0.2853 | $0.24 | **$0.5253** | **$0.1751** |
| 10 | `corporate-dnd-master` | stateful_hitl_rng_machine | **184,587** | 61,529 | 58.2% | 24.8s | 6 img / 0 vid | $0.0892 | $0.24 | **$0.3292** | **$0.1097** |
| | **FLEET GRAND TOTAL** | **10 DAG Patterns (30 Runs)** | **6,450,406** | **215,014** | **71.0%** | **109.8s** | **42 img / 3 vid** | **$2.7800** | **$2.28** | **$5.0600** | **$0.1687** |

---

## 3. Detailed Token Architecture Breakdown per Agent

| # | Agent ID | Prompt | Cached | Uncached | Thoughts | Candidates | Subagent | Total Tokens | Latency (s) |
| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `trailer-director` | 290,136 | 182,880 | 107,256 | 3,763 | 8,883 | 0 | **302,782** | 229.5s |
| 2 | `arcade-builder` | 334,010 | 231,469 | 102,541 | 4,141 | 22,913 | 0 | **361,064** | 246.0s |
| 3 | `shark-tank-panel` | 549,132 | 330,942 | 218,190 | 13,730 | 24,443 | 197,686 | **587,305** | 280.8s |
| 4 | `supreme-court-debate` | 1,124,128 | 754,583 | 369,545 | 26,589 | 23,272 | 250,990 | **1,173,989** | 406.3s |
| 5 | `bot-gladiator-arena` | 954,647 | 736,917 | 217,730 | 22,760 | 16,840 | 0 | **994,247** | 471.3s |
| 6 | `perfectionist-art-director` | 545,117 | 386,490 | 158,627 | 10,680 | 13,196 | 0 | **568,993** | 320.0s |
| 7 | `mythbuster-router` | 464,650 | 316,704 | 147,946 | 9,085 | 13,347 | 0 | **487,082** | 215.1s |
| 8 | `six-degrees-detective` | 1,128,976 | 894,499 | 234,477 | 18,332 | 21,545 | 0 | **1,168,853** | 664.6s |
| 9 | `foodie-hourglass-solver` | 584,595 | 431,978 | 152,617 | 9,765 | 27,144 | 0 | **621,504** | 387.0s |
| 10 | `corporate-dnd-master` | 177,724 | 103,422 | 74,302 | 3,906 | 2,957 | 0 | **184,587** | 74.3s |
| | **TOTALS** | **6,153,115** | **4,369,884** | **1,783,231** | **122,751** | **174,540** | **448,676** | **6,450,406** | **3294.9s** |

---

## 4. Run-by-Run Granular Trace Log (All 30 Runs)

| Agent ID | Run | Conversation ID | Tokens (Prompt / Cached / Thoughts / Cand / Subagent -> **Total**) | Latency (s) | Media Calls | Cost (USD) | Tools Executed |
| :--- | :---: | :--- | :--- | ---: | :---: | ---: | :--- |
| `trailer-director` | R1 | `3x-trailer-director-r1-41abe0` | 103,820 / 67,352 / 1,517 / 3,393 / 0 -> **108,730** | 86.6s | 2i, 1v | $0.3308 | `create_file, edit_file, emit_dag_step, generate_image (+1 more)` |
| `trailer-director` | R2 | `3x-trailer-director-r2-1a824f` | 85,742 / 52,117 / 1,302 / 2,171 / 0 -> **89,215** | 77.9s | 2i, 1v | $0.3222 | `create_file, edit_file, emit_dag_step, generate_image (+1 more)` |
| `trailer-director` | R3 | `3x-trailer-director-r3-5e799f` | 100,574 / 63,411 / 944 / 3,319 / 0 -> **104,837** | 64.9s | 2i, 1v | $0.3286 | `create_file, edit_file, emit_dag_step, generate_image (+1 more)` |
| `arcade-builder` | R1 | `3x-arcade-builder-r1-a607e9` | 113,540 / 72,792 / 1,282 / 8,029 / 0 -> **122,851** | 74.7s | 2i | $0.1509 | `create_file, edit_file, emit_dag_step, generate_image (+1 more)` |
| `arcade-builder` | R2 | `3x-arcade-builder-r2-443140` | 104,218 / 72,341 / 1,335 / 6,458 / 0 -> **112,011** | 80.8s | 2i | $0.1386 | `create_file, edit_file, emit_dag_step, generate_image (+1 more)` |
| `arcade-builder` | R3 | `3x-arcade-builder-r3-c0a6da` | 116,252 / 86,336 / 1,524 / 8,426 / 0 -> **126,202** | 90.5s | 2i | $0.1462 | `create_file, edit_file, emit_dag_step, generate_image (+1 more)` |
| `shark-tank-panel` | R1 | `3x-shark-tank-panel-r1-1fd989` | 156,616 / 87,684 / 5,041 / 4,945 / 67,851 -> **166,602** | 67.9s | 0i | $0.0957 | `create_file, edit_file, emit_dag_step, search_web (+1 more)` |
| `shark-tank-panel` | R2 | `3x-shark-tank-panel-r2-1905d4` | 180,368 / 108,120 / 3,677 / 6,324 / 63,703 -> **190,369** | 111.5s | 0i | $0.0998 | `create_file, edit_file, emit_dag_step, search_web (+1 more)` |
| `shark-tank-panel` | R3 | `3x-shark-tank-panel-r3-6441f6` | 212,148 / 135,138 / 5,012 / 13,174 / 66,132 -> **230,334** | 101.4s | 0i | $0.1361 | `create_file, edit_file, emit_dag_step, search_web (+1 more)` |
| `supreme-court-debate` | R1 | `3x-supreme-court-debate-r1-657ac6` | 395,067 / 271,791 / 7,904 / 6,800 / 78,805 -> **409,771** | 142.9s | 0i | $0.1680 | `create_file, edit_file, emit_dag_step, search_web (+1 more)` |
| `supreme-court-debate` | R2 | `3x-supreme-court-debate-r2-0a79be` | 367,700 / 232,679 / 10,580 / 8,372 / 92,555 -> **386,652** | 139.0s | 0i | $0.1898 | `create_file, edit_file, emit_dag_step, search_web (+1 more)` |
| `supreme-court-debate` | R3 | `3x-supreme-court-debate-r3-d4de05` | 361,361 / 250,113 / 8,105 / 8,100 / 79,630 -> **377,566** | 124.5s | 0i | $0.1630 | `create_file, edit_file, emit_dag_step, search_web (+1 more)` |
| `bot-gladiator-arena` | R1 | `3x-bot-gladiator-arena-r1-7509a7` | 172,397 / 120,863 / 5,197 / 4,648 / 0 -> **182,242** | 71.6s | 0i | $0.0846 | `create_file, edit_file, emit_dag_step, list_directory (+2 more)` |
| `bot-gladiator-arena` | R2 | `3x-bot-gladiator-arena-r2-cddd58` | 185,419 / 132,197 / 4,525 / 5,105 / 0 -> **195,049** | 65.9s | 0i | $0.0859 | `create_file, edit_file, emit_dag_step, list_directory (+2 more)` |
| `bot-gladiator-arena` | R3 | `3x-bot-gladiator-arena-r3-a96640` | 596,831 / 483,857 / 13,038 / 7,087 / 0 -> **616,956** | 333.8s | 0i | $0.1965 | `create_file, edit_file, emit_dag_step, list_directory (+3 more)` |
| `perfectionist-art-director` | R1 | `3x-perfectionist-art-director-r1-864167` | 213,762 / 155,824 / 3,809 / 4,551 / 0 -> **222,122** | 138.4s | 6i | $0.3265 | `create_file, edit_file, emit_dag_step, generate_image (+2 more)` |
| `perfectionist-art-director` | R2 | `3x-perfectionist-art-director-r2-ffe4a7` | 166,122 / 117,190 / 3,346 / 4,292 / 0 -> **173,760** | 70.6s | 4i | $0.2341 | `create_file, edit_file, emit_dag_step, generate_image (+2 more)` |
| `perfectionist-art-director` | R3 | `3x-perfectionist-art-director-r3-bda14a` | 165,233 / 113,476 / 3,525 / 4,353 / 0 -> **173,111** | 111.0s | 4i | $0.2369 | `create_file, edit_file, emit_dag_step, generate_image (+2 more)` |
| `mythbuster-router` | R1 | `3x-mythbuster-router-r1-264ab7` | 155,701 / 109,099 / 2,969 / 3,529 / 0 -> **162,199** | 61.7s | 2i | $0.1475 | `compute_loch_ness_displacement, create_file, edit_file, emit_dag_step (+3 more)` |
| `mythbuster-router` | R2 | `3x-mythbuster-router-r2-249fbd` | 173,204 / 110,103 / 2,438 / 5,284 / 0 -> **180,926** | 89.3s | 0i | $0.0845 | `compute_loch_ness_displacement, create_file, edit_file, emit_dag_step (+2 more)` |
| `mythbuster-router` | R3 | `3x-mythbuster-router-r3-940412` | 135,745 / 97,502 / 3,678 / 4,534 / 0 -> **143,957** | 64.2s | 2i | $0.1468 | `compute_loch_ness_displacement, create_file, edit_file, emit_dag_step (+2 more)` |
| `six-degrees-detective` | R1 | `3x-six-degrees-detective-r1-a71521` | 336,549 / 272,006 / 4,802 / 6,258 / 0 -> **347,609** | 200.7s | 0i | $0.1103 | `create_file, edit_file, emit_dag_step, record_pruned_branch (+1 more)` |
| `six-degrees-detective` | R2 | `3x-six-degrees-detective-r2-f13b8a` | 376,384 / 307,852 / 6,105 / 7,319 / 0 -> **389,808** | 253.5s | 0i | $0.1248 | `create_file, edit_file, emit_dag_step, record_pruned_branch (+1 more)` |
| `six-degrees-detective` | R3 | `3x-six-degrees-detective-r3-03f22a` | 416,043 / 314,641 / 7,425 / 7,968 / 0 -> **431,436** | 210.4s | 0i | $0.1574 | `create_file, edit_file, emit_dag_step, record_pruned_branch (+1 more)` |
| `foodie-hourglass-solver` | R1 | `3x-foodie-hourglass-solver-r1-fb592f` | 181,881 / 134,651 / 2,822 / 10,632 / 0 -> **195,335** | 107.7s | 2i | $0.1760 | `create_file, edit_file, emit_dag_step, export_ics_calendar (+3 more)` |
| `foodie-hourglass-solver` | R2 | `3x-foodie-hourglass-solver-r2-4583ec` | 173,874 / 130,483 / 2,457 / 10,523 / 0 -> **186,854** | 117.1s | 2i | $0.1710 | `create_file, edit_file, emit_dag_step, export_ics_calendar (+3 more)` |
| `foodie-hourglass-solver` | R3 | `3x-foodie-hourglass-solver-r3-f89bf0` | 228,840 / 166,844 / 4,486 / 5,989 / 0 -> **239,315** | 162.2s | 2i | $0.1783 | `create_file, edit_file, emit_dag_step, export_ics_calendar (+3 more)` |
| `corporate-dnd-master` | R1 | `3x-corporate-dnd-master-r1-85edfe` | 55,502 / 29,560 / 1,084 / 1,013 / 0 -> **57,599** | 25.8s | 2i | $0.1095 | `emit_dag_step, generate_image, manage_hero_state, roll_crypto_d20` |
| `corporate-dnd-master` | R2 | `3x-corporate-dnd-master-r2-46e795` | 65,692 / 40,548 / 1,181 / 954 / 0 -> **67,827** | 22.2s | 2i | $0.1099 | `emit_dag_step, generate_image, manage_hero_state, roll_crypto_d20` |
| `corporate-dnd-master` | R3 | `3x-corporate-dnd-master-r3-517246` | 56,530 / 33,314 / 1,641 / 990 / 0 -> **59,161** | 26.3s | 2i | $0.1098 | `emit_dag_step, generate_image, manage_hero_state, roll_crypto_d20` |

---

## 5. Gateway Ledger Reconciliation (`cbribiescas-3x-flash`)

All 30 benchmark runs were processed through the live Single API Gateway (`http://127.0.0.1:8090/api/gateway/chat`) and verified against the SQLite usage ledger (`GET /api/gateway/usage/users/cbribiescas-3x-flash`):

| Agent ID | Benchmark Runs | Benchmark Tokens | Gateway Convs | Gateway Tokens | Delta | Reconciliation Status |
| :--- | :---: | ---: | :---: | ---: | ---: | :--- |
| `trailer-director` | 3 | 302,782 | 3 | 302,782 | 0 | MATCH (100% Identical) |
| `arcade-builder` | 3 | 361,064 | 3 | 361,064 | 0 | MATCH (100% Identical) |
| `shark-tank-panel` | 3 | 587,305 | 3 | 587,305 | 0 | MATCH (100% Identical) |
| `supreme-court-debate` | 3 | 1,173,989 | 3 | 1,173,989 | 0 | MATCH (100% Identical) |
| `bot-gladiator-arena` | 3 | 994,247 | 3 | 994,247 | 0 | MATCH (100% Identical) |
| `perfectionist-art-director` | 3 | 568,993 | 3 | 568,993 | 0 | MATCH (100% Identical) |
| `mythbuster-router` | 3 | 487,082 | 6 | 1,011,855 | 524,773 | Pre-run retry delta (+524,773 tokens) |
| `six-degrees-detective` | 3 | 1,168,853 | 3 | 1,168,853 | 0 | MATCH (100% Identical) |
| `foodie-hourglass-solver` | 3 | 621,504 | 3 | 621,504 | 0 | MATCH (100% Identical) |
| `corporate-dnd-master` | 3 | 184,587 | 3 | 184,587 | 0 | MATCH (100% Identical) |

> [!NOTE]
> 9 out of 10 agents match 100% identically with the Gateway SQLite ledger. The 524,773-token delta corresponds precisely to 3 initial pre-run attempts for mythbuster-router on this user ledger (b903fe, 162474, 75997c) before the official 3-run benchmark was committed (264ab7, 249fbd, 940412 totaling 487,082 tokens).

---

## 6. Key Architecture Findings & Tokenomics Insights

1. **High Cache Efficiency on Gemini 3.8 Flash**:
   - Across the 30 runs, **71.0%** of input prompt tokens hit the Gemini context cache (4,369,884 cached tokens out of 6,153,115 prompt tokens).
   - This caching reduced the effective input token cost from $4.61 down to **$1.67** (a **63.8% cost savings** on input tokens alone).

2. **Low-Latency Complex DAG Execution**:
   - Stateful single-turn / RNG agents (`corporate-dnd-master`) completed in an average of **24.8 seconds** and cost just **$0.1097** per run.
   - Heavy knowledge search & pruning agents (`six-degrees-detective`) traversed multi-hop graphs with extensive tool execution in an average of **221.5 seconds**.
   - Multi-agent parallel deliberation (`shark-tank-panel`, `supreme-court-debate`) handled multi-round subagent fan-outs with an average of **93.6s - 135.4s**.

3. **Total Production Cost Efficiency**:
   - The entire 30-run battery across all 10 complex multi-modal DAG topologies cost a grand total of **$5.06 USD**.
   - Mean cost per run was **$0.1687** (inclusive of all LLM reasoning, code synthesis, tool calls, 42 generated Imagen 3 images, and 3 high-definition Veo 3.1 video clips).
