/* ==========================================================================
   Antigravity Live Agent & DAG Studio — Frontend Application (app.js)
   Zero-build Vanilla ES Module talking to Single API Gateway (/api/gateway/*)
   ========================================================================== */

const API_BASE = "/api/gateway";

/* --------------------------------------------------------------------------
   1. Canonical SVG DAG Blueprints (Antigravity Builder + All 10 Topologies)
      ViewBox coordinate space: 1000 x 280
   -------------------------------------------------------------------------- */
export const CANONICAL_DAG_BLUEPRINTS = {
  antigravity: {
    title: "Autonomous Meta-Builder & Dynamic Tool Synthesis Loop",
    badge: "Builder Loop",
    nodes: [
      { id: "discover", label: "Inspect Catalog", sub: "list_registered...", type: "input", x: 105, y: 140, tools: ["list_registered_agents_and_tools", "view_file", "search_directory"] },
      { id: "synthesize_tool", label: "Synthesize Python Tool", sub: "create_custom_tool", type: "builder", x: 350, y: 66, tools: ["create_custom_tool"] },
      { id: "bind_tools", label: "Bind Harness & Media", sub: "search / run / veo", type: "process", x: 350, y: 214, tools: ["search_web", "read_url_content", "run_command", "create_file", "edit_file", "generate_image", "generate_video", "start_subagent", "invoke_subagent"] },
      { id: "compile_dag", label: "Compile Agent Spec", sub: "build_custom_agent", type: "builder", x: 645, y: 140, tools: ["build_custom_agent"] },
      { id: "ready", label: "Live on Gateway", sub: ".md + .json ready", type: "output", x: 895, y: 140, tools: [] },
    ],
    edges: [
      { from: "discover", to: "synthesize_tool", label: "new tool" },
      { from: "discover", to: "bind_tools", label: "catalog" },
      { from: "synthesize_tool", to: "compile_dag", label: "AST ok" },
      { from: "bind_tools", to: "compile_dag", label: "wire DAG" },
      { from: "compile_dag", to: "discover", label: "self-heal", isLoop: true, curveY: -55 },
      { from: "compile_dag", to: "ready", label: "registered" },
    ],
  },

  "trailer-director": {
    title: "Linear Sequential Pipeline DAG — Blockbuster Trailer Studio",
    badge: "Sequential Pipeline",
    nodes: [
      { id: "intake", label: "Mundane Premise", sub: "prompt intake", type: "input", x: 95, y: 140, tools: [] },
      { id: "script", label: "3-Act Voiceover", sub: "scriptwriter", type: "process", x: 295, y: 140, tools: ["create_file", "emit_dag_step"] },
      { id: "poster", label: "Theatrical Poster", sub: "generate_image", type: "media", x: 500, y: 140, tools: ["generate_image", "log_vision_critique"] },
      { id: "veo_clip", label: "Veo 3.1 Climax", sub: "generate_video_clip", type: "media", x: 705, y: 140, tools: ["generate_video_clip", "generate_video"] },
      { id: "premiere", label: "Final Cut Delivery", sub: "poster + MP4", type: "output", x: 905, y: 140, tools: [] },
    ],
    edges: [
      { from: "intake", to: "script", label: "act I-III" },
      { from: "script", to: "poster", label: "key art" },
      { from: "poster", to: "veo_clip", label: "16:9 4s" },
      { from: "veo_clip", to: "premiere", label: "multimodal" },
    ],
  },

  "arcade-builder": {
    title: "Generator-Verifier Self-Healing Loop — HTML5 Arcade Factory",
    badge: "Generator-Verifier Cycle",
    nodes: [
      { id: "spec", label: "Arcade Spec", sub: "Kopi Dodge", type: "input", x: 95, y: 150, tools: [] },
      { id: "coder", label: "HTML5 Canvas Coder", sub: "create_file / edit", type: "generator", x: 310, y: 150, tools: ["create_file", "edit_file"] },
      { id: "validate_html5_game", label: "Headless Game QA", sub: "validate_html5_game", type: "verifier", x: 545, y: 150, tools: ["validate_html5_game", "run_command"] },
      { id: "box_art", label: "16-Bit Box Art", sub: "generate_image", type: "media", x: 755, y: 150, tools: ["generate_image"] },
      { id: "cabinet", label: "Playable Cabinet", sub: "iframe + art", type: "output", x: 915, y: 150, tools: ["emit_dag_step"] },
    ],
    edges: [
      { from: "spec", to: "coder", label: "build" },
      { from: "coder", to: "validate_html5_game", label: "AST + loop QA" },
      { from: "validate_html5_game", to: "coder", label: "self-heal retry", isLoop: true, curveY: -78 },
      { from: "validate_html5_game", to: "box_art", label: "passed=true" },
      { from: "box_art", to: "cabinet", label: "ship" },
    ],
  },

  "shark-tank-panel": {
    title: "Parallel 3-Shark Map-Reduce Fan-Out — VC Pitch Roaster",
    badge: "Parallel Map-Reduce",
    nodes: [
      { id: "pitch_in", label: "Startup Pitch", sub: "fan-out coordinator", type: "input", x: 105, y: 140, tools: ["search_web", "read_url_content"] },
      { id: "numbers_hawk", label: "Numbers Hawk", sub: "unit economics VC", type: "subagent", x: 470, y: 52, tools: ["start_subagent", "invoke_subagent"], matchKeys: ["numbers", "hawk", "fin", "economics", "shark_1", "shark_numbers"] },
      { id: "hype_visionary", label: "Hype Visionary", sub: "TAM & moat VC", type: "subagent", x: 470, y: 140, tools: ["start_subagent", "invoke_subagent"], matchKeys: ["hype", "visionary", "growth", "shark_2", "shark_vision"] },
      { id: "skeptical_customer", label: "Skeptical Customer", sub: "retention critic", type: "subagent", x: 470, y: 228, tools: ["start_subagent", "invoke_subagent"], matchKeys: ["skeptic", "customer", "user", "shark_3", "shark_skeptic"] },
      { id: "term_sheet", label: "Term Sheet & Pitch", sub: "reduce synthesis", type: "output", x: 855, y: 140, tools: ["emit_dag_step", "create_file"] },
    ],
    edges: [
      { from: "pitch_in", to: "numbers_hawk", label: "spawn" },
      { from: "pitch_in", to: "hype_visionary", label: "spawn" },
      { from: "pitch_in", to: "skeptical_customer", label: "spawn" },
      { from: "numbers_hawk", to: "term_sheet", label: "score" },
      { from: "hype_visionary", to: "term_sheet", label: "score" },
      { from: "skeptical_customer", to: "term_sheet", label: "score" },
    ],
  },

  "supreme-court-debate": {
    title: "Multi-Round Adversarial Cross-Exam Ping-Pong — Supreme Court",
    badge: "Adversarial Cross-Exam",
    nodes: [
      { id: "docket", label: "Certiorari Docket", sub: "hotdog vs taco", type: "input", x: 100, y: 140, tools: ["search_web"] },
      { id: "counsel_pro", label: "Counsel PRO", sub: "structuralist brief", type: "subagent", x: 390, y: 68, tools: ["start_subagent", "invoke_subagent", "search_web"], matchKeys: ["pro", "petitioner", "affirmative", "counsel_pro", "advocate"] },
      { id: "counsel_con", label: "Counsel CON", sub: "originalist rebuttal", type: "subagent", x: 390, y: 212, tools: ["start_subagent", "invoke_subagent", "search_web"], matchKeys: ["con", "respondent", "negative", "counsel_con", "challenger"] },
      { id: "rebuttal_round", label: "Cross-Exam Clash", sub: "rebuttal synthesis", type: "process", x: 655, y: 140, tools: ["emit_dag_step", "read_url_content"] },
      { id: "chief_justice", label: "Chief Justice Opinion", sub: "final ruling", type: "output", x: 895, y: 140, tools: ["create_file"] },
    ],
    edges: [
      { from: "docket", to: "counsel_pro", label: "opening" },
      { from: "docket", to: "counsel_con", label: "opening" },
      { from: "counsel_pro", to: "counsel_con", label: "cross-exam", isLoop: true, curveY: 0 },
      { from: "counsel_con", to: "counsel_pro", label: "rebuttal", isLoop: true, curveY: 0 },
      { from: "counsel_pro", to: "rebuttal_round", label: "record" },
      { from: "counsel_con", to: "rebuttal_round", label: "record" },
      { from: "rebuttal_round", to: "chief_justice", label: "verdict" },
    ],
  },

  "bot-gladiator-arena": {
    title: "Evolutionary 3-Bot Tournament Bracket — Prisoner's Dilemma Arena",
    badge: "3-Bot Tournament Arena",
    nodes: [
      { id: "arena_spec", label: "Payoff Matrix", sub: "2,000-rd spec", type: "input", x: 95, y: 140, tools: [] },
      { id: "bot_a", label: "Code Bot Alpha", sub: "bot_a.py", type: "generator", x: 345, y: 52, tools: ["create_file"], matchKeys: ["bot_a", "alpha", "tit_for_tat"] },
      { id: "bot_b", label: "Code Bot Beta", sub: "bot_b.py", type: "generator", x: 345, y: 140, tools: ["create_file"], matchKeys: ["bot_b", "beta", "pavlov", "grudger", "grim"] },
      { id: "bot_c", label: "Code Bot Gamma", sub: "bot_c.py", type: "generator", x: 345, y: 228, tools: ["create_file"], matchKeys: ["bot_c", "gamma", "adaptive", "defect", "opportunist"] },
      { id: "run_bot_tournament", label: "12,000-Move Arena", sub: "run_bot_tournament", type: "verifier", x: 645, y: 140, tools: ["run_bot_tournament", "run_command"] },
      { id: "champion", label: "Crown Champion", sub: "matrix & trophy", type: "output", x: 895, y: 140, tools: ["generate_image", "emit_dag_step"] },
    ],
    edges: [
      { from: "arena_spec", to: "bot_a", label: "strategy A" },
      { from: "arena_spec", to: "bot_b", label: "strategy B" },
      { from: "arena_spec", to: "bot_c", label: "strategy C" },
      { from: "bot_a", to: "run_bot_tournament", label: "load" },
      { from: "bot_b", to: "run_bot_tournament", label: "load" },
      { from: "bot_c", to: "run_bot_tournament", label: "load" },
      { from: "run_bot_tournament", to: "champion", label: "leaderboard" },
    ],
  },

  "perfectionist-art-director": {
    title: "Multimodal Producer-Vision Critic Reflection Loop",
    badge: "Vision Critic Loop",
    nodes: [
      { id: "brief", label: "Comic Storyboard", sub: "3-panel script", type: "input", x: 95, y: 150, tools: ["create_file"] },
      { id: "draft_v1", label: "Render Draft V1", sub: "generate_image", type: "media", x: 295, y: 150, tools: ["generate_image"], sequentialSlot: 1 },
      { id: "inspect_v1", label: "Multimodal Inspect", sub: "view_file (vision)", type: "process", x: 495, y: 150, tools: ["view_file"] },
      { id: "vision_critic", label: "Vision Critique", sub: "log_vision_critique", type: "verifier", x: 695, y: 150, tools: ["log_vision_critique"] },
      { id: "masterpiece_v2", label: "Masterpiece V2", sub: "generate_image", type: "output", x: 900, y: 150, tools: ["generate_image", "emit_dag_step"], sequentialSlot: 2 },
    ],
    edges: [
      { from: "brief", to: "draft_v1", label: "v1 prompt" },
      { from: "draft_v1", to: "inspect_v1", label: "pixels" },
      { from: "inspect_v1", to: "vision_critic", label: "score /10" },
      { from: "vision_critic", to: "draft_v1", label: "upgraded prompt", isLoop: true, curveY: -78 },
      { from: "vision_critic", to: "masterpiece_v2", label: "render V2" },
    ],
  },

  "mythbuster-router": {
    title: "Conditional Router Diamond DAG — Quantitative MythBuster",
    badge: "Conditional Router",
    nodes: [
      { id: "claim", label: "Viral Bar-Bet", sub: "Loch Ness 8.1B", type: "input", x: 95, y: 140, tools: [] },
      { id: "primary_data", label: "Source Constants", sub: "search_web", type: "process", x: 295, y: 140, tools: ["search_web", "read_url_content"] },
      { id: "router_math", label: "Math Router", sub: "verify_claim_math", type: "router", x: 515, y: 140, tools: ["verify_claim_math", "run_command"] },
      { id: "CONFIRMED_INFOGRAPHIC", label: "CONFIRMED Branch", sub: "scale infographic", type: "media", x: 745, y: 70, tools: ["generate_image"], matchKeys: ["confirmed", "confirmed_infographic"] },
      { id: "BUSTED_ORIGIN_TRACE", label: "BUSTED Branch", sub: "myth origin trace", type: "verifier", x: 745, y: 210, tools: ["search_web"], matchKeys: ["busted", "busted_origin_trace"] },
      { id: "verdict", label: "Official Receipt", sub: "verified math", type: "output", x: 920, y: 140, tools: ["emit_dag_step", "create_file"] },
    ],
    edges: [
      { from: "claim", to: "primary_data", label: "citations" },
      { from: "primary_data", to: "router_math", label: "compute" },
      { from: "router_math", to: "CONFIRMED_INFOGRAPHIC", label: "confirmed=true", branchKey: "CONFIRMED_INFOGRAPHIC" },
      { from: "router_math", to: "BUSTED_ORIGIN_TRACE", label: "confirmed=false", branchKey: "BUSTED_ORIGIN_TRACE" },
      { from: "CONFIRMED_INFOGRAPHIC", to: "verdict", label: "deliver" },
      { from: "BUSTED_ORIGIN_TRACE", to: "verdict", label: "deliver" },
    ],
  },

  "six-degrees-detective": {
    title: "Dynamic Tree Search & Dead-End Prune — Six Degrees Detective",
    badge: "Tree Search & Prune",
    nodes: [
      { id: "root_entity", label: "Origin: Bubble Tea", sub: "Taichung 1980s", type: "input", x: 95, y: 140, tools: ["search_web"] },
      { id: "hop_1_active", label: "Hop 1: Verified Link", sub: "search_web", type: "process", x: 330, y: 82, tools: ["search_web", "read_url_content", "emit_dag_step"], matchKeys: ["hop_1", "hop1", "step_1"] },
      { id: "pruned_1", label: "Dead-End Branch A", sub: "record_pruned_branch", type: "prunable", x: 330, y: 208, tools: ["record_pruned_branch"], matchKeys: ["prune", "dead"] },
      { id: "hop_2_active", label: "Hop 2-3: Bridge", sub: "aerospace / NASA", type: "process", x: 610, y: 82, tools: ["search_web", "emit_dag_step"], matchKeys: ["hop_2", "hop2", "hop_3", "hop3", "bridge"] },
      { id: "pruned_2", label: "Dead-End Branch B", sub: "✂ pruned (>4 hops)", type: "prunable", x: 610, y: 208, tools: ["record_pruned_branch"] },
      { id: "target_moon", label: "Apollo 11 Landing", sub: "≤4 verified hops", type: "output", x: 890, y: 140, tools: ["create_file"] },
    ],
    edges: [
      { from: "root_entity", to: "hop_1_active", label: "explore" },
      { from: "root_entity", to: "pruned_1", label: "prune" },
      { from: "hop_1_active", to: "hop_2_active", label: "hop ≤3" },
      { from: "hop_1_active", to: "pruned_2", label: "prune" },
      { from: "hop_2_active", to: "target_moon", label: "Q.E.D." },
    ],
  },

  "food-crawl-planner": {
    title: "Hourglass Gather-Solve-Publish DAG — Street Food Crawl Planner",
    badge: "Hourglass Topology",
    nodes: [
      { id: "gather_starters", label: "Gather Starters", sub: "search_web", type: "input", x: 120, y: 54, tools: ["search_web"], matchKeys: ["starter"] },
      { id: "gather_mains", label: "Gather Mains", sub: "hawker / street stalls", type: "input", x: 120, y: 140, tools: ["search_web", "read_url_content"], matchKeys: ["main", "gather"] },
      { id: "gather_desserts", label: "Gather Desserts", sub: "local sweets", type: "input", x: 120, y: 226, tools: ["search_web"], matchKeys: ["dessert"] },
      { id: "solve_crawl_constraints", label: "Route & Budget Solver", sub: "solve_crawl_constraints", type: "router", x: 495, y: 140, tools: ["solve_crawl_constraints", "run_command"] },
      { id: "export_ics_calendar", label: "Export .ics Schedule", sub: "export_ics_calendar", type: "output", x: 865, y: 54, tools: ["export_ics_calendar"] },
      { id: "html_card", label: "HTML5 Crawl Card", sub: "create_file (.html)", type: "output", x: 865, y: 140, tools: ["create_file"] },
      { id: "postcard_art", label: "Watercolor Postcard", sub: "generate_image", type: "media", x: 865, y: 226, tools: ["generate_image", "emit_dag_step"] },
    ],
    edges: [
      { from: "gather_starters", to: "solve_crawl_constraints", label: "candidates" },
      { from: "gather_mains", to: "solve_crawl_constraints", label: "S$20 / 75m" },
      { from: "gather_desserts", to: "solve_crawl_constraints", label: "candidates" },
      { from: "solve_crawl_constraints", to: "export_ics_calendar", label: "RFC 5545" },
      { from: "solve_crawl_constraints", to: "html_card", label: "route map" },
      { from: "solve_crawl_constraints", to: "postcard_art", label: "illustrate" },
    ],
  },

  "foodie-hourglass-solver": {
    title: "Hourglass Gather-Solve-Publish DAG — Street Food Crawl Planner",
    badge: "Hourglass Topology",
    nodes: [
      { id: "gather_starters", label: "Gather Starters", sub: "search_web", type: "input", x: 120, y: 54, tools: ["search_web"], matchKeys: ["starter"] },
      { id: "gather_mains", label: "Gather Mains", sub: "Maxwell stalls", type: "input", x: 120, y: 140, tools: ["search_web", "read_url_content"], matchKeys: ["main", "gather"] },
      { id: "gather_desserts", label: "Gather Desserts", sub: "Chinatown sweet", type: "input", x: 120, y: 226, tools: ["search_web"], matchKeys: ["dessert"] },
      { id: "solve_crawl_constraints", label: "Knapsack Waist", sub: "solve_crawl_constraints", type: "router", x: 495, y: 140, tools: ["solve_crawl_constraints", "run_command"] },
      { id: "export_ics_calendar", label: "Export .ics Schedule", sub: "export_ics_calendar", type: "output", x: 865, y: 54, tools: ["export_ics_calendar"] },
      { id: "html_card", label: "HTML5 Crawl Card", sub: "create_file (.html)", type: "output", x: 865, y: 140, tools: ["create_file"] },
      { id: "postcard_art", label: "Watercolor Postcard", sub: "generate_image", type: "media", x: 865, y: 226, tools: ["generate_image", "emit_dag_step"] },
    ],
    edges: [
      { from: "gather_starters", to: "solve_crawl_constraints", label: "candidates" },
      { from: "gather_mains", to: "solve_crawl_constraints", label: "S$20 / 75m" },
      { from: "gather_desserts", to: "solve_crawl_constraints", label: "candidates" },
      { from: "solve_crawl_constraints", to: "export_ics_calendar", label: "RFC 5545" },
      { from: "solve_crawl_constraints", to: "html_card", label: "route map" },
      { from: "solve_crawl_constraints", to: "postcard_art", label: "illustrate" },
    ],
  },

  "corporate-dnd-master": {
    title: "Stateful HITL & Cryptographic d20 State Machine — Corporate D&D",
    badge: "Stateful HITL Loop",
    nodes: [
      { id: "load_hero", label: "Load Hero Sheet", sub: "manage_hero_state", type: "input", x: 105, y: 150, tools: ["manage_hero_state"], sequentialSlot: 1 },
      { id: "roll_crypto_d20", label: "OS CSPRNG d20", sub: "roll_crypto_d20", type: "verifier", x: 315, y: 150, tools: ["roll_crypto_d20"] },
      { id: "encounter_art", label: "Boss Encounter Art", sub: "generate_image", type: "media", x: 525, y: 150, tools: ["generate_image"] },
      { id: "save_hero", label: "Persist HP & Loot", sub: "hero_state.json", type: "process", x: 730, y: 150, tools: ["manage_hero_state", "emit_dag_step"], sequentialSlot: 2 },
      { id: "hitl_choice", label: "Player Turn / HITL", sub: "next turn / choice", type: "output", x: 910, y: 150, tools: ["ask_question"] },
    ],
    edges: [
      { from: "load_hero", to: "roll_crypto_d20", label: "stats" },
      { from: "roll_crypto_d20", to: "encounter_art", label: "nat 1..20" },
      { from: "encounter_art", to: "save_hero", label: "apply HP" },
      { from: "save_hero", to: "hitl_choice", label: "state saved" },
      { from: "hitl_choice", to: "load_hero", label: "next turn", isLoop: true, curveY: -80 },
    ],
  },
};

/* --------------------------------------------------------------------------
   2. All 10 Fun Quick-Build DAG Scenarios (Creation + Starter Missions)
   -------------------------------------------------------------------------- */
export const SCENARIO_PRESETS = [
  {
    num: 1,
    agentId: "trailer-director",
    icon: "🎬",
    name: "Hollywood Trailer Director",
    topology: "Linear Sequential Pipeline",
    tools: ["generate_image", "generate_video_clip", "emit_dag_step"],
    blurb: "Turns mundane daily moments into an Oscar-worthy 3-act voiceover, poster & playable 4s Veo 3.1 trailer.",
    creationPrompt:
      `Build and register custom agent \`trailer-director\` ("Hollywood Trailer Director") using \`build_custom_agent\` with \`dag_topology="Linear Sequential Pipeline"\` and \`tool_names=["generate_image", "generate_video_clip", "generate_video", "create_file", "emit_dag_step"]\`. Configure its system instructions to: (1) write a dramatic 3-act movie trailer voiceover script, (2) call \`generate_image\` for a theatrical poster, (3) call \`generate_video_clip\` (4s, 16:9) for the climax trailer clip, and (4) call \`emit_dag_step\` at key stages without printing raw /tmp paths.`,
    missionPrompt:
      `Turn "Looking for a parking spot at a packed shopping mall on Saturday afternoon" into a high-stakes sci-fi blockbuster trailer! Deliver the 3-act voiceover script, generate the theatrical movie poster via \`generate_image\`, and render a 4-second 16:9 trailer clip via \`generate_video_clip\`.`,
  },
  {
    num: 2,
    agentId: "arcade-builder",
    icon: "🕹️",
    name: "Self-Healing Arcade Factory",
    topology: "Generator-Verifier Loop",
    tools: ["create_file", "validate_html5_game", "generate_image"],
    blurb: "Writes a playable HTML5 Canvas game, runs headless AST/loop QA, self-heals bugs, and paints 16-bit box art.",
    creationPrompt:
      `Build and register custom agent \`arcade-builder\` ("Self-Healing Arcade Factory") using \`build_custom_agent\` with \`dag_topology="Generator-Verifier Self-Healing Loop"\` and \`tool_names=["create_file", "edit_file", "validate_html5_game", "generate_image", "emit_dag_step"]\`. Instruct it to write a complete single-file HTML5 Canvas game in \`kopi_dodge.html\` with keyboard controls and \`requestAnimationFrame\`, validate it with \`validate_html5_game\` (self-healing until \`passed=True\`), and generate 16-bit arcade cabinet box art via \`generate_image\`.`,
    missionPrompt:
      `Build a playable retro HTML5 Canvas arcade game saved as \`kopi_dodge.html\` called "Kopi Dodge" where an office worker catches falling espresso cups while dodging red calendar invites! Validate it with \`validate_html5_game\` until \`passed: true\`, and generate retro 16-bit arcade cabinet box art with \`generate_image\`.`,
  },
  {
    num: 3,
    agentId: "shark-tank-panel",
    icon: "🦈",
    name: "Shark Tank 3-VC Panel",
    topology: "Parallel Map-Reduce Fan-Out",
    tools: ["start_subagent", "search_web", "emit_dag_step"],
    blurb: "Spawns 3 distinct VC Shark subagents in parallel to roast your startup pitch, check competitors & draft a Term Sheet.",
    creationPrompt:
      `Build and register custom agent \`shark-tank-panel\` ("Shark Tank 3-VC Panel") using \`build_custom_agent\` with \`dag_topology="Parallel Map-Reduce Fan-Out"\`, \`enable_subagents=True\`, \`tool_names=["start_subagent", "search_web", "emit_dag_step"]\`, and 3 declared subagents in \`subagent_specs_json\`: \`numbers_hawk\` (ruthless unit economics VC), \`hype_visionary\` (moonshot TAM VC), and \`skeptical_customer\` (pragmatic buyer critic). Instruct the coordinator to research live competitors via \`search_web\`, invoke all 3 Sharks, and synthesize scores (/10) + a Term Sheet.`,
    missionPrompt:
      `Pitch: "Rent-a-Retriever — an on-demand subscription service delivering golden retrievers to stressed software engineers for 45-minute code-review therapy sessions." Fan out to all 3 Shark subagents, check real competitors via \`search_web\`, and deliver the Shark Scorecard + Term Sheet!`,
  },
  {
    num: 4,
    agentId: "supreme-court-debate",
    icon: "⚖️",
    name: "Supreme Court Cross-Exam",
    topology: "Adversarial Cross-Exam Ping-Pong",
    tools: ["start_subagent", "search_web", "emit_dag_step"],
    blurb: "Pits Counsel PRO vs Counsel CON in multi-round adversarial cross-examination before the Chief Justice rules.",
    creationPrompt:
      `Build and register custom agent \`supreme-court-debate\` ("Supreme Court Cross-Exam") using \`build_custom_agent\` with \`dag_topology="Multi-Round Adversarial Cross-Exam"\`, \`enable_subagents=True\`, \`tool_names=["start_subagent", "search_web", "emit_dag_step"]\`, and subagents \`counsel_pro\` and \`counsel_con\`. Instruct it to run Opening Briefs, Cross-Examination Rebuttals grounded with \`search_web\` citations, and a final Chief Justice Ruling.`,
    missionPrompt:
      `Docket #26-404: "Under the Cube Rule of Food and statutory sandwich jurisprudence, is a hotdog legally and structurally a taco?" Run Counsel PRO vs Counsel CON cross-examination with real culinary/legal citations and issue the Chief Justice's Majority Opinion!`,
  },
  {
    num: 5,
    agentId: "bot-gladiator-arena",
    icon: "⚔️",
    name: "AI Bot Gladiator Arena",
    topology: "3-Bot Tournament Bracket",
    tools: ["create_file", "run_bot_tournament", "generate_image"],
    blurb: "Codes 3 Python Prisoner's Dilemma bots in the sandbox and battles them across 2,000 deterministic rounds.",
    creationPrompt:
      `Build and register custom agent \`bot-gladiator-arena\` ("AI Bot Gladiator Arena") using \`build_custom_agent\` with \`dag_topology="Evolutionary Tournament Bracket"\` and \`tool_names=["create_file", "run_bot_tournament", "generate_image", "emit_dag_step"]\`. Instruct it to write 3 distinct Python strategy bots (\`bot_a.py\`, \`bot_b.py\`, \`bot_c.py\`) implementing \`decide(my_history: list[str], opponent_history: list[str]) -> str\` returning \`'C'\` or \`'D'\`, execute \`run_bot_tournament(rounds=2000)\`, and present the exact match matrix + champion banner.`,
    missionPrompt:
      `Code 3 rival Prisoner's Dilemma gladiator bots in Python (\`bot_a.py\` Tit-for-Two-Tats, \`bot_b.py\` Grim Trigger, and \`bot_c.py\` Opportunistic Pavlov), battle them in \`run_bot_tournament\` for 2,000 rounds per pairing, report the exact leaderboard & match matrix, and generate a champion trophy illustration!`,
  },
  {
    num: 6,
    agentId: "perfectionist-art-director",
    icon: "🎨",
    name: "Perfectionist Art Director",
    topology: "Multimodal Vision Critic Loop",
    tools: ["generate_image", "view_file", "log_vision_critique"],
    blurb: "Paints Draft V1, visually inspects its own pixels via multimodal vision, logs a critique, and renders Masterpiece V2.",
    creationPrompt:
      `Build and register custom agent \`perfectionist-art-director\` ("Perfectionist Art Director") using \`build_custom_agent\` with \`dag_topology="Multimodal Producer-Vision Critic Reflection Loop"\` and \`tool_names=["generate_image", "view_file", "log_vision_critique", "emit_dag_step"]\`. Instruct it to: (1) render Draft V1 with \`generate_image\`, (2) visually inspect Draft V1 with \`view_file\`, (3) score composition & lighting and write an upgraded prompt via \`log_vision_critique\`, and (4) render Masterpiece V2 with \`generate_image\`.`,
    missionPrompt:
      `Create a 3-panel comic strip about a developer accidentally screen-sharing 47 chaotic browser tabs during an executive board demo: render Draft V1 (\`generate_image\`), visually inspect it (\`view_file\`), log your critique & upgraded prompt (\`log_vision_critique\`), and render the polished Masterpiece V2!`,
  },
  {
    num: 7,
    agentId: "mythbuster-router",
    icon: "🧪",
    name: "MythBuster Conditional Router",
    topology: "Conditional Router Diamond",
    tools: ["search_web", "verify_claim_math", "generate_image"],
    blurb: "Synthesizes custom math verification, checks Loch Ness volume vs 8.1B humans, and dynamically branches on truth!",
    creationPrompt:
      `First use \`create_custom_tool\` to synthesize a reusable helper tool \`compute_packing_ratio(container_cubic_meters: float, item_count: float, item_cubic_meters: float = 0.065) -> dict\` that calculates total item volume, fill percentage, and spare capacity. Then call \`build_custom_agent\` to register \`mythbuster-router\` ("MythBuster Conditional Router") with \`dag_topology="Conditional Router Diamond"\` and \`tool_names=["search_web", "verify_claim_math", "compute_packing_ratio", "generate_image", "emit_dag_step"]\` that branches to \`CONFIRMED_INFOGRAPHIC\` (generating a scale diagram) or \`BUSTED_ORIGIN_TRACE\` based on \`verify_claim_math\`.`,
    missionPrompt:
      `Fact-check this viral bar bet: "Every single human on Earth (8.1 billion people) could fit completely submerged inside Loch Ness at the same time with room to spare." Search Loch Ness volume via \`search_web\`, verify the exact cubic-meter math with \`verify_claim_math\`, and execute the routed branch!`,
  },
  {
    num: 8,
    agentId: "six-degrees-detective",
    icon: "🕸️",
    name: "Six Degrees Tree Detective",
    topology: "Dynamic Tree Search & Prune",
    tools: ["search_web", "record_pruned_branch", "emit_dag_step"],
    blurb: "Explores live web entity links to connect two wildly unrelated topics in ≤4 hops while pruning dead-end branches.",
    creationPrompt:
      `Build and register custom agent \`six-degrees-detective\` ("Six Degrees Tree Detective") using \`build_custom_agent\` with \`dag_topology="Dynamic Tree Search & Prune"\` and \`tool_names=["search_web", "read_url_content", "record_pruned_branch", "emit_dag_step"]\`. Instruct it to explore candidate factual bridges via \`search_web\`, prune dead-end or weak branches explicitly via \`record_pruned_branch\`, emit verified hops via \`emit_dag_step\`, and prove a chain of <= 4 factual hops.`,
    missionPrompt:
      `Connect "Bubble Tea (Pearl Milk Tea)" to the "Apollo 11 Moon Landing" in 4 or fewer 100% factual, citation-verified hops! Use \`search_web\` to test candidate paths, call \`record_pruned_branch\` on at least one dead-end path you reject, and present the winning hop chain!`,
  },
  {
    num: 9,
    agentId: "food-crawl-planner",
    icon: "🍜",
    name: "Street Food Crawl Planner",
    topology: "Hourglass Gather-Solve-Publish",
    tools: ["search_web", "solve_crawl_constraints", "export_ics_calendar", "generate_image"],
    blurb: "Scouts street food stalls, solves a S$20 / 75-min route waist, and fans out to .ics calendar + HTML card + postcard!",
    creationPrompt:
      `Build and register custom agent \`food-crawl-planner\` ("Street Food Crawl Planner") using \`build_custom_agent\` with \`dag_topology="Hourglass Gather-Solve-Publish"\` and \`tool_names=["search_web", "solve_crawl_constraints", "export_ics_calendar", "create_file", "generate_image", "emit_dag_step"]\`. Instruct it to gather real Starter/Main/Dessert street food stalls via \`search_web\`, optimize via \`solve_crawl_constraints\`, and publish all 3 outputs: an \`.ics\` schedule (\`export_ics_calendar\`), an HTML itinerary card (\`create_file\`), and a watercolor foodie postcard (\`generate_image\`).`,
    missionPrompt:
      `Plan an optimal 3-stop Singapore hawker crawl (Starter + Main + Dessert) around Maxwell & Chinatown under S$20 total and 75 minutes! Gather real stalls via \`search_web\`, solve with \`solve_crawl_constraints\`, export \`food_crawl.ics\` via \`export_ics_calendar\`, save a styled \`food_crawl_card.html\`, and generate a watercolor foodie postcard!`,
  },
  {
    num: 10,
    agentId: "corporate-dnd-master",
    icon: "🐉",
    name: "Corporate D&D State Machine",
    topology: "Stateful HITL & Crypto RNG Loop",
    tools: ["manage_hero_state", "roll_crypto_d20", "generate_image", "ask_question"],
    blurb: "Runs an office RPG with persistent hero_state.json, genuine OS CSPRNG d20 rolls, boss art, and multi-turn quests.",
    creationPrompt:
      `Build and register custom agent \`corporate-dnd-master\` ("Corporate D&D State Machine") using \`build_custom_agent\` with \`dag_topology="Stateful HITL Crypto-RNG State Machine"\` and \`tool_names=["manage_hero_state", "roll_crypto_d20", "generate_image", "ask_question", "emit_dag_step"]\`. Instruct it on every turn to load/init hero state via \`manage_hero_state\`, roll a genuine cryptographic d20 via \`roll_crypto_d20\`, mutate HP/loot in \`manage_hero_state\`, illustrate the boss encounter via \`generate_image\`, and offer 3 tactical next-turn actions.`,
    missionPrompt:
      `Start Turn 1 of my quest as "Spreadsheet Paladin" entering Q4 Planning Dungeon to face the Hydra of Scope Creep! Initialize my hero state via \`manage_hero_state\`, roll my opening Pivot-Table Smite attack via \`roll_crypto_d20\` (+3 modifier), persist resulting HP/loot, generate boss encounter art via \`generate_image\`, and present my 3 tactical choices for Turn 2 (without blocking on stdin)!`,
  },
];

/* --------------------------------------------------------------------------
   3. Tool Visual Metadata & Formatting Helpers
   -------------------------------------------------------------------------- */
const TOOL_META = {
  search_web: { icon: "🔍", badge: "badge-cyan", label: "Web Search" },
  read_url_content: { icon: "🌐", badge: "badge-cyan", label: "Read URL" },
  run_command: { icon: "🐍", badge: "badge-amber", label: "Sandbox Shell" },
  create_file: { icon: "📄", badge: "badge-emerald", label: "Create File" },
  edit_file: { icon: "✏️", badge: "badge-emerald", label: "Edit File" },
  view_file: { icon: "👁️", badge: "badge-teal", label: "Inspect File / Vision" },
  list_directory: { icon: "📁", badge: "badge-teal", label: "List Dir" },
  find_file: { icon: "🔎", badge: "badge-teal", label: "Find File" },
  search_directory: { icon: "🗂️", badge: "badge-teal", label: "Search Dir" },
  generate_image: { icon: "🎨", badge: "badge-emerald", label: "Generate Image" },
  generate_video: { icon: "🎬", badge: "badge-coral", label: "Veo 3.1 Video" },
  generate_video_clip: { icon: "🎬", badge: "badge-coral", label: "Veo 3.1 Trailer Clip" },
  log_vision_critique: { icon: "🧐", badge: "badge-amber", label: "Vision Critique" },
  validate_html5_game: { icon: "🕹️", badge: "badge-emerald", label: "HTML5 QA Validator" },
  run_bot_tournament: { icon: "⚔️", badge: "badge-amber", label: "Gladiator Arena" },
  verify_claim_math: { icon: "🧮", badge: "badge-cyan", label: "Math Router" },
  solve_crawl_constraints: { icon: "🍜", badge: "badge-emerald", label: "Constraint Solver" },
  export_ics_calendar: { icon: "📅", badge: "badge-teal", label: "iCalendar Export" },
  roll_crypto_d20: { icon: "🎲", badge: "badge-amber", label: "Crypto CSPRNG d20" },
  manage_hero_state: { icon: "🛡️", badge: "badge-teal", label: "Hero State Machine" },
  emit_dag_step: { icon: "📍", badge: "badge-cyan", label: "DAG Milestone" },
  record_pruned_branch: { icon: "✂️", badge: "badge-coral", label: "Prune Dead Branch" },
  start_subagent: { icon: "🤝", badge: "badge-teal", label: "Spawn Subagent" },
  invoke_subagent: { icon: "🤝", badge: "badge-teal", label: "Invoke Subagent" },
  create_custom_tool: { icon: "🛠️", badge: "badge-amber", label: "Synthesize Python Tool" },
  build_custom_agent: { icon: "🏗️", badge: "badge-cyan", label: "Compile Custom Agent" },
  list_registered_agents_and_tools: { icon: "📋", badge: "badge-teal", label: "Inspect Registry" },
  ask_question: { icon: "💬", badge: "badge-amber", label: "HITL Choice" },
};

function getToolMeta(toolName) {
  return TOOL_META[toolName] || { icon: "⚙️", badge: "badge-cyan", label: toolName || "Tool" };
}

function fmtInt(n) {
  const num = Number(n || 0);
  return Number.isFinite(num) ? num.toLocaleString("en-US") : "0";
}

function fmtBytes(bytes) {
  const b = Number(bytes || 0);
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

function fmtLatency(ms) {
  const v = Number(ms || 0);
  if (v <= 0) return "0 ms";
  if (v < 1000) return `${Math.round(v)} ms`;
  return `${(v / 1000).toFixed(1)}s`;
}

function estimateFlashCostUSD(tok = {}) {
  // Illustrative Gemini Flash blended telemetry estimate ($0.15/1M input, $0.0375/1M cached, $0.60/1M output+thoughts)
  const prompt = Math.max(0, Number(tok.prompt_tokens || 0) - Number(tok.cached_tokens || 0));
  const cached = Math.max(0, Number(tok.cached_tokens || 0));
  const out = Math.max(0, Number(tok.candidates_tokens || 0) + Number(tok.thoughts_tokens || 0));
  const cost = (prompt * 0.15 + cached * 0.0375 + out * 0.6) / 1_000_000;
  return cost < 0.0001 && (prompt + cached + out) > 0 ? "<$0.0001" : `$${cost.toFixed(4)}`;
}

function escapeHtml(raw) {
  return String(raw ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function relativeTime(isoStr) {
  if (!isoStr) return "";
  const dt = new Date(isoStr);
  if (Number.isNaN(dt.getTime())) return "";
  const sec = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 1000));
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

/* Safe, fast Markdown renderer supporting fenced code, tables, lists, bold, links */
export function renderMarkdown(mdText) {
  if (!mdText) return "";
  const codeBlocks = [];
  let text = String(mdText).replace(/\r\n/g, "\n");

  // 1. Extract fenced code blocks first
  text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    const safeLang = escapeHtml(lang || "code");
    const safeCode = escapeHtml(code.replace(/\n$/, ""));
    codeBlocks.push(
      `<div class="my-2 rounded-lg overflow-hidden" style="border: 1px solid var(--border-subtle); background: var(--bg-inset);">` +
        `<div class="flex items-center justify-between px-3 py-1 text-[11px] font-mono-num" style="background: var(--bg-elevated); color: var(--text-muted); border-bottom: 1px solid var(--border-subtle);">` +
          `<span>${safeLang}</span>` +
          `<button type="button" class="copy-code-btn hover:underline" style="background:none;border:none;color:var(--accent-cyan);cursor:pointer;">Copy</button>` +
        `</div>` +
        `<pre style="margin:0;border:none;"><code>${safeCode}</code></pre>` +
      `</div>`
    );
    return `\u0000CODEBLOCK_${idx}\u0000`;
  });

  // 2. Escape remaining HTML
  text = escapeHtml(text);

  // 3. Inline formatting helper
  const fmtInline = (line) =>
    line
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/api\/gateway\/media\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
      );

  // 4. Block-level line parser (headings, tables, lists, blockquotes, paragraphs)
  const lines = text.split("\n");
  const out = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    if (/^\u0000CODEBLOCK_(\d+)\u0000$/.test(trimmed)) {
      out.push(trimmed);
      i++;
      continue;
    }

    // Markdown Table detection
    if (
      trimmed.includes("|") &&
      i + 1 < lines.length &&
      /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(lines[i + 1])
    ) {
      const parseCells = (row) =>
        row
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((c) => fmtInline(c.trim()));

      const headers = parseCells(lines[i]);
      i += 2; // skip header + separator
      const rows = [];
      while (i < lines.length && lines[i].trim().includes("|") && lines[i].trim() !== "") {
        rows.push(parseCells(lines[i]));
        i++;
      }
      out.push(
        `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>` +
          `<tbody>${rows
            .map((r) => `<tr>${headers.map((_, ci) => `<td>${r[ci] ?? ""}</td>`).join("")}</tr>`)
            .join("")}</tbody></table>`
      );
      continue;
    }

    // Headings
    const hMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (hMatch) {
      const lvl = hMatch[1].length;
      out.push(`<h${lvl}>${fmtInline(hMatch[2])}</h${lvl}>`);
      i++;
      continue;
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
      out.push(`<hr style="border:none;border-top:1px solid var(--border-subtle);margin:10px 0;" />`);
      i++;
      continue;
    }

    // Blockquote
    if (trimmed.startsWith("&gt;")) {
      const qLines = [];
      while (i < lines.length && lines[i].trim().startsWith("&gt;")) {
        qLines.push(fmtInline(lines[i].trim().replace(/^&gt;\s?/, "")));
        i++;
      }
      out.push(`<blockquote>${qLines.join("<br/>")}</blockquote>`);
      continue;
    }

    // Unordered list
    if (/^[-*•]\s+/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
        items.push(`<li>${fmtInline(lines[i].trim().replace(/^[-*•]\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    // Ordered list
    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(`<li>${fmtInline(lines[i].trim().replace(/^\d+\.\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    // Paragraph
    const pLines = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,4}\s|[-*•]\s|\d+\.\s|&gt;|\u0000CODEBLOCK_)/.test(lines[i].trim())
    ) {
      pLines.push(fmtInline(lines[i]));
      i++;
    }
    out.push(`<p>${pLines.join("<br/>")}</p>`);
  }

  let html = out.join("\n");
  html = html.replace(/\u0000CODEBLOCK_(\d+)\u0000/g, (_, idx) => codeBlocks[Number(idx)] || "");
  return html;
}

/* --------------------------------------------------------------------------
   4. Central Studio State
   -------------------------------------------------------------------------- */
function safeStorageGet(key, fallback) {
  try {
    if (typeof localStorage !== "undefined") {
      return localStorage.getItem(key) || fallback;
    }
  } catch {
    // Ignore sandboxed storage restrictions
  }
  return fallback;
}

function safeStorageSet(key, val) {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(key, val);
    }
  } catch {
    // Ignore sandboxed storage restrictions
  }
}

const state = {
  theme: safeStorageGet("ag_studio_theme", "dark"),
  userId: safeStorageGet("ag_studio_user_id", "cbribiescas"),
  agentId: "antigravity",
  previewPresetId: null, // set when previewing an unbuilt scenario's DAG
  conversationId: null,
  antigravityConversationId: null,
  activeTurnCount: 0,

  agents: [],
  toolsCatalog: null,
  conversations: [],
  conversationTurns: [],
  userUsage: null,
  globalSummary: null,

  sidebarTab: "agents", // "agents" | "presets" | "threads"
  filterAgentThreads: false,
  leaderboardTab: "agents", // "agents" | "users" | "convs"
  dagMode: "blueprint", // "blueprint" | "registry"

  // SVG DAG Runtime State
  currentGraph: { title: "", badge: "", nodes: [], edges: [] },
  nodeStates: {}, // nodeId -> { status, summary, toolCalls: [] }
  edgeStates: {}, // edgeKey -> "active" | "completed" | "retry" | "pruned" | "bypassed"
  selectedNodeId: null,
  dagZoom: 1,
  dagPanX: 0,
  dagPanY: 0,
  lastTurnEvents: [],
  sequentialCounters: {},

  // Streaming State
  isStreaming: false,
  abortController: null,
  latencyTimerId: null,
  streamStartMs: 0,
};

/* --------------------------------------------------------------------------
   5. SVG DAG Graph Resolution, Auto-Layout & Real-Time Animator
   -------------------------------------------------------------------------- */
const SVG_NS = "http://www.w3.org/2000/svg";
const NODE_W = 148;
const NODE_H = 48;

function resolveCanonicalKey(agentObj, agentId) {
  const id = String(agentId || agentObj?.agent_id || "").toLowerCase();
  if (CANONICAL_DAG_BLUEPRINTS[id]) return id;
  if (id === "gemini_antigravity_demo" || id === "gemini-antigravity-demo" || agentObj?.is_builder) {
    return "antigravity";
  }
  const topo = String(agentObj?.dag_topology || "").toLowerCase();
  if (topo.includes("sequential") || topo.includes("trailer")) return "trailer-director";
  if (topo.includes("self-heal") || topo.includes("generator-verifier") || topo.includes("arcade")) return "arcade-builder";
  if (topo.includes("shark") || topo.includes("map-reduce") || topo.includes("parallel")) return "shark-tank-panel";
  if (topo.includes("adversarial") || topo.includes("cross-exam") || topo.includes("debate")) return "supreme-court-debate";
  if (topo.includes("tournament") || topo.includes("gladiator") || topo.includes("bracket")) return "bot-gladiator-arena";
  if (topo.includes("vision") || topo.includes("critic") || topo.includes("reflection")) return "perfectionist-art-director";
  if (topo.includes("router") || topo.includes("conditional") || topo.includes("diamond")) return "mythbuster-router";
  if (topo.includes("tree") || topo.includes("prune") || topo.includes("six")) return "six-degrees-detective";
  if (topo.includes("hourglass") || topo.includes("gather") || topo.includes("foodie") || topo.includes("crawl")) return "food-crawl-planner";
  if (topo.includes("hitl") || topo.includes("dnd") || topo.includes("crypto") || topo.includes("state machine")) return "corporate-dnd-master";
  return null;
}

/* Automatic layered topological layout for custom registry dag_nodes / dag_edges */
function layoutCustomRegistryGraph(agentObj) {
  const rawNodes = Array.isArray(agentObj?.dag_nodes) ? agentObj.dag_nodes : [];
  const rawEdges = Array.isArray(agentObj?.dag_edges) ? agentObj.dag_edges : [];
  if (!rawNodes.length) {
    return structuredClone(CANONICAL_DAG_BLUEPRINTS.antigravity);
  }

  const nodeMap = new Map();
  rawNodes.forEach((n, idx) => {
    const id = String(n.id || n.node_id || `node_${idx + 1}`);
    const tools = Array.isArray(n.tools) ? n.tools : [];
    nodeMap.set(id, {
      id,
      label: String(n.label || n.name || id).slice(0, 22),
      sub: tools[0] || String(n.type || "step"),
      type: String(n.type || "process"),
      tools,
      x: typeof n.x === "number" ? n.x : null,
      y: typeof n.y === "number" ? n.y : null,
    });
  });

  const validEdges = [];
  rawEdges.forEach((e) => {
    const from = String(e.from || e.source || "");
    const to = String(e.to || e.target || "");
    if (nodeMap.has(from) && nodeMap.has(to)) {
      validEdges.push({
        from,
        to,
        label: String(e.label || e.condition || ""),
        isLoop: Boolean(e.isLoop),
      });
    }
  });

  // Compute Longest-Path DAG layers while breaking cycles cleanly
  const ids = Array.from(nodeMap.keys());
  const layerOf = {};
  ids.forEach((id, i) => {
    layerOf[id] = i === 0 ? 0 : 0;
  });

  const visitedPairs = new Set();
  for (let pass = 0; pass < ids.length; pass++) {
    validEdges.forEach((e) => {
      const pairKey = `${e.from}->${e.to}`;
      if (e.from === e.to) {
        e.isLoop = true;
        return;
      }
      // Detect back-edge if `to` already precedes `from` in input order and creates cycle
      const fromIdx = ids.indexOf(e.from);
      const toIdx = ids.indexOf(e.to);
      if (toIdx < fromIdx) {
        e.isLoop = true;
        e.curveY = -74;
        return;
      }
      if (!visitedPairs.has(pairKey) || layerOf[e.to] < layerOf[e.from] + 1) {
        layerOf[e.to] = Math.min(ids.length - 1, Math.max(layerOf[e.to], layerOf[e.from] + 1));
        visitedPairs.add(pairKey);
      }
    });
  }

  const buckets = new Map();
  let maxLayer = 0;
  ids.forEach((id) => {
    const l = layerOf[id] || 0;
    maxLayer = Math.max(maxLayer, l);
    if (!buckets.has(l)) buckets.set(l, []);
    buckets.get(l).push(nodeMap.get(id));
  });

  const marginX = 110;
  const usableW = 1000 - marginX * 2;
  buckets.forEach((group, layer) => {
    const x = maxLayer === 0 ? 500 : marginX + (layer / maxLayer) * usableW;
    const count = group.length;
    group.forEach((node, idx) => {
      if (node.x === null) node.x = Math.round(x);
      if (node.y === null) {
        if (count === 1) node.y = 140;
        else {
          const span = Math.min(184, (count - 1) * 84);
          node.y = Math.round(140 - span / 2 + (idx / (count - 1)) * span);
        }
      }
    });
  });

  return {
    title: agentObj?.dag_topology || agentObj?.display_name || "Registered Agent DAG",
    badge: "Registry Spec",
    nodes: Array.from(nodeMap.values()),
    edges: validEdges,
  };
}

function buildActiveGraphModel() {
  const targetId = state.previewPresetId || state.agentId;
  const agentObj = state.agents.find((a) => a.agent_id === targetId);
  const canonicalKey = resolveCanonicalKey(agentObj, targetId);

  let graph;
  if (state.dagMode === "registry" && agentObj && Array.isArray(agentObj.dag_nodes) && agentObj.dag_nodes.length > 0) {
    graph = layoutCustomRegistryGraph(agentObj);
  } else if (canonicalKey && CANONICAL_DAG_BLUEPRINTS[canonicalKey]) {
    graph = structuredClone(CANONICAL_DAG_BLUEPRINTS[canonicalKey]);
    if (agentObj?.dag_topology) {
      graph.title = `${agentObj.display_name || targetId} — ${agentObj.dag_topology}`;
    }
  } else if (agentObj) {
    graph = layoutCustomRegistryGraph(agentObj);
  } else {
    graph = structuredClone(CANONICAL_DAG_BLUEPRINTS.antigravity);
  }

  state.currentGraph = graph;
  const nextNodeStates = {};
  graph.nodes.forEach((n) => {
    nextNodeStates[n.id] = state.nodeStates[n.id] || {
      status: "idle",
      summary: "",
      toolCalls: [],
    };
  });
  state.nodeStates = nextNodeStates;
  renderDagSvg();
}

function resetDagExecutionStatuses() {
  state.nodeStates = {};
  state.edgeStates = {};
  state.sequentialCounters = {};
  state.currentGraph.nodes.forEach((n) => {
    state.nodeStates[n.id] = { status: "idle", summary: "", toolCalls: [] };
  });
  renderDagSvg();
}

function edgeKey(e) {
  return `${e.from}->${e.to}`;
}

function computeEdgePath(src, dst, edge) {
  const sx = src.x;
  const sy = src.y;
  const dx = dst.x;
  const dy = dst.y;

  if (edge.isLoop || dx <= sx + 20) {
    // Self-healing / cross-exam curved arc
    if (Math.abs(dx - sx) < 25 && Math.abs(dy - sy) > 35) {
      // Vertical ping-pong (e.g., Counsel PRO <-> Counsel CON)
      const dir = dy > sy ? 1 : -1;
      const offsetX = dir > 0 ? 34 : -34;
      const x1 = sx + offsetX;
      const y1 = sy + dir * (NODE_H / 2 + 2);
      const x2 = dx + offsetX;
      const y2 = dy - dir * (NODE_H / 2 + 4);
      const cx = sx + offsetX * 2.2;
      const cy = (y1 + y2) / 2;
      return {
        d: `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`,
        lx: cx,
        ly: cy,
      };
    }
    const arcY = Math.min(sy, dy) + (edge.curveY || -74);
    const startX = sx;
    const startY = sy - NODE_H / 2;
    const endX = dx;
    const endY = dy - NODE_H / 2 - 2;
    const midX = (startX + endX) / 2;
    return {
      d: `M ${startX} ${startY} C ${startX} ${arcY}, ${endX} ${arcY}, ${endX} ${endY}`,
      lx: midX,
      ly: arcY + 13,
    };
  }

  const startX = sx + NODE_W / 2;
  const startY = sy;
  const endX = dx - NODE_W / 2 - 3;
  const endY = dy;
  const cOffset = Math.max(36, (endX - startX) * 0.46);
  return {
    d: `M ${startX} ${startY} C ${startX + cOffset} ${startY}, ${endX - cOffset} ${endY}, ${endX} ${endY}`,
    lx: (startX + endX) / 2,
    ly: (startY + endY) / 2 - 7,
  };
}

function applyDagTransform() {
  const g = document.getElementById("dag-pan-zoom-group");
  if (!g) return;
  g.setAttribute(
    "transform",
    `translate(${state.dagPanX}, ${state.dagPanY}) scale(${state.dagZoom})`
  );
}

export function renderDagSvg() {
  const edgesLayer = document.getElementById("dag-edges-layer");
  const nodesLayer = document.getElementById("dag-nodes-layer");
  const badgeEl = document.getElementById("dag-agent-badge");
  const titleEl = document.getElementById("dag-topology-title");
  if (!edgesLayer || !nodesLayer) return;

  const targetId = state.previewPresetId || state.agentId;
  if (badgeEl) {
    badgeEl.textContent = state.previewPresetId ? `preview: ${targetId}` : targetId;
  }
  if (titleEl) {
    titleEl.textContent = state.currentGraph.title || "Agent DAG Topology";
  }

  edgesLayer.innerHTML = "";
  nodesLayer.innerHTML = "";

  const nodeById = new Map(state.currentGraph.nodes.map((n) => [n.id, n]));

  // 1. Render Edges
  state.currentGraph.edges.forEach((edge) => {
    const src = nodeById.get(edge.from);
    const dst = nodeById.get(edge.to);
    if (!src || !dst) return;

    const geom = computeEdgePath(src, dst, edge);
    const eState = state.edgeStates[edgeKey(edge)] || "idle";

    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", geom.d);
    let cls = "dag-edge-path";
    let marker = "url(#arrow-idle)";
    if (edge.isLoop) cls += " edge-loop";
    if (eState === "active") {
      cls += " edge-active";
      marker = "url(#arrow-active)";
    } else if (eState === "completed") {
      cls += " edge-completed";
      marker = "url(#arrow-completed)";
    } else if (eState === "retry") {
      cls += " edge-retry";
      marker = "url(#arrow-retry)";
    } else if (eState === "pruned") {
      cls += " edge-pruned";
      marker = "url(#arrow-pruned)";
    } else if (eState === "bypassed") {
      cls += " edge-bypassed";
    }
    path.setAttribute("class", cls);
    path.setAttribute("marker-end", marker);
    edgesLayer.appendChild(path);

    if (edge.label) {
      const lblText = edge.label.slice(0, 18);
      const pillW = Math.max(36, lblText.length * 5.7 + 10);
      const rect = document.createElementNS(SVG_NS, "rect");
      rect.setAttribute("x", String(geom.lx - pillW / 2));
      rect.setAttribute("y", String(geom.ly - 8));
      rect.setAttribute("width", String(pillW));
      rect.setAttribute("height", "14");
      rect.setAttribute("rx", "4");
      rect.setAttribute("class", "dag-edge-label-bg");
      edgesLayer.appendChild(rect);

      const txt = document.createElementNS(SVG_NS, "text");
      txt.setAttribute("x", String(geom.lx));
      txt.setAttribute("y", String(geom.ly + 2));
      txt.setAttribute("text-anchor", "middle");
      txt.setAttribute("class", "dag-edge-label");
      txt.textContent = lblText;
      edgesLayer.appendChild(txt);
    }
  });

  // 2. Render Nodes
  state.currentGraph.nodes.forEach((node) => {
    const rt = state.nodeStates[node.id] || { status: "idle", summary: "", toolCalls: [] };
    const status = rt.status || "idle";

    const g = document.createElementNS(SVG_NS, "g");
    g.setAttribute("transform", `translate(${node.x - NODE_W / 2}, ${node.y - NODE_H / 2})`);
    g.setAttribute("class", `dag-node-group${state.selectedNodeId === node.id ? " selected" : ""}`);
    g.setAttribute("data-node-id", node.id);
    g.setAttribute("data-status", status);

    // Pulse Halo
    const halo = document.createElementNS(SVG_NS, "rect");
    halo.setAttribute("x", "-3");
    halo.setAttribute("y", "-3");
    halo.setAttribute("width", String(NODE_W + 6));
    halo.setAttribute("height", String(NODE_H + 6));
    halo.setAttribute("rx", node.type === "router" ? "14" : "11");
    halo.setAttribute("class", "dag-node-halo");
    g.appendChild(halo);

    // Body (Diamond-accented chamfer for router nodes, crisp rounded rect for standard nodes)
    if (node.type === "router") {
      const poly = document.createElementNS(SVG_NS, "polygon");
      const pts = `14,0 ${NODE_W - 14},0 ${NODE_W},${NODE_H / 2} ${NODE_W - 14},${NODE_H} 14,${NODE_H} 0,${NODE_H / 2}`;
      poly.setAttribute("points", pts);
      poly.setAttribute("class", "dag-node-body");
      g.appendChild(poly);
    } else {
      const rect = document.createElementNS(SVG_NS, "rect");
      rect.setAttribute("width", String(NODE_W));
      rect.setAttribute("height", String(NODE_H));
      rect.setAttribute("rx", "10");
      rect.setAttribute("class", "dag-node-body");
      g.appendChild(rect);
    }

    // Status Indicator Dot / Glyph
    const statusGlyphMap = {
      idle: { fill: "hsl(215, 14%, 40%)", char: "" },
      thinking: { fill: "hsl(38, 92%, 54%)", char: "…" },
      running: { fill: "hsl(199, 89%, 52%)", char: "⚡" },
      completed: { fill: "hsl(156, 68%, 45%)", char: "✓" },
      routed: { fill: "hsl(156, 68%, 45%)", char: "◇" },
      retry: { fill: "hsl(38, 92%, 54%)", char: "↺" },
      pruned: { fill: "hsl(8, 82%, 60%)", char: "✂" },
      error: { fill: "hsl(8, 82%, 60%)", char: "!" },
      bypassed: { fill: "hsl(215, 12%, 34%)", char: "–" },
    };
    const stMeta = statusGlyphMap[status] || statusGlyphMap.idle;

    const badgeCircle = document.createElementNS(SVG_NS, "circle");
    badgeCircle.setAttribute("cx", String(NODE_W - 15));
    badgeCircle.setAttribute("cy", "14");
    badgeCircle.setAttribute("r", "6.5");
    badgeCircle.setAttribute("fill", stMeta.fill);
    badgeCircle.setAttribute("opacity", status === "idle" ? "0.45" : "1");
    g.appendChild(badgeCircle);

    if (stMeta.char) {
      const glyph = document.createElementNS(SVG_NS, "text");
      glyph.setAttribute("x", String(NODE_W - 15));
      glyph.setAttribute("y", "17.5");
      glyph.setAttribute("text-anchor", "middle");
      glyph.setAttribute("font-size", "8.5");
      glyph.setAttribute("font-weight", "700");
      glyph.setAttribute("fill", "#081018");
      glyph.textContent = stMeta.char;
      g.appendChild(glyph);
    }

    // Node Title
    const title = document.createElementNS(SVG_NS, "text");
    title.setAttribute("x", node.type === "router" ? "18" : "11");
    title.setAttribute("y", "20");
    title.setAttribute("class", "dag-node-title");
    title.textContent = (node.label || node.id).slice(0, 18);
    g.appendChild(title);

    // Subtitle / Live Tool Count
    const sub = document.createElementNS(SVG_NS, "text");
    sub.setAttribute("x", node.type === "router" ? "18" : "11");
    sub.setAttribute("y", "36");
    sub.setAttribute("class", "dag-node-sub");
    const callCount = rt.toolCalls?.length || 0;
    const baseSub = rt.dynamicSub || node.sub || node.type || "";
    sub.textContent = callCount > 0 ? `${baseSub.slice(0, 14)} (${callCount}x)` : baseSub.slice(0, 20);
    g.appendChild(sub);

    g.addEventListener("click", (ev) => {
      ev.stopPropagation();
      state.selectedNodeId = node.id;
      openNodeInspector(node.id);
      renderDagSvg();
    });

    nodesLayer.appendChild(g);
  });

  applyDagTransform();
  if (state.selectedNodeId) {
    openNodeInspector(state.selectedNodeId);
  }
}

function openNodeInspector(nodeId) {
  const box = document.getElementById("dag-node-inspector");
  const node = state.currentGraph.nodes.find((n) => n.id === nodeId);
  if (!box || !node) return;
  const rt = state.nodeStates[node.id] || { status: "idle", summary: "", toolCalls: [] };

  document.getElementById("inspector-node-type").textContent = node.type || "step";
  document.getElementById("inspector-node-title").textContent = node.label || node.id;
  document.getElementById("inspector-node-id").textContent = node.id;
  document.getElementById("inspector-node-status").textContent = rt.status || "idle";

  const toolsEl = document.getElementById("inspector-node-tools");
  const boundTools = node.tools || [];
  toolsEl.innerHTML = boundTools.length
    ? boundTools.map((t) => `<span class="badge-chip font-mono-num">${escapeHtml(t)}</span>`).join("")
    : `<span class="text-[11px]" style="color:var(--text-muted);">Orchestration / Synthesis Step</span>`;

  const sumEl = document.getElementById("inspector-node-summary");
  if (rt.summary) {
    sumEl.textContent = rt.summary;
  } else if (rt.toolCalls?.length) {
    sumEl.textContent = `Executed ${rt.toolCalls.length} tool call(s): ${rt.toolCalls.join(", ")}`;
  } else {
    sumEl.textContent = "Awaiting turn execution on this node.";
  }
  box.classList.remove("hidden");
}

function activateIncomingEdges(targetNodeId, edgeStatus = "active") {
  state.currentGraph.edges.forEach((e) => {
    if (e.to === targetNodeId && !e.isLoop) {
      state.edgeStates[edgeKey(e)] = edgeStatus;
    }
  });
}

function findMatchingNodeForTool(toolName, args = {}) {
  const nodes = state.currentGraph.nodes;
  if (!nodes.length) return null;

  // 1. Subagent delegation match (e.g., numbers_hawk, counsel_pro)
  if (toolName === "start_subagent" || toolName === "invoke_subagent") {
    const subTarget = String(
      args.agent_name || args.subagent_name || args.name || args.prompt || ""
    ).toLowerCase();
    const matchedSub = nodes.find((n) => {
      if (n.id.toLowerCase() === subTarget) return true;
      if (Array.isArray(n.matchKeys) && n.matchKeys.some((k) => subTarget.includes(k))) return true;
      return n.type === "subagent" && subTarget.includes(n.id.toLowerCase());
    });
    if (matchedSub) return matchedSub;
    const anyIdleSub = nodes.find(
      (n) => n.type === "subagent" && state.nodeStates[n.id]?.status === "idle"
    );
    if (anyIdleSub) return anyIdleSub;
  }

  // 2. File creation match (e.g. bot_a.py, bot_b.py, bot_c.py, maxwell_crawl_card.html)
  if (toolName === "create_file" || toolName === "edit_file") {
    const fTarget = String(args.TargetFile || args.file_path || args.path || "").toLowerCase();
    if (fTarget) {
      const matchedFileNode = nodes.find(
        (n) =>
          Array.isArray(n.matchKeys) &&
          n.matchKeys.some((k) => fTarget.includes(k))
      );
      if (matchedFileNode) return matchedFileNode;
    }
  }

  // 3. Exact ID match
  const exactId = nodes.find((n) => n.id === toolName);
  if (exactId) return exactId;

  // 4. Nodes binding this toolName (handle sequential slots like Draft V1 -> Masterpiece V2)
  const candidates = nodes.filter(
    (n) => Array.isArray(n.tools) && n.tools.includes(toolName)
  );
  if (candidates.length === 1) return candidates[0];
  if (candidates.length > 1) {
    const unvisited = candidates.find(
      (n) => state.nodeStates[n.id]?.status !== "completed"
    );
    return unvisited || candidates[candidates.length - 1];
  }

  // 5. Fallback to middle process node
  return nodes.find((n) => n.type !== "input" && n.type !== "output") || nodes[0];
}

export function applyEventToDag(ev) {
  const nodes = state.currentGraph.nodes;
  if (!nodes.length) return;
  const captionEl = document.getElementById("dag-step-caption");
  const statusPill = document.getElementById("dag-live-status-pill");

  if (ev.type === "turn_start") {
    resetDagExecutionStatuses();
    const first = nodes[0];
    if (first) {
      state.nodeStates[first.id].status = "completed";
      state.nodeStates[first.id].summary = `Turn #${ev.turn_number || 1} started`;
    }
    if (nodes[1]) {
      state.nodeStates[nodes[1].id].status = "thinking";
      activateIncomingEdges(nodes[1].id, "active");
    }
    if (statusPill) {
      statusPill.className = "badge-chip badge-cyan font-mono-num";
      statusPill.textContent = `⚡ STREAMING TURN #${ev.turn_number || 1}`;
    }
    renderDagSvg();
    return;
  }

  if (ev.type === "thought") {
    const runningExists = nodes.some((n) => state.nodeStates[n.id]?.status === "running");
    if (!runningExists) {
      const target =
        nodes.find((n) => state.nodeStates[n.id]?.status === "thinking") ||
        nodes.find((n) => state.nodeStates[n.id]?.status === "idle" && n.type !== "output");
      if (target) state.nodeStates[target.id].status = "thinking";
    }
    if (captionEl && ev.text) {
      captionEl.textContent = `💭 ${String(ev.text).replace(/\s+/g, " ").trim().slice(0, 48)}…`;
    }
    renderDagSvg();
    return;
  }

  if (ev.type === "tool_call") {
    const node = findMatchingNodeForTool(ev.tool_name, ev.args || {});
    if (node) {
      const rt = state.nodeStates[node.id];
      rt.status = "running";
      rt.toolCalls.push(ev.tool_name);
      rt.summary = `Calling ${ev.tool_name}…`;
      ev._matchedDagNodeId = node.id;
      activateIncomingEdges(node.id, "active");
    }
    if (captionEl) captionEl.textContent = `🔧 ${ev.tool_name}()`;
    renderDagSvg();
    return;
  }

  if (ev.type === "tool_result") {
    const node =
      nodes.find((n) => state.nodeStates[n.id]?.status === "running" && state.nodeStates[n.id]?.toolCalls.includes(ev.tool_name)) ||
      findMatchingNodeForTool(ev.tool_name, {});
    if (node) {
      const rt = state.nodeStates[node.id];
      rt.status = ev.is_error ? "error" : "completed";
      rt.summary = ev.is_error ? `Error in ${ev.tool_name}` : `${ev.tool_name} completed`;
      activateIncomingEdges(node.id, ev.is_error ? "pruned" : "completed");
    }
    renderDagSvg();
    return;
  }

  if (ev.type === "dag_step") {
    const rawId = String(ev.node_id || "").toLowerCase();
    const rawLabel = String(ev.node_label || "").toLowerCase();
    let target =
      nodes.find((n) => n.id.toLowerCase() === rawId) ||
      nodes.find((n) => Array.isArray(n.matchKeys) && n.matchKeys.some((k) => rawId.includes(k) || rawLabel.includes(k)));

    if (!target && ev.status === "pruned") {
      target =
        nodes.find((n) => n.type === "prunable" && state.nodeStates[n.id]?.status !== "pruned") ||
        nodes.find((n) => n.type === "prunable");
      if (target && ev.node_label) {
        state.nodeStates[target.id].dynamicSub = `✂ ${ev.node_label.slice(0, 16)}`;
      }
    }
    if (!target && ev.source_tool) {
      target = findMatchingNodeForTool(ev.source_tool, {});
    }

    if (target) {
      const st = String(ev.status || "completed").toLowerCase();
      state.nodeStates[target.id].status = st;
      if (ev.summary) state.nodeStates[target.id].summary = ev.summary;

      if (st === "pruned") {
        activateIncomingEdges(target.id, "pruned");
      } else if (st === "retry") {
        // Light up self-healing / reflection curved loop edge!
        state.currentGraph.edges.forEach((e) => {
          if (e.from === target.id && e.isLoop) {
            state.edgeStates[edgeKey(e)] = "retry";
          }
        });
      } else if (st === "routed") {
        activateIncomingEdges(target.id, "completed");
        // Dim unchosen conditional router sibling branch
        state.currentGraph.edges.forEach((e) => {
          if (e.branchKey && e.branchKey !== target.id) {
            state.edgeStates[edgeKey(e)] = "bypassed";
            if (state.nodeStates[e.to] && state.nodeStates[e.to].status === "idle") {
              state.nodeStates[e.to].status = "bypassed";
            }
          }
        });
      } else if (st === "completed") {
        activateIncomingEdges(target.id, "completed");
      }
    }
    if (captionEl) captionEl.textContent = `📍 ${ev.node_label || ev.node_id}: ${ev.status}`;
    renderDagSvg();
    return;
  }

  if (ev.type === "turn_complete") {
    const outNodes = nodes.filter((n) => n.type === "output");
    outNodes.forEach((out) => {
      state.nodeStates[out.id].status = "completed";
      state.nodeStates[out.id].summary = `Delivered in ${fmtLatency(ev.latency_ms)}`;
      activateIncomingEdges(out.id, "completed");
    });
    // Clear any lingering "thinking" state on intermediate nodes
    nodes.forEach((n) => {
      if (state.nodeStates[n.id]?.status === "thinking") {
        state.nodeStates[n.id].status = "completed";
      }
    });
    if (statusPill) {
      statusPill.className = "badge-chip badge-emerald font-mono-num";
      statusPill.textContent = `✓ TURN #${ev.turn_number || 1} COMPLETE • ${fmtLatency(ev.latency_ms)}`;
    }
    if (captionEl) {
      captionEl.textContent = `Completed (${(ev.tool_calls || []).length} tools, ${(ev.media || []).length} artifacts)`;
    }
    renderDagSvg();
  }

  if (ev.type === "error") {
    if (statusPill) {
      statusPill.className = "badge-chip badge-coral font-mono-num";
      statusPill.textContent = "⚠ TURN ERROR";
    }
    renderDagSvg();
  }
}

/* --------------------------------------------------------------------------
   6. Telemetry HUD & Left Sidebar Renderers
   -------------------------------------------------------------------------- */
function updateStackedBar(prefix, tok = {}) {
  const p = Math.max(0, Number(tok.prompt_tokens || 0));
  const c = Math.max(0, Number(tok.cached_tokens || 0));
  const th = Math.max(0, Number(tok.thoughts_tokens || 0));
  const cand = Math.max(0, Number(tok.candidates_tokens || 0));
  const sub = Math.max(0, Number(tok.subagent_tokens || 0));
  const denom = Math.max(1, p + c + th + cand + sub);

  const setW = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.style.width = `${Math.min(100, (val / denom) * 100).toFixed(1)}%`;
  };
  setW(`${prefix}-bar-prompt`, p);
  setW(`${prefix}-bar-cached`, c);
  setW(`${prefix}-bar-thoughts`, th);
  setW(`${prefix}-bar-candidates`, cand);
  setW(`${prefix}-bar-subagent`, sub);
}

function updateRequestHud(reqTokens = {}, latencyMs = 0) {
  const tot = Number(reqTokens.total_tokens || 0);
  const prompt = Number(reqTokens.prompt_tokens || 0);
  const cached = Number(reqTokens.cached_tokens || 0);
  const sub = Number(reqTokens.subagent_tokens || 0);

  document.getElementById("hud-req-total").textContent = fmtInt(tot);
  document.getElementById("hud-req-latency").textContent = fmtLatency(latencyMs);
  document.getElementById("hud-req-cost").textContent = estimateFlashCostUSD(reqTokens);
  document.getElementById("hud-req-prompt").textContent = fmtInt(prompt);
  document.getElementById("hud-req-cached").textContent = fmtInt(cached);
  document.getElementById("hud-req-thoughts").textContent = fmtInt(reqTokens.thoughts_tokens);
  document.getElementById("hud-req-candidates").textContent = fmtInt(reqTokens.candidates_tokens);
  document.getElementById("hud-req-subagent").textContent = fmtInt(sub);

  const cachePct = prompt > 0 ? Math.min(100, Math.round((cached / prompt) * 100)) : 0;
  const subPct = tot > 0 ? Math.min(100, Math.round((sub / tot) * 100)) : 0;
  document.getElementById("hud-req-cache-pct").textContent = `${cachePct}%`;
  document.getElementById("hud-req-sub-pct").textContent = `${subPct}%`;

  updateStackedBar("req", reqTokens);
}

function updateConversationHud(convTokens = {}, turnCount = 0) {
  document.getElementById("hud-conv-total").textContent = fmtInt(convTokens.total_tokens);
  document.getElementById("hud-conv-turns").textContent = `${turnCount} turn${turnCount === 1 ? "" : "s"}`;
  document.getElementById("hud-conv-prompt").textContent = fmtInt(convTokens.prompt_tokens);
  document.getElementById("hud-conv-cached").textContent = fmtInt(convTokens.cached_tokens);
  document.getElementById("hud-conv-thoughts").textContent = fmtInt(convTokens.thoughts_tokens);
  document.getElementById("hud-conv-candidates").textContent = fmtInt(convTokens.candidates_tokens);
  document.getElementById("hud-conv-subagent").textContent = fmtInt(convTokens.subagent_tokens);

  const idDisplay = document.getElementById("hud-conv-id-display");
  if (state.conversationId) {
    idDisplay.textContent = `conv: ${state.conversationId.slice(0, 12)}…`;
    idDisplay.title = `Gateway conversation_id: ${state.conversationId}\nAntigravity SQLite trajectory: ${state.antigravityConversationId || "derived"}`;
  } else {
    idDisplay.textContent = "conv: (new thread)";
  }

  updateStackedBar("conv", convTokens);
  renderTurnSparkline();
}

function renderTurnSparkline() {
  const wrap = document.getElementById("hud-turn-sparkline-wrap");
  const container = document.getElementById("hud-turn-sparkline");
  if (!wrap || !container) return;
  const turns = state.conversationTurns || [];
  if (!turns.length) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  const maxTok = Math.max(1, ...turns.map((t) => Number(t.total_tokens || t.tokens?.total_tokens || 0)));
  container.innerHTML = turns
    .slice(-12)
    .map((t) => {
      const tot = Number(t.total_tokens || t.tokens?.total_tokens || 0);
      const hPct = Math.max(14, Math.round((tot / maxTok) * 100));
      return (
        `<div class="flex-1 flex flex-col items-center gap-0.5" title="Turn #${t.turn_number}: ${fmtInt(tot)} tokens (${fmtLatency(t.latency_ms)})">` +
          `<div style="height:${hPct}%; width:100%; min-height:4px; border-radius:3px 3px 1px 1px; background:var(--accent-cyan);"></div>` +
          `<span class="text-[9px] font-mono-num" style="color:var(--text-muted);">T${t.turn_number}</span>` +
        `</div>`
      );
    })
    .join("");
}

function updateUserMeter(usageObj) {
  const tok = usageObj?.tokens || usageObj || {};
  document.getElementById("user-meter-name").textContent = state.userId;
  document.getElementById("composer-user-label").textContent = state.userId;
  document.getElementById("user-meter-total").textContent = `${fmtInt(tok.total_tokens)} tok`;
  document.getElementById("user-meter-prompt").textContent = fmtInt(tok.prompt_tokens);
  document.getElementById("user-meter-thoughts").textContent = fmtInt(tok.thoughts_tokens);
  document.getElementById("user-meter-subagent").textContent = fmtInt(tok.subagent_tokens);

  const cCount = Number(usageObj?.conversation_count ?? 0);
  const tCount = Number(usageObj?.turn_count ?? 0);
  document.getElementById("user-convs-pill").textContent = `${cCount} convs • ${tCount} turns`;
  updateStackedBar("user", tok);
}

function renderGlobalLeaderboard() {
  const summary = state.globalSummary;
  if (!summary) return;
  const g = summary.global || {};
  document.getElementById("header-kpi-global-tokens").textContent = fmtInt(g.total_tokens);
  document.getElementById("hud-global-avg-lat").textContent = `avg ${fmtLatency(g.avg_latency_ms)}`;
  document.getElementById("hud-sum-users").textContent = fmtInt(g.user_count);
  document.getElementById("hud-sum-convs").textContent = fmtInt(g.conversation_count);
  document.getElementById("hud-sum-turns").textContent = fmtInt(g.turn_count);

  const listEl = document.getElementById("hud-leaderboard-list");
  if (!listEl) return;

  if (state.leaderboardTab === "agents") {
    const rows = summary.by_agent || [];
    if (!rows.length) {
      listEl.innerHTML = `<div class="text-xs p-3 text-center" style="color:var(--text-muted);">No agent turns recorded yet. Launch a preset or send a prompt!</div>`;
      return;
    }
    const maxTok = Math.max(1, ...rows.map((r) => Number(r.total_tokens || 0)));
    listEl.innerHTML = rows
      .map((r) => {
        const pct = Math.max(3, Math.round((Number(r.total_tokens || 0) / maxTok) * 100));
        const sub = Number(r.subagent_tokens || 0);
        return (
          `<div class="leaderboard-row space-y-1" data-select-agent="${escapeHtml(r.agent_id)}">` +
            `<div class="flex items-center justify-between gap-2 text-xs">` +
              `<strong class="font-mono-num truncate">${escapeHtml(r.agent_id)}</strong>` +
              `<span class="font-mono-num font-semibold" style="color:var(--accent-cyan);">${fmtInt(r.total_tokens)}</span>` +
            `</div>` +
            `<div class="h-1.5 rounded-full overflow-hidden" style="background:var(--bg-inset);">` +
              `<div style="width:${pct}%;height:100%;background:var(--accent-cyan);"></div>` +
            `</div>` +
            `<div class="flex items-center justify-between text-[10.5px] font-mono-num" style="color:var(--text-muted);">` +
              `<span>${r.conversation_count} conv • ${r.turn_count} turns</span>` +
              `<span>${sub > 0 ? `sub: ${fmtInt(sub)}` : "main"}</span>` +
            `</div>` +
          `</div>`
        );
      })
      .join("");

    listEl.querySelectorAll("[data-select-agent]").forEach((el) => {
      el.addEventListener("click", () => selectAgent(el.getAttribute("data-select-agent")));
    });
    return;
  }

  if (state.leaderboardTab === "users") {
    const rows = summary.by_user || [];
    if (!rows.length) {
      listEl.innerHTML = `<div class="text-xs p-3 text-center" style="color:var(--text-muted);">No user activity yet.</div>`;
      return;
    }
    const maxTok = Math.max(1, ...rows.map((r) => Number(r.total_tokens || 0)));
    listEl.innerHTML = rows
      .map((r) => {
        const pct = Math.max(3, Math.round((Number(r.total_tokens || 0) / maxTok) * 100));
        return (
          `<div class="leaderboard-row space-y-1" data-select-user="${escapeHtml(r.user_id)}">` +
            `<div class="flex items-center justify-between gap-2 text-xs">` +
              `<strong class="font-mono-num truncate">👤 ${escapeHtml(r.user_id)}</strong>` +
              `<span class="font-mono-num font-semibold" style="color:var(--accent-emerald);">${fmtInt(r.total_tokens)}</span>` +
            `</div>` +
            `<div class="h-1.5 rounded-full overflow-hidden" style="background:var(--bg-inset);">` +
              `<div style="width:${pct}%;height:100%;background:var(--accent-emerald);"></div>` +
            `</div>` +
            `<div class="flex items-center justify-between text-[10.5px] font-mono-num" style="color:var(--text-muted);">` +
              `<span>${r.conversation_count} convs</span>` +
              `<span>${r.turn_count} turns</span>` +
            `</div>` +
          `</div>`
        );
      })
      .join("");

    listEl.querySelectorAll("[data-select-user]").forEach((el) => {
      el.addEventListener("click", () => switchActiveUser(el.getAttribute("data-select-user")));
    });
    return;
  }

  // Top Conversations
  const convs = summary.by_conversation || [];
  if (!convs.length) {
    listEl.innerHTML = `<div class="text-xs p-3 text-center" style="color:var(--text-muted);">No saved conversations yet.</div>`;
    return;
  }
  listEl.innerHTML = convs
    .slice(0, 20)
    .map(
      (c) =>
        `<div class="leaderboard-row space-y-1" data-load-conv="${escapeHtml(c.conversation_id)}">` +
          `<div class="flex items-center justify-between gap-1.5 text-xs">` +
            `<span class="font-semibold truncate">${escapeHtml(c.title || "Conversation")}</span>` +
            `<span class="font-mono-num shrink-0" style="color:var(--accent-cyan);">${fmtInt(c.total_tokens)}</span>` +
          `</div>` +
          `<div class="flex items-center justify-between text-[10.5px] font-mono-num" style="color:var(--text-muted);">` +
            `<span>${escapeHtml(c.agent_id)} • ${escapeHtml(c.user_id)}</span>` +
            `<span>${c.turn_count}t</span>` +
          `</div>` +
        `</div>`
    )
    .join("");

  listEl.querySelectorAll("[data-load-conv]").forEach((el) => {
    el.addEventListener("click", () => loadConversationById(el.getAttribute("data-load-conv")));
  });
}

function renderAgentsSidebar() {
  const container = document.getElementById("agents-list-container");
  if (!container) return;

  const catalog = state.agents.length
    ? state.agents
    : [
        {
          agent_id: "antigravity",
          display_name: "Antigravity (Agent & Tool Builder)",
          description: "Autonomous meta-builder synthesizing custom Python tools & compiling specialized DAG agents.",
          dag_topology: "Builder & Dynamic Tool Loop",
          tool_names: ["create_custom_tool", "build_custom_agent", "generate_video"],
          tool_count: 12,
          enable_subagents: true,
          is_builder: true,
        },
      ];

  document.getElementById("header-kpi-agents").textContent = String(catalog.length);
  document.getElementById("tab-count-agents").textContent = String(catalog.length);

  container.innerHTML = catalog
    .map((ag) => {
      const isBuilder = ag.agent_id === "antigravity" || ag.is_builder;
      const isActive = !state.previewPresetId && state.agentId === ag.agent_id;
      const preset = SCENARIO_PRESETS.find((p) => p.agentId === ag.agent_id);
      const icon = isBuilder ? "🚀" : preset?.icon || "🤖";
      const toolCount = Number(ag.tool_count ?? (ag.tool_names || []).length);

      return (
        `<button type="button" class="agent-item${isActive ? " active" : ""}" data-agent-card="${escapeHtml(ag.agent_id)}">` +
          `<div class="flex items-center justify-between gap-2 w-full">` +
            `<div class="flex items-center gap-1.5 min-w-0">` +
              `<span>${icon}</span>` +
              `<strong class="text-xs font-bold truncate">${escapeHtml(ag.display_name || ag.agent_id)}</strong>` +
            `</div>` +
            `<span class="badge-chip ${isBuilder ? "badge-cyan" : "badge-emerald"} font-mono-num shrink-0">${toolCount} tools</span>` +
          `</div>` +
          `<div class="text-[11.5px] line-clamp-2" style="color:var(--text-muted);">${escapeHtml(ag.description || "")}</div>` +
          `<div class="flex flex-wrap items-center gap-1 pt-0.5">` +
            `<span class="badge-chip font-mono-num">${escapeHtml((ag.dag_topology || "DAG").slice(0, 28))}</span>` +
            (ag.enable_subagents ? `<span class="badge-chip badge-teal">Subagents</span>` : "") +
          `</div>` +
        `</button>`
      );
    })
    .join("");

  container.querySelectorAll("[data-agent-card]").forEach((btn) => {
    btn.addEventListener("click", () => selectAgent(btn.getAttribute("data-agent-card")));
  });

  renderPresetsSidebar();
}

function renderPresetsSidebar() {
  const container = document.getElementById("presets-list-container");
  if (!container) return;

  const registeredIds = new Set(state.agents.map((a) => a.agent_id));
  const builtCount = SCENARIO_PRESETS.filter((p) => registeredIds.has(p.agentId)).length;
  const counterEl = document.getElementById("presets-built-counter");
  if (counterEl) counterEl.textContent = `${builtCount} / 10 Built`;

  container.innerHTML = SCENARIO_PRESETS.map((p) => {
    const isBuilt = registeredIds.has(p.agentId);
    return (
      `<article class="preset-card" id="preset-card-${escapeHtml(p.agentId)}">` +
        `<div class="flex items-start justify-between gap-2">` +
          `<div class="min-w-0">` +
            `<div class="flex items-center gap-1.5">` +
              `<span class="text-sm">${p.icon}</span>` +
              `<strong class="text-xs font-bold truncate">#${p.num} ${escapeHtml(p.name)}</strong>` +
            `</div>` +
            `<div class="text-[10.5px] font-mono-num mt-0.5" style="color:var(--accent-cyan);">${escapeHtml(p.topology)}</div>` +
          `</div>` +
          `<span class="badge-chip ${isBuilt ? "badge-emerald" : "badge-amber"} shrink-0">${isBuilt ? "✓ Ready" : "Unbuilt"}</span>` +
        `</div>` +
        `<p class="text-[11.5px] m-0 leading-snug" style="color:var(--text-secondary);">${escapeHtml(p.blurb)}</p>` +
        `<div class="flex flex-wrap gap-1">` +
          p.tools.map((t) => `<span class="badge-chip font-mono-num">${escapeHtml(t)}</span>`).join("") +
        `</div>` +
        `<div class="grid grid-cols-3 gap-1.5 pt-0.5">` +
          `<button type="button" class="btn-studio py-1 px-2 text-[11px]" data-preset-preview="${escapeHtml(p.agentId)}" title="Preview Canonical SVG DAG">` +
            `👁️ DAG` +
          `</button>` +
          `<button type="button" class="btn-studio py-1 px-2 text-[11px]" data-preset-build="${escapeHtml(p.agentId)}" title="Send Creation Prompt to Antigravity Builder Agent">` +
            `🛠️ Build` +
          `</button>` +
          `<button type="button" class="btn-studio ${isBuilt ? "btn-emerald" : "btn-primary"} py-1 px-2 text-[11px]" data-preset-run="${escapeHtml(p.agentId)}" title="${isBuilt ? `Switch to ${p.agentId} and run Starter Mission` : `Auto-Build ${p.agentId} via Antigravity then Run Mission`}">` +
            `▶️ Run` +
          `</button>` +
        `</div>` +
      `</article>`
    );
  }).join("");

  container.querySelectorAll("[data-preset-preview]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-preset-preview");
      state.previewPresetId = id;
      state.selectedNodeId = null;
      resetDagExecutionStatuses();
      buildActiveGraphModel();
      showToast(`Previewing canonical DAG blueprint for ${id}`);
    });
  });

  container.querySelectorAll("[data-preset-build]").forEach((btn) => {
    btn.addEventListener("click", () => launchPresetBuild(btn.getAttribute("data-preset-build")));
  });

  container.querySelectorAll("[data-preset-run]").forEach((btn) => {
    btn.addEventListener("click", () => launchPresetMission(btn.getAttribute("data-preset-run")));
  });
}

function renderConversationsSidebar() {
  const container = document.getElementById("conversations-list-container");
  if (!container) return;

  const filtered = state.filterAgentThreads
    ? state.conversations.filter((c) => c.agent_id === state.agentId)
    : state.conversations;

  document.getElementById("tab-count-threads").textContent = String(filtered.length);

  if (!filtered.length) {
    container.innerHTML =
      `<div class="p-3 rounded-lg text-xs text-center" style="background:var(--bg-inset);color:var(--text-muted);border:1px solid var(--border-subtle);">` +
        `No saved conversations for <code>${escapeHtml(state.userId)}</code>${state.filterAgentThreads ? ` on <code>${escapeHtml(state.agentId)}</code>` : ""} yet.` +
      `</div>`;
    return;
  }

  container.innerHTML = filtered
    .map((c) => {
      const isCurrent = state.conversationId === c.conversation_id;
      return (
        `<button type="button" class="agent-item${isCurrent ? " active" : ""}" data-conv-item="${escapeHtml(c.conversation_id)}">` +
          `<div class="flex items-center justify-between gap-2 w-full">` +
            `<strong class="text-xs font-semibold truncate">${escapeHtml(c.title || "Conversation")}</strong>` +
            `<span class="badge-chip badge-cyan font-mono-num shrink-0">${c.turn_count}t</span>` +
          `</div>` +
          `<div class="flex items-center justify-between w-full text-[11px] font-mono-num" style="color:var(--text-muted);">` +
            `<span class="truncate">${escapeHtml(c.agent_id)}</span>` +
            `<span>${fmtInt(c.total_tokens)} tok • ${relativeTime(c.updated_at)}</span>` +
          `</div>` +
        `</button>`
      );
    })
    .join("");

  container.querySelectorAll("[data-conv-item]").forEach((btn) => {
    btn.addEventListener("click", () => loadConversationById(btn.getAttribute("data-conv-item")));
  });
}

function updateComposerHeaderAndChips() {
  document.getElementById("composer-agent-label").textContent = state.agentId;
  document.getElementById("composer-user-label").textContent = state.userId;

  const convBadge = document.getElementById("composer-conv-badge");
  if (state.conversationId) {
    convBadge.className = "badge-chip badge-emerald font-mono-num";
    convBadge.textContent = `🔗 Continuing ${state.conversationId.slice(0, 8)}… (Turn #${state.activeTurnCount + 1})`;
  } else {
    convBadge.className = "badge-chip font-mono-num";
    convBadge.textContent = "🆕 New Thread (Turn #1)";
  }

  const chipsBar = document.getElementById("quick-chips-bar");
  if (!chipsBar) return;

  const chips = [];
  if (state.agentId === "antigravity") {
    chips.push(
      {
        label: "📋 List All Tools & Agents",
        prompt: "Call `list_registered_agents_and_tools` and give me a crisp summary of all built-in, scenario, and dynamic tools plus currently registered custom agents.",
      },
      {
        label: "🛠️ Build #1 Trailer Director",
        prompt: SCENARIO_PRESETS[0].creationPrompt,
      },
      {
        label: "🕹️ Build #2 Self-Healing Arcade",
        prompt: SCENARIO_PRESETS[1].creationPrompt,
      },
      {
        label: "🧪 Synthesize Tool + #7 MythBuster",
        prompt: SCENARIO_PRESETS[6].creationPrompt,
      }
    );
  } else {
    const matchingPreset = SCENARIO_PRESETS.find((p) => p.agentId === state.agentId);
    if (matchingPreset) {
      chips.push({
        label: `▶️ Starter Mission: ${matchingPreset.name}`,
        prompt: matchingPreset.missionPrompt,
      });
    }
    if (state.agentId === "corporate-dnd-master" && state.conversationId) {
      chips.push({
        label: "🎲 Turn 2: Cast Executive Escalation (+4)",
        prompt: "Turn 2: Load my current hero state via `manage_hero_state`, roll `roll_crypto_d20` (+4 modifier) to cast 'Executive Escalation Shield' against the Hydra, update HP/loot, and narrate what happens!",
      });
    } else if (state.conversationId) {
      chips.push({
        label: "🔄 Follow-up Turn (Prove Stateful Memory)",
        prompt: "Summarize what we just produced in Turn 1 and add one bonus insight or refinement while keeping our conversation context!",
      });
    }
  }

  chipsBar.innerHTML = chips
    .map(
      (c, idx) =>
        `<button type="button" class="btn-studio py-1 px-2.5 text-[11px] shrink-0" data-quick-chip="${idx}">` +
          `${escapeHtml(c.label)}` +
        `</button>`
    )
    .join("");

  chipsBar.querySelectorAll("[data-quick-chip]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.getAttribute("data-quick-chip"));
      const chosen = chips[idx];
      if (!chosen) return;
      const input = document.getElementById("chat-input");
      input.value = chosen.prompt;
      input.focus();
    });
  });
}

/* --------------------------------------------------------------------------
   7. Execution Feed, Tool Pills & Rich Multimodal Artifact Viewer
   -------------------------------------------------------------------------- */
function renderEmptyWelcomeState() {
  const feed = document.getElementById("execution-feed");
  if (!feed) return;
  const ag = state.agents.find((a) => a.agent_id === state.agentId);
  const preset = SCENARIO_PRESETS.find((p) => p.agentId === state.agentId);

  feed.innerHTML =
    `<div class="turn-block my-auto py-6">` +
      `<div class="agent-turn-card space-y-4">` +
        `<div class="flex flex-wrap items-center justify-between gap-2">` +
          `<div class="flex items-center gap-2.5">` +
            `<span class="text-xl">${state.agentId === "antigravity" ? "🚀" : preset?.icon || "🤖"}</span>` +
            `<div>` +
              `<h2 class="font-display text-base font-bold m-0">${escapeHtml(ag?.display_name || state.agentId)}</h2>` +
              `<div class="text-xs font-mono-num" style="color:var(--text-muted);">${escapeHtml(ag?.dag_topology || "Autonomous Agentic DAG")}</div>` +
            `</div>` +
          `</div>` +
          `<span class="badge-chip badge-cyan font-mono-num">POST /api/gateway/chat/stream</span>` +
        `</div>` +
        `<p class="text-xs m-0 leading-relaxed" style="color:var(--text-secondary);">` +
          escapeHtml(
            ag?.description ||
              "Select any of the 10 Fun DAG Presets in the left sidebar to watch Antigravity synthesize tools, compile custom agents, and animate every node, subagent, Veo 3.1 clip, and HTML5 canvas artifact live."
          ) +
        `</p>` +
        `<div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">` +
          `<button type="button" id="welcome-btn-open-presets" class="preset-card text-left cursor-pointer">` +
            `<strong class="text-xs">⚡ 10 Quick-Build DAGs</strong>` +
            `<span class="text-[11px]" style="color:var(--text-muted);">1-click Build via Antigravity or Run Starter Missions across all 10 topologies.</span>` +
          `</button>` +
          `<button type="button" id="welcome-btn-inspect-tools" class="preset-card text-left cursor-pointer">` +
            `<strong class="text-xs">🧰 28+ Harness &amp; Scenario Tools</strong>` +
            `<span class="text-[11px]" style="color:var(--text-muted);">Inspect built-in, scenario, and AST-validated dynamic Python tools.</span>` +
          `</button>` +
          `<button type="button" id="welcome-btn-run-sample" class="preset-card text-left cursor-pointer">` +
            `<strong class="text-xs">${preset ? `▶️ Run ${escapeHtml(preset.name)}` : "📋 Live Registry Check"}</strong>` +
            `<span class="text-[11px]" style="color:var(--text-muted);">${preset ? "Launch this custom agent's signature multimodal mission right now." : "Stream a live turn through Antigravity on the Single API Gateway."}</span>` +
          `</button>` +
        `</div>` +
      `</div>` +
    `</div>`;

  document.getElementById("welcome-btn-open-presets")?.addEventListener("click", () => {
    switchSidebarTab("presets");
  });
  document.getElementById("welcome-btn-inspect-tools")?.addEventListener("click", () => {
    openToolsRegistryModal();
  });
  document.getElementById("welcome-btn-run-sample")?.addEventListener("click", () => {
    if (preset) {
      sendChatTurn(preset.missionPrompt);
    } else {
      sendChatTurn(
        "Call `list_registered_agents_and_tools` and summarize the available tool categories and currently registered custom DAG agents."
      );
    }
  });
}

function createArtifactElement(art) {
  const url = art.url || `${API_BASE}/media/${art.rel_path || ""}`;
  const fname = art.filename || "artifact";
  const kind = art.kind || "file";
  const sizeStr = art.size_bytes ? fmtBytes(art.size_bytes) : "";

  const card = document.createElement("div");
  card.className = `artifact-card${kind === "html" || kind === "video" ? " artifact-wide" : ""}`;

  if (kind === "image") {
    card.innerHTML =
      `<div class="artifact-header">` +
        `<div class="flex items-center gap-1.5 min-w-0">` +
          `<span class="badge-chip badge-emerald">🎨 IMAGE</span>` +
          `<span class="font-mono-num truncate">${escapeHtml(fname)}</span>` +
        `</div>` +
        `<div class="flex items-center gap-1.5 shrink-0">` +
          `<span class="text-[10.5px] font-mono-num" style="color:var(--text-muted);">${escapeHtml(sizeStr)}</span>` +
          `<button type="button" class="btn-studio py-0.5 px-2 text-[11px]" data-zoom-img>⛶ Zoom</button>` +
          `<a href="${escapeHtml(url)}" download="${escapeHtml(fname)}" class="btn-studio py-0.5 px-2 text-[11px]">⬇</a>` +
        `</div>` +
      `</div>` +
      `<img src="${escapeHtml(url)}" alt="${escapeHtml(fname)}" loading="lazy" class="artifact-img" />`;

    const openZoom = () => openArtifactLightbox("IMAGE", fname, url, "image");
    card.querySelector(".artifact-img")?.addEventListener("click", openZoom);
    card.querySelector("[data-zoom-img]")?.addEventListener("click", openZoom);
    return card;
  }

  if (kind === "video") {
    card.innerHTML =
      `<div class="artifact-header">` +
        `<div class="flex items-center gap-1.5 min-w-0">` +
          `<span class="badge-chip badge-coral">🎬 VEO 3.1 MP4</span>` +
          `<span class="font-mono-num truncate">${escapeHtml(fname)}</span>` +
        `</div>` +
        `<div class="flex items-center gap-1.5 shrink-0">` +
          `<span class="text-[10.5px] font-mono-num" style="color:var(--text-muted);">${escapeHtml(sizeStr)}</span>` +
          `<a href="${escapeHtml(url)}" download="${escapeHtml(fname)}" class="btn-studio py-0.5 px-2 text-[11px]">⬇ Download MP4</a>` +
        `</div>` +
      `</div>` +
      `<video src="${escapeHtml(url)}" controls autoplay loop muted playsinline class="artifact-video"></video>`;
    return card;
  }

  if (kind === "html") {
    card.innerHTML =
      `<div class="artifact-header">` +
        `<div class="flex items-center gap-1.5 min-w-0">` +
          `<span class="badge-chip badge-cyan">🕹️ SANDBOX HTML5</span>` +
          `<span class="font-mono-num truncate">${escapeHtml(fname)}</span>` +
        `</div>` +
        `<div class="flex items-center gap-1.5 shrink-0">` +
          `<button type="button" class="btn-studio btn-emerald py-0.5 px-2 text-[11px]" data-focus-iframe>🕹️ Focus Controls</button>` +
          `<button type="button" class="btn-studio py-0.5 px-2 text-[11px]" data-reload-iframe>↻ Reload</button>` +
          `<button type="button" class="btn-studio py-0.5 px-2 text-[11px]" data-expand-iframe>⛶ Fullscreen</button>` +
          `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="btn-studio py-0.5 px-2 text-[11px]">↗ Tab</a>` +
        `</div>` +
      `</div>` +
      `<iframe src="${escapeHtml(url)}" sandbox="allow-scripts" title="${escapeHtml(fname)}" class="artifact-iframe"></iframe>`;

    const iframe = card.querySelector("iframe");
    card.querySelector("[data-focus-iframe]")?.addEventListener("click", () => {
      iframe?.focus();
      showToast(`Focused ${fname} — use keyboard/mouse inside the canvas!`);
    });
    card.querySelector("[data-reload-iframe]")?.addEventListener("click", () => {
      if (iframe) iframe.src = url + (url.includes("?") ? "&" : "?") + "t=" + Date.now();
    });
    card.querySelector("[data-expand-iframe]")?.addEventListener("click", () => {
      openArtifactLightbox("HTML5 SANDBOX", fname, url, "html");
    });
    return card;
  }

  if (kind === "calendar") {
    card.innerHTML =
      `<div class="artifact-header">` +
        `<div class="flex items-center gap-1.5 min-w-0">` +
          `<span class="badge-chip badge-teal">📅 ICALENDAR (.ICS)</span>` +
          `<span class="font-mono-num truncate">${escapeHtml(fname)}</span>` +
        `</div>` +
        `<div class="flex items-center gap-1.5 shrink-0">` +
          `<button type="button" class="btn-studio py-0.5 px-2 text-[11px]" data-preview-ics>Preview Events</button>` +
          `<a href="${escapeHtml(url)}" download="${escapeHtml(fname)}" class="btn-studio btn-primary py-0.5 px-2 text-[11px]">⬇ Add to Calendar</a>` +
        `</div>` +
      `</div>` +
      `<pre class="hidden m-0 p-3 text-[11px] font-mono-num overflow-x-auto" style="background:var(--bg-inset);color:var(--text-secondary);" data-ics-box></pre>`;

    card.querySelector("[data-preview-ics]")?.addEventListener("click", async () => {
      const box = card.querySelector("[data-ics-box]");
      if (!box) return;
      if (!box.classList.contains("hidden")) {
        box.classList.add("hidden");
        return;
      }
      box.classList.remove("hidden");
      box.textContent = "Loading .ics schedule…";
      try {
        const res = await fetch(url);
        box.textContent = await res.text();
      } catch (err) {
        box.textContent = `Could not preview .ics: ${err}`;
      }
    });
    return card;
  }

  card.innerHTML =
    `<div class="artifact-header">` +
      `<div class="flex items-center gap-1.5 min-w-0">` +
        `<span class="badge-chip">📎 FILE</span>` +
        `<span class="font-mono-num truncate">${escapeHtml(fname)}</span>` +
      `</div>` +
      `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="btn-studio py-0.5 px-2 text-[11px]">↗ Download (${escapeHtml(sizeStr)})</a>` +
    `</div>`;
  return card;
}

function wireCopyCodeButtons(rootEl) {
  rootEl.querySelectorAll(".copy-code-btn").forEach((btn) => {
    if (btn.dataset.wired) return;
    btn.dataset.wired = "1";
    btn.addEventListener("click", () => {
      const code = btn.closest("div")?.parentElement?.querySelector("pre code")?.textContent || "";
      navigator.clipboard?.writeText(code);
      btn.textContent = "Copied ✓";
      setTimeout(() => {
        btn.textContent = "Copy";
      }, 1400);
    });
  });
}

function createTurnDomScaffold({ userMessage, agentId, turnNumber }) {
  const feed = document.getElementById("execution-feed");
  // Clear empty welcome card if present
  if (feed.querySelector("#welcome-btn-open-presets")) {
    feed.innerHTML = "";
  }

  const block = document.createElement("div");
  block.className = "turn-block";

  block.innerHTML =
    `<div class="user-bubble">` +
      `<div class="flex items-center justify-between gap-3 text-[11px] mb-1 font-mono-num" style="color:var(--text-muted);">` +
        `<span>👤 ${escapeHtml(state.userId)}</span>` +
        `<span>Turn #${turnNumber}</span>` +
      `</div>` +
      `<div class="text-sm whitespace-pre-wrap">${escapeHtml(userMessage)}</div>` +
    `</div>` +
    `<div class="agent-turn-card">` +
      `<div class="flex flex-wrap items-center justify-between gap-2 pb-2" style="border-bottom:1px solid var(--border-subtle);">` +
        `<div class="flex items-center gap-2">` +
          `<span class="badge-chip badge-cyan font-mono-num">🤖 ${escapeHtml(agentId)}</span>` +
          `<span class="turn-status-badge badge-chip font-mono-num"><i class="spinner-ring mr-1"></i> Executing…</span>` +
        `</div>` +
        `<span class="turn-token-summary text-[11px] font-mono-num" style="color:var(--text-muted);">Streaming SSE…</span>` +
      `</div>` +
      `<details class="thought-details hidden">` +
        `<summary>` +
          `<span>💭 Agent Reasoning &amp; Subagent Thoughts (<span class="thought-char-count font-mono-num">0</span> chars)</span>` +
          `<span class="text-[11px]" style="color:var(--text-muted);">Toggle</span>` +
        `</summary>` +
        `<div class="thought-body"></div>` +
      `</details>` +
      `<div class="tool-pills-list space-y-1.5 hidden"></div>` +
      `<div class="dag-milestones-row flex flex-wrap gap-1.5 hidden"></div>` +
      `<div class="md-prose response-markdown"></div>` +
      `<div class="artifact-grid hidden"></div>` +
    `</div>`;

  feed.appendChild(block);
  feed.scrollTop = feed.scrollHeight;

  return {
    block,
    statusBadge: block.querySelector(".turn-status-badge"),
    tokenSummary: block.querySelector(".turn-token-summary"),
    thoughtDetails: block.querySelector(".thought-details"),
    thoughtCount: block.querySelector(".thought-char-count"),
    thoughtBody: block.querySelector(".thought-body"),
    toolPillsList: block.querySelector(".tool-pills-list"),
    dagMilestonesRow: block.querySelector(".dag-milestones-row"),
    responseMarkdown: block.querySelector(".response-markdown"),
    artifactGrid: block.querySelector(".artifact-grid"),
    toolMap: new Map(),
    seenArtifactUrls: new Set(),
    thoughtBuffer: "",
    markdownBuffer: "",
  };
}

function appendOrUpdateToolPill(scaffold, ev) {
  scaffold.toolPillsList.classList.remove("hidden");
  const callId = ev.call_id || `${ev.tool_name}_${scaffold.toolMap.size + 1}`;

  if (ev.type === "tool_call" && !scaffold.toolMap.has(callId)) {
    const meta = getToolMeta(ev.tool_name);
    const pill = document.createElement("div");
    pill.className = "tool-pill-card";
    pill.setAttribute("data-state", "running");

    const argPreview = summarizeToolArgs(ev.tool_name, ev.args || {});
    pill.innerHTML =
      `<div class="tool-pill-header">` +
        `<div class="flex items-center gap-2 min-w-0">` +
          `<span>${meta.icon}</span>` +
          `<code class="font-mono-num font-semibold text-xs">${escapeHtml(ev.tool_name)}</code>` +
          (ev.is_subagent ? `<span class="badge-chip badge-teal">subagent</span>` : "") +
          `<span class="text-xs truncate" style="color:var(--text-muted);">${escapeHtml(argPreview)}</span>` +
        `</div>` +
        `<div class="flex items-center gap-1.5 shrink-0">` +
          `<span class="pill-action-slot"></span>` +
          `<span class="pill-state-badge badge-chip badge-cyan font-mono-num"><i class="spinner-ring mr-1"></i>run</span>` +
        `</div>` +
      `</div>` +
      `<div class="tool-pill-payload space-y-2">` +
        `<div><div class="text-[10.5px] uppercase mb-0.5" style="color:var(--text-muted);">Arguments</div>` +
        `<pre class="m-0 whitespace-pre-wrap">${escapeHtml(JSON.stringify(ev.args || {}, null, 2))}</pre></div>` +
        `<div class="pill-result-block hidden"><div class="text-[10.5px] uppercase mb-0.5" style="color:var(--text-muted);">Result</div>` +
        `<pre class="pill-result-json m-0 whitespace-pre-wrap"></pre></div>` +
      `</div>`;

    pill.querySelector(".tool-pill-header")?.addEventListener("click", (clickEv) => {
      if (clickEv.target.closest("button")) return;
      pill.classList.toggle("expanded");
    });

    scaffold.toolPillsList.appendChild(pill);
    scaffold.toolMap.set(callId, { pill, args: ev.args || {}, toolName: ev.tool_name });
    return;
  }

  if (ev.type === "tool_result") {
    let entry = scaffold.toolMap.get(callId);
    if (!entry) {
      appendOrUpdateToolPill(scaffold, {
        type: "tool_call",
        call_id: callId,
        tool_name: ev.tool_name,
        args: {},
        is_subagent: ev.is_subagent,
      });
      entry = scaffold.toolMap.get(callId);
    }
    if (!entry) return;

    const { pill } = entry;
    pill.setAttribute("data-state", ev.is_error ? "error" : "done");
    const badge = pill.querySelector(".pill-state-badge");
    if (badge) {
      badge.className = `pill-state-badge badge-chip ${ev.is_error ? "badge-coral" : "badge-emerald"} font-mono-num`;
      badge.textContent = ev.is_error ? "ERR" : "OK ✓";
    }
    const resBlock = pill.querySelector(".pill-result-block");
    const resJson = pill.querySelector(".pill-result-json");
    if (resBlock && resJson) {
      resBlock.classList.remove("hidden");
      resJson.textContent = JSON.stringify(ev.result ?? {}, null, 2);
    }

    // Special UX: when `build_custom_agent` creates a new agent, offer a 1-click Switch button right on the pill!
    if (!ev.is_error && ev.tool_name === "build_custom_agent") {
      const createdId = ev.result?.agent_id || entry.args?.agent_id;
      if (createdId) {
        const slot = pill.querySelector(".pill-action-slot");
        if (slot) {
          slot.innerHTML = `<button type="button" class="btn-studio btn-emerald py-0.5 px-2 text-[11px]">🚀 Use ${escapeHtml(createdId)}</button>`;
          slot.querySelector("button")?.addEventListener("click", async () => {
            await fetchAgentsCatalog();
            selectAgent(createdId, true);
          });
        }
        fetchAgentsCatalog();
        fetchToolsCatalog();
        showToast(`Custom Agent "${createdId}" registered on Gateway!`, createdId);
      }
    } else if (!ev.is_error && ev.tool_name === "create_custom_tool") {
      fetchToolsCatalog();
      const tName = ev.result?.tool_name || entry.args?.tool_name || "tool";
      showToast(`Dynamic Python tool "${tName}" AST-validated & hot-registered!`);
    }
  }
}

function summarizeToolArgs(toolName, args) {
  if (!args || typeof args !== "object") return "";
  if (args.query) return `"${String(args.query).slice(0, 48)}"`;
  if (args.agent_id) return `agent_id="${args.agent_id}"`;
  if (args.tool_name) return `tool="${args.tool_name}"`;
  if (args.agent_name || args.subagent_name || args.name) {
    return `-> ${args.agent_name || args.subagent_name || args.name}`;
  }
  if (args.TargetFile || args.file_path || args.path) {
    return String(args.TargetFile || args.file_path || args.path).split("/").pop();
  }
  if (args.CommandLine || args.command) {
    return String(args.CommandLine || args.command).slice(0, 46);
  }
  if (args.prompt) return `"${String(args.prompt).slice(0, 44)}…"`;
  if (args.claim) return `"${String(args.claim).slice(0, 44)}…"`;
  const keys = Object.keys(args);
  if (!keys.length) return "";
  return `${keys[0]}=${String(args[keys[0]]).slice(0, 32)}`;
}

/* --------------------------------------------------------------------------
   8. Real-Time SSE Streaming Execution (`POST /api/gateway/chat/stream`)
   -------------------------------------------------------------------------- */
export async function sendChatTurn(rawMessage, options = {}) {
  const message = String(rawMessage || "").trim();
  if (!message || state.isStreaming) return null;

  const targetAgentId = options.overrideAgentId || state.agentId;
  if (targetAgentId !== state.agentId) {
    selectAgent(targetAgentId, Boolean(options.forceNewThread));
  } else if (options.forceNewThread) {
    startNewConversationThread(false);
  }
  state.previewPresetId = null;
  buildActiveGraphModel();

  const estTurn = state.conversationId ? state.activeTurnCount + 1 : 1;
  const scaffold = createTurnDomScaffold({
    userMessage: message,
    agentId: state.agentId,
    turnNumber: estTurn,
  });

  state.isStreaming = true;
  state.lastTurnEvents = [];
  state.abortController = new AbortController();
  state.streamStartMs = performance.now();

  document.getElementById("btn-send-message").disabled = true;
  document.getElementById("btn-stop-stream").classList.remove("hidden");
  document.getElementById("gateway-status-dot").classList.add("streaming");

  clearInterval(state.latencyTimerId);
  state.latencyTimerId = setInterval(() => {
    const elapsed = performance.now() - state.streamStartMs;
    document.getElementById("hud-req-latency").textContent = fmtLatency(elapsed);
  }, 120);

  let rafMarkdownPending = false;
  const flushMarkdown = () => {
    rafMarkdownPending = false;
    scaffold.responseMarkdown.innerHTML = renderMarkdown(scaffold.markdownBuffer);
    wireCopyCodeButtons(scaffold.responseMarkdown);
  };

  let completedPayload = null;

  try {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: state.userId,
        conversation_id: state.conversationId,
        agent_id: state.agentId,
        message,
      }),
      signal: state.abortController.signal,
    });

    if (!res.ok) {
      let errDetail = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errJson.error || errDetail;
      } catch {
        errDetail = await res.text();
      }
      throw new Error(errDetail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let sseBuffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      sseBuffer += decoder.decode(value, { stream: true });

      let boundaryIdx;
      while ((boundaryIdx = sseBuffer.indexOf("\n\n")) !== -1) {
        const rawFrame = sseBuffer.slice(0, boundaryIdx);
        sseBuffer = sseBuffer.slice(boundaryIdx + 2);

        const dataLines = [];
        for (const line of rawFrame.split("\n")) {
          if (line.startsWith(":")) continue; // keepalive comment
          if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }
        if (!dataLines.length) continue;

        let ev;
        try {
          ev = JSON.parse(dataLines.join("\n"));
        } catch {
          continue;
        }

        state.lastTurnEvents.push(ev);
        applyEventToDag(ev);

        if (ev.type === "turn_start") {
          state.conversationId = ev.conversation_id;
          state.antigravityConversationId = ev.antigravity_conversation_id;
          updateComposerHeaderAndChips();
        } else if (ev.type === "thought") {
          scaffold.thoughtDetails.classList.remove("hidden");
          const prefix = ev.is_subagent ? "\n[Subagent] " : "";
          scaffold.thoughtBuffer += (scaffold.thoughtBuffer ? "" : prefix) + (ev.text || "");
          scaffold.thoughtBody.textContent = scaffold.thoughtBuffer;
          scaffold.thoughtCount.textContent = fmtInt(scaffold.thoughtBuffer.length);
        } else if (ev.type === "tool_call" || ev.type === "tool_result") {
          appendOrUpdateToolPill(scaffold, ev);
        } else if (ev.type === "dag_step") {
          scaffold.dagMilestonesRow.classList.remove("hidden");
          const st = String(ev.status || "completed").toLowerCase();
          const badgeCls =
            st === "pruned"
              ? "badge-coral"
              : st === "retry"
              ? "badge-amber"
              : st === "running"
              ? "badge-cyan"
              : "badge-emerald";
          const chip = document.createElement("span");
          chip.className = `badge-chip ${badgeCls} font-mono-num`;
          chip.textContent = `${ev.node_label || ev.node_id}: ${st}`;
          scaffold.dagMilestonesRow.appendChild(chip);
        } else if (ev.type === "text_delta") {
          if (!ev.is_subagent) {
            scaffold.markdownBuffer += ev.text || "";
            if (!rafMarkdownPending) {
              rafMarkdownPending = true;
              requestAnimationFrame(flushMarkdown);
            }
          }
        } else if (ev.type === "media") {
          const mUrl = ev.url || ev.path;
          if (mUrl && !scaffold.seenArtifactUrls.has(mUrl)) {
            scaffold.seenArtifactUrls.add(mUrl);
            scaffold.artifactGrid.classList.remove("hidden");
            scaffold.artifactGrid.appendChild(createArtifactElement(ev));
          }
        } else if (ev.type === "usage") {
          clearInterval(state.latencyTimerId);
          state.activeTurnCount = Number(ev.turn_number || state.activeTurnCount + 1);
          updateRequestHud(ev.request_tokens, ev.latency_ms);
          updateConversationHud(ev.conversation_tokens, state.activeTurnCount);
          if (ev.user_tokens) {
            updateUserMeter({
              ...(state.userUsage || {}),
              tokens: ev.user_tokens,
              conversation_count: Math.max(1, Number(state.userUsage?.conversation_count || 0)),
              turn_count: Number(state.userUsage?.turn_count || 0) + 1,
            });
          }
        } else if (ev.type === "turn_complete") {
          completedPayload = ev;
          clearInterval(state.latencyTimerId);
          state.conversationId = ev.conversation_id;
          state.antigravityConversationId = ev.antigravity_conversation_id;
          state.activeTurnCount = Number(ev.turn_number || 1);

          if (ev.response_text) {
            scaffold.markdownBuffer = ev.response_text;
          }
          flushMarkdown();

          (ev.media || []).forEach((art) => {
            const mUrl = art.url || art.path;
            if (mUrl && !scaffold.seenArtifactUrls.has(mUrl)) {
              scaffold.seenArtifactUrls.add(mUrl);
              scaffold.artifactGrid.classList.remove("hidden");
              scaffold.artifactGrid.appendChild(createArtifactElement(art));
            }
          });

          scaffold.statusBadge.className = "turn-status-badge badge-chip badge-emerald font-mono-num";
          scaffold.statusBadge.textContent = `✓ Done in ${fmtLatency(ev.latency_ms)}`;
          scaffold.tokenSummary.textContent = `${fmtInt(ev.request_tokens?.total_tokens)} req tok • ${fmtInt(ev.conversation_tokens?.total_tokens)} conv tok`;

          state.conversationTurns.push({
            turn_number: ev.turn_number,
            total_tokens: ev.request_tokens?.total_tokens || 0,
            latency_ms: ev.latency_ms,
          });
          updateRequestHud(ev.request_tokens, ev.latency_ms);
          updateConversationHud(ev.conversation_tokens, state.activeTurnCount);
          updateComposerHeaderAndChips();
        } else if (ev.type === "error") {
          throw new Error(ev.error || "Agent turn failed");
        }
      }
    }
  } catch (err) {
    clearInterval(state.latencyTimerId);
    const aborted = err?.name === "AbortError";
    scaffold.statusBadge.className = `turn-status-badge badge-chip ${aborted ? "badge-amber" : "badge-coral"} font-mono-num`;
    scaffold.statusBadge.textContent = aborted ? "■ Stopped" : "⚠ Error";
    if (!aborted) {
      const errDiv = document.createElement("div");
      errDiv.className = "p-2.5 rounded-lg text-xs font-mono-num";
      errDiv.style.cssText = "background:var(--accent-coral-soft);color:var(--accent-coral);border:1px solid hsla(8,82%,60%,0.4);";
      errDiv.textContent = `Gateway Error: ${err?.message || err}`;
      scaffold.responseMarkdown.appendChild(errDiv);
      applyEventToDag({ type: "error", error: String(err) });
    }
  } finally {
    clearInterval(state.latencyTimerId);
    state.isStreaming = false;
    state.abortController = null;
    document.getElementById("btn-send-message").disabled = false;
    document.getElementById("btn-stop-stream").classList.add("hidden");
    document.getElementById("gateway-status-dot").classList.remove("streaming");

    const feed = document.getElementById("execution-feed");
    if (feed) feed.scrollTop = feed.scrollHeight;

    // Refresh persistent ledgers in background
    Promise.all([
      fetchAgentsCatalog(),
      fetchConversations(),
      fetchUserUsage(),
      fetchGlobalSummary(),
    ]).catch(() => {});
  }

  return completedPayload;
}

/* --------------------------------------------------------------------------
   9. Quick-Build Presets & Conversation History Restoration
   -------------------------------------------------------------------------- */
async function launchPresetBuild(presetAgentId) {
  const preset = SCENARIO_PRESETS.find((p) => p.agentId === presetAgentId);
  if (!preset || state.isStreaming) return;
  selectAgent("antigravity", true);
  showToast(`Building "${preset.agentId}" via Antigravity Builder Agent…`);
  await sendChatTurn(preset.creationPrompt, {
    overrideAgentId: "antigravity",
    forceNewThread: true,
  });
}

async function launchPresetMission(presetAgentId) {
  const preset = SCENARIO_PRESETS.find((p) => p.agentId === presetAgentId);
  if (!preset || state.isStreaming) return;

  const exists = state.agents.some((a) => a.agent_id === preset.agentId);
  if (!exists) {
    // Smart Auto-Pipeline: Step 1 Build via Antigravity -> Step 2 Switch & Run Starter Mission!
    showToast(`Step 1/2: Building ${preset.agentId} via Antigravity first…`);
    selectAgent("antigravity", true);
    const buildRes = await sendChatTurn(preset.creationPrompt, {
      overrideAgentId: "antigravity",
      forceNewThread: true,
    });
    if (!buildRes) return;
    await fetchAgentsCatalog();
    if (!state.agents.some((a) => a.agent_id === preset.agentId)) {
      showToast(`Check builder output above — ${preset.agentId} was not yet registered.`);
      return;
    }
    showToast(`Step 2/2: Switching to ${preset.agentId} & launching Starter Mission!`);
  }

  selectAgent(preset.agentId, true);
  await sendChatTurn(preset.missionPrompt, {
    overrideAgentId: preset.agentId,
    forceNewThread: true,
  });
}

export async function loadConversationById(conversationId) {
  if (!conversationId || state.isStreaming) return;
  try {
    const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(conversationId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const conv = data.conversation;
    const turns = data.turns || [];
    if (!conv) return;

    if (conv.user_id && conv.user_id !== state.userId) {
      state.userId = conv.user_id;
      document.getElementById("user-id-input").value = conv.user_id;
    }

    state.agentId = conv.agent_id || "antigravity";
    state.previewPresetId = null;
    state.conversationId = conv.conversation_id;
    state.antigravityConversationId = conv.antigravity_conversation_id;
    state.activeTurnCount = Number(conv.turn_count || turns.length || 0);
    state.conversationTurns = turns;

    buildActiveGraphModel();
    resetDagExecutionStatuses();

    const feed = document.getElementById("execution-feed");
    feed.innerHTML = "";

    turns.forEach((t) => {
      const scaffold = createTurnDomScaffold({
        userMessage: t.message_preview || "(User prompt)",
        agentId: t.agent_id || state.agentId,
        turnNumber: t.turn_number || 1,
      });
      scaffold.statusBadge.className = "turn-status-badge badge-chip badge-emerald font-mono-num";
      scaffold.statusBadge.textContent = `✓ Saved Turn • ${fmtLatency(t.latency_ms)}`;
      scaffold.tokenSummary.textContent = `${fmtInt(t.total_tokens)} turn tok`;

      (t.tool_calls || []).forEach((tc, idx) => {
        const cid = tc.call_id || `hist_${t.turn_number}_${idx}`;
        appendOrUpdateToolPill(scaffold, {
          type: "tool_call",
          call_id: cid,
          tool_name: tc.tool_name,
          args: tc.args || {},
        });
        appendOrUpdateToolPill(scaffold, {
          type: "tool_result",
          call_id: cid,
          tool_name: tc.tool_name,
          result: tc.result ?? {},
          is_error: Boolean(tc.is_error),
        });
        applyEventToDag({ type: "tool_call", tool_name: tc.tool_name, args: tc.args || {} });
        applyEventToDag({ type: "tool_result", tool_name: tc.tool_name, is_error: Boolean(tc.is_error) });
      });

      scaffold.markdownBuffer = t.response_preview || "";
      scaffold.responseMarkdown.innerHTML = renderMarkdown(scaffold.markdownBuffer);
      wireCopyCodeButtons(scaffold.responseMarkdown);

      (t.media || []).forEach((art) => {
        const mUrl = art.url || art.path;
        if (mUrl && !scaffold.seenArtifactUrls.has(mUrl)) {
          scaffold.seenArtifactUrls.add(mUrl);
          scaffold.artifactGrid.classList.remove("hidden");
          scaffold.artifactGrid.appendChild(createArtifactElement(art));
        }
      });
    });

    const lastTurn = turns[turns.length - 1];
    if (lastTurn) {
      updateRequestHud(lastTurn.tokens || lastTurn, lastTurn.latency_ms);
      applyEventToDag({
        type: "turn_complete",
        turn_number: conv.turn_count,
        latency_ms: lastTurn.latency_ms,
        tool_calls: lastTurn.tool_calls || [],
        media: lastTurn.media || [],
      });
    }
    updateConversationHud(conv.tokens || conv, state.activeTurnCount);
    renderAgentsSidebar();
    renderConversationsSidebar();
    updateComposerHeaderAndChips();
    showToast(`Restored persistent conversation (${state.activeTurnCount} turn(s))`);
  } catch (err) {
    showToast(`Failed to load conversation: ${err?.message || err}`);
  }
}

function selectAgent(agentId, startFresh = true) {
  if (!agentId) return;
  state.agentId = agentId;
  state.previewPresetId = null;
  state.selectedNodeId = null;
  document.getElementById("dag-node-inspector")?.classList.add("hidden");

  if (startFresh) {
    startNewConversationThread(false);
  }
  resetDagExecutionStatuses();
  buildActiveGraphModel();
  renderAgentsSidebar();
  renderConversationsSidebar();
  updateComposerHeaderAndChips();
  if (!state.conversationId) {
    renderEmptyWelcomeState();
  }
}

function startNewConversationThread(renderWelcome = true) {
  state.conversationId = null;
  state.antigravityConversationId = null;
  state.activeTurnCount = 0;
  state.conversationTurns = [];
  updateConversationHud({}, 0);
  resetDagExecutionStatuses();
  renderConversationsSidebar();
  updateComposerHeaderAndChips();
  if (renderWelcome) {
    renderEmptyWelcomeState();
  }
}

async function switchActiveUser(newUserId) {
  const cleaned = String(newUserId || "").trim() || "cbribiescas";
  state.userId = cleaned;
  safeStorageSet("ag_studio_user_id", cleaned);

  const inputEl = document.getElementById("user-id-input");
  const selectEl = document.getElementById("user-id-select");
  if (inputEl) inputEl.value = cleaned;
  if (selectEl) {
    const hasOpt = Array.from(selectEl.options).some((o) => o.value === cleaned);
    if (!hasOpt) {
      const opt = document.createElement("option");
      opt.value = cleaned;
      opt.textContent = cleaned;
      selectEl.appendChild(opt);
    }
    selectEl.value = cleaned;
  }

  startNewConversationThread(true);
  await Promise.all([fetchUserUsage(), fetchConversations()]);
}

/* --------------------------------------------------------------------------
   10. Gateway REST API Fetchers & Modals
   -------------------------------------------------------------------------- */
async function fetchGatewayHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    document.getElementById("header-model-name").textContent = data.model || "gemini-3.7-flash";
    document.getElementById("gateway-status-dot").classList.remove("offline");
    document.getElementById("gateway-status-text").textContent = "GATEWAY ONLINE";
  } catch {
    document.getElementById("gateway-status-dot").classList.add("offline");
    document.getElementById("gateway-status-text").textContent = "GATEWAY OFFLINE";
  }
}

async function fetchAgentsCatalog() {
  const res = await fetch(`${API_BASE}/agents`);
  if (!res.ok) return;
  const data = await res.json();
  state.agents = Array.isArray(data.agents) ? data.agents : [];
  renderAgentsSidebar();
  buildActiveGraphModel();
}

async function fetchToolsCatalog() {
  const res = await fetch(`${API_BASE}/tools`);
  if (!res.ok) return;
  const data = await res.json();
  state.toolsCatalog = data;
  const totalTools =
    data.counts?.total_tools ||
    (data.all_tool_names || []).length ||
    (data.builtin_tools || []).length;
  document.getElementById("header-kpi-tools").textContent = String(totalTools);
}

async function fetchConversations() {
  const res = await fetch(
    `${API_BASE}/conversations?user_id=${encodeURIComponent(state.userId)}&limit=100`
  );
  if (!res.ok) return;
  const data = await res.json();
  state.conversations = Array.isArray(data.conversations) ? data.conversations : [];
  renderConversationsSidebar();
}

async function fetchUserUsage() {
  const res = await fetch(
    `${API_BASE}/usage/users/${encodeURIComponent(state.userId)}`
  );
  if (!res.ok) return;
  state.userUsage = await res.json();
  updateUserMeter(state.userUsage);
}

async function fetchGlobalSummary() {
  const res = await fetch(`${API_BASE}/usage/summary`);
  if (!res.ok) return;
  state.globalSummary = await res.json();
  renderGlobalLeaderboard();

  // Populate discovered users into user-id-select dropdown
  const selectEl = document.getElementById("user-id-select");
  if (selectEl && Array.isArray(state.globalSummary.by_user)) {
    const existing = new Set(Array.from(selectEl.options).map((o) => o.value));
    state.globalSummary.by_user.forEach((u) => {
      if (u.user_id && !existing.has(u.user_id)) {
        const opt = document.createElement("option");
        opt.value = u.user_id;
        opt.textContent = u.user_id;
        selectEl.appendChild(opt);
      }
    });
  }
}

async function refreshAllStudioData() {
  await Promise.allSettled([
    fetchGatewayHealth(),
    fetchAgentsCatalog(),
    fetchToolsCatalog(),
    fetchUserUsage(),
    fetchConversations(),
    fetchGlobalSummary(),
  ]);
}

async function openToolsRegistryModal() {
  const modal = document.getElementById("tools-registry-modal");
  const body = document.getElementById("tools-modal-body");
  if (!modal || !body) return;
  modal.classList.remove("hidden");
  body.innerHTML = `<div class="p-4 text-center"><span class="spinner-ring mr-2"></span>Loading live catalog…</div>`;

  await Promise.allSettled([fetchToolsCatalog(), fetchAgentsCatalog()]);
  const cat = state.toolsCatalog || {};

  const renderGroup = (title, badgeCls, items) => {
    if (!items || !items.length) {
      return `<div><h3 class="font-display text-sm font-bold mb-1">${escapeHtml(title)} (0)</h3><p class="text-xs" style="color:var(--text-muted);">None registered yet.</p></div>`;
    }
    return (
      `<div>` +
        `<h3 class="font-display text-sm font-bold mb-2">${escapeHtml(title)} (${items.length})</h3>` +
        `<div class="grid grid-cols-1 md:grid-cols-2 gap-2">` +
          items
            .map((item) => {
              const name = typeof item === "string" ? item : item.name;
              const desc = typeof item === "string" ? "" : item.description || "";
              const meta = getToolMeta(name);
              return (
                `<div class="p-2.5 rounded-lg" style="background:var(--bg-elevated);border:1px solid var(--border-subtle);">` +
                  `<div class="flex items-center justify-between gap-2">` +
                    `<code class="font-mono-num font-semibold text-xs">${meta.icon} ${escapeHtml(name)}</code>` +
                    `<span class="badge-chip ${badgeCls}">${escapeHtml(item.source || "tool")}</span>` +
                  `</div>` +
                  (desc ? `<p class="text-[11px] m-0 mt-1" style="color:var(--text-secondary);">${escapeHtml(desc)}</p>` : "") +
                `</div>`
              );
            })
            .join("") +
        `</div>` +
      `</div>`
    );
  };

  body.innerHTML =
    renderGroup("1. Dynamic Synthesized Tools (app/dynamic_tools/)", "badge-amber", cat.dynamic_tools || []) +
    renderGroup("2. Scenario DAG Tools (app/scenario_tools/)", "badge-emerald", cat.scenario_tools || []) +
    renderGroup("3. Core & Agent Builder Tools", "badge-cyan", cat.core_custom_tools || []) +
    renderGroup("4. Antigravity SDK Built-in Harness Tools", "badge-teal", cat.builtin_tools || []);
}

function openArtifactLightbox(kindLabel, title, url, mode) {
  const modal = document.getElementById("artifact-lightbox-modal");
  const content = document.getElementById("lightbox-content");
  if (!modal || !content) return;

  document.getElementById("lightbox-kind-badge").textContent = kindLabel;
  document.getElementById("lightbox-title").textContent = title;
  document.getElementById("lightbox-open-raw").href = url;

  if (mode === "html") {
    content.innerHTML = `<iframe src="${escapeHtml(url)}" sandbox="allow-scripts" class="w-full h-full rounded-lg border-0" style="background:#0b0e14;"></iframe>`;
  } else {
    content.innerHTML = `<img src="${escapeHtml(url)}" alt="${escapeHtml(title)}" class="max-w-full max-h-full object-contain rounded-lg" />`;
  }
  modal.classList.remove("hidden");
}

let toastTimer = null;
function showToast(msg, switchAgentId = null) {
  const el = document.getElementById("studio-toast");
  if (!el) return;
  clearTimeout(toastTimer);
  el.innerHTML =
    `<span class="text-xs flex-1">${escapeHtml(msg)}</span>` +
    (switchAgentId
      ? `<button type="button" class="btn-studio btn-emerald py-1 px-2 text-[11px]" id="toast-switch-btn">Switch →</button>`
      : "");
  el.classList.remove("hidden");
  if (switchAgentId) {
    document.getElementById("toast-switch-btn")?.addEventListener("click", () => {
      el.classList.add("hidden");
      selectAgent(switchAgentId, true);
    });
  }
  toastTimer = setTimeout(() => el.classList.add("hidden"), 5200);
}

function switchSidebarTab(tabName) {
  state.sidebarTab = tabName;
  ["agents", "presets", "threads"].forEach((t) => {
    const btn = document.querySelector(`[data-sidebar-tab="${t}"]`);
    const panel = document.getElementById(`sidebar-panel-${t}`);
    const isMatch = t === tabName;
    if (btn) {
      btn.classList.toggle("active", isMatch);
      btn.setAttribute("aria-selected", String(isMatch));
    }
    if (panel) panel.classList.toggle("hidden", !isMatch);
  });
}

async function replayLastTurnDagAnimation() {
  if (state.isStreaming) return;
  const events = state.lastTurnEvents.length
    ? state.lastTurnEvents
    : [
        { type: "turn_start", turn_number: 1 },
        ...state.currentGraph.nodes.slice(1, -1).map((n) => ({
          type: "dag_step",
          node_id: n.id,
          node_label: n.label,
          status: n.type === "prunable" ? "pruned" : "completed",
          summary: "Simulated walkthrough step",
        })),
        { type: "turn_complete", turn_number: 1, latency_ms: 1420, tool_calls: [], media: [] },
      ];

  resetDagExecutionStatuses();
  for (const ev of events) {
    if (ev.type === "text_delta" || ev.type === "usage" || ev.type === "media") continue;
    applyEventToDag(ev);
    await new Promise((r) => setTimeout(r, 340));
  }
}

/* --------------------------------------------------------------------------
   11. Studio Initialization & Interactive Event Wiring
   -------------------------------------------------------------------------- */
function applyTheme(theme) {
  state.theme = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", state.theme);
  safeStorageSet("ag_studio_theme", state.theme);
  const icon = document.getElementById("theme-toggle-icon");
  if (icon) icon.textContent = state.theme === "dark" ? "☀" : "☾";
}

function initDagViewportInteractions() {
  const viewport = document.getElementById("dag-viewport");
  if (!viewport) return;

  let dragging = false;
  let startX = 0;
  let startY = 0;

  viewport.addEventListener("mousedown", (e) => {
    if (e.target.closest(".dag-node-group") || e.target.closest(".dag-node-inspector")) return;
    dragging = true;
    startX = e.clientX - state.dagPanX;
    startY = e.clientY - state.dagPanY;
  });

  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    state.dagPanX = e.clientX - startX;
    state.dagPanY = e.clientY - startY;
    applyDagTransform();
  });

  window.addEventListener("mouseup", () => {
    dragging = false;
  });

  document.getElementById("btn-dag-zoom-in")?.addEventListener("click", () => {
    state.dagZoom = Math.min(2.0, Number((state.dagZoom + 0.15).toFixed(2)));
    applyDagTransform();
  });
  document.getElementById("btn-dag-zoom-out")?.addEventListener("click", () => {
    state.dagZoom = Math.max(0.55, Number((state.dagZoom - 0.15).toFixed(2)));
    applyDagTransform();
  });
  document.getElementById("btn-dag-reset")?.addEventListener("click", () => {
    state.dagZoom = 1;
    state.dagPanX = 0;
    state.dagPanY = 0;
    applyDagTransform();
  });
  document.getElementById("btn-close-node-inspector")?.addEventListener("click", () => {
    state.selectedNodeId = null;
    document.getElementById("dag-node-inspector")?.classList.add("hidden");
    renderDagSvg();
  });
}

async function initStudio() {
  applyTheme(state.theme);

  // Sync User Identity controls
  const userInput = document.getElementById("user-id-input");
  const userSelect = document.getElementById("user-id-select");
  if (userInput) userInput.value = state.userId;
  if (userSelect) userSelect.value = state.userId;

  userSelect?.addEventListener("change", (e) => switchActiveUser(e.target.value));
  userInput?.addEventListener("change", (e) => switchActiveUser(e.target.value));
  userInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      switchActiveUser(userInput.value);
    }
  });

  // Sidebar Tabs
  document.querySelectorAll("[data-sidebar-tab]").forEach((btn) => {
    btn.addEventListener("click", () => switchSidebarTab(btn.getAttribute("data-sidebar-tab")));
  });
  document.getElementById("btn-jump-to-presets")?.addEventListener("click", () => {
    switchSidebarTab("presets");
  });

  // Layout Focus Tabs
  document.querySelectorAll("[data-focus-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-focus-mode");
      document.getElementById("studio-workspace")?.setAttribute("data-focus", mode);
      document.querySelectorAll("[data-focus-mode]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
    });
  });

  // DAG Mode Switcher (Canonical Blueprint vs Raw Registry Spec)
  document.querySelectorAll("[data-dag-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.dagMode = btn.getAttribute("data-dag-mode");
      document.querySelectorAll("[data-dag-mode]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      buildActiveGraphModel();
    });
  });

  document.getElementById("btn-dag-replay")?.addEventListener("click", replayLastTurnDagAnimation);

  // Leaderboard Tabs
  document.querySelectorAll("[data-lb-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.leaderboardTab = btn.getAttribute("data-lb-tab");
      document.querySelectorAll("[data-lb-tab]").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      renderGlobalLeaderboard();
    });
  });

  // Conversation Controls
  document.getElementById("btn-new-conversation")?.addEventListener("click", () =>
    startNewConversationThread(true)
  );
  document.getElementById("btn-composer-new-thread")?.addEventListener("click", () =>
    startNewConversationThread(true)
  );
  document.getElementById("chk-filter-agent-threads")?.addEventListener("change", (e) => {
    state.filterAgentThreads = Boolean(e.target.checked);
    renderConversationsSidebar();
  });

  document.getElementById("btn-copy-conv-ids")?.addEventListener("click", () => {
    if (!state.conversationId) {
      showToast("No active conversation ID yet — send a turn first!");
      return;
    }
    const text = `conversation_id=${state.conversationId}\nantigravity_conversation_id=${state.antigravityConversationId || ""}`;
    navigator.clipboard?.writeText(text);
    showToast("Copied Gateway & Antigravity SQLite trajectory IDs!");
  });

  // Header & Modals
  document.getElementById("btn-theme-toggle")?.addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark");
  });
  document.getElementById("btn-refresh-all")?.addEventListener("click", async () => {
    await refreshAllStudioData();
    showToast("Synchronized agents, tools, threads & token ledger!");
  });
  document.getElementById("btn-open-tools-modal")?.addEventListener("click", openToolsRegistryModal);
  document.getElementById("btn-close-tools-modal")?.addEventListener("click", () => {
    document.getElementById("tools-registry-modal")?.classList.add("hidden");
  });
  document.getElementById("tools-registry-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "tools-registry-modal") e.target.classList.add("hidden");
  });
  document.getElementById("btn-close-lightbox")?.addEventListener("click", () => {
    document.getElementById("artifact-lightbox-modal")?.classList.add("hidden");
    document.getElementById("lightbox-content").innerHTML = "";
  });
  document.getElementById("artifact-lightbox-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "artifact-lightbox-modal") {
      e.target.classList.add("hidden");
      document.getElementById("lightbox-content").innerHTML = "";
    }
  });

  // Chat Form & Enter Key Submission
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  chatForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const val = chatInput.value;
    if (!val.trim() || state.isStreaming) return;
    chatInput.value = "";
    await sendChatTurn(val);
  });
  chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm?.requestSubmit();
    }
  });
  document.getElementById("btn-stop-stream")?.addEventListener("click", () => {
    state.abortController?.abort();
  });

  initDagViewportInteractions();
  buildActiveGraphModel();
  renderPresetsSidebar();
  updateComposerHeaderAndChips();
  renderEmptyWelcomeState();

  await refreshAllStudioData();
  if (!state.conversationId) {
    renderEmptyWelcomeState();
  }
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStudio);
  } else {
    initStudio();
  }
}
