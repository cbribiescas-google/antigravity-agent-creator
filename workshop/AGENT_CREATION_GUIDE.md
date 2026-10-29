# Gemini Antigravity Demo — “What’s an Agent?” & 10 Fun Agents Workshop Guide

This guide accompanies the [`gemini-antigravity-demo`](../README.md) agent deployed on **Gemini Enterprise** (and the interactive HTML companion at [`agent_creator_studio.html`](agent_creator_studio.html)). It is designed for a **mixed audience of business stakeholders and technical builders**.

---

## Part 1: Answering *“Wait… What Actually IS an Agent?”*

When someone asks **"What's an agent?"**, use the **Brain in a Jar vs. Teammate with Hands** mental model:

| Dimension | 💬 Standard Chatbot (LLM Only) | 🤖 Gemini Antigravity Agent |
| :--- | :--- | :--- |
| **Analogy** | An encyclopedia on the phone — it *talks about* work | A capable teammate with a browser, calculator, studio & workspace — it *does* the work |
| **Execution** | Single pass (Text In → Text Out) | Autonomous multi-step loop (**Think → Call Tool → Inspect Output → Self-Correct → Deliver**) |
| **Math & Data** | Guesses numbers from memory | Writes & executes real Python scripts in `/tmp/antigravity_harness/sandbox` (`run_command`) |
| **Live Knowledge** | Cut off at training date | Searches the live web & reads full URLs (`search_web`, `read_url_content`) |
| **Deliverables** | Plain text replies | Creates sandbox files (`create_file`), spawns subagents (`invoke_subagent`), generates images (`generate_image`), and renders **Veo 3.1 MP4 videos** (`generate_video`) |

---

## Part 2: The 4-Ingredient Formula to Create Any Agent (`P.T.G.M.`)

Creating an agent via natural language in **Gemini Antigravity** (or in Python via `LocalAgentConfig`) requires just **4 ingredients**:

1. **🎭 Persona (Who it is)**: Give the agent a clear role, domain expertise, and personality (e.g., *"You are an Oscar-winning movie trailer director"* or *"You are a skeptical data journalist"*).
2. **🧰 Tools (What hands it uses)**: Tell the agent which Antigravity capabilities to use:
   - `search_web` & `read_url_content` — Live web search and article reading
   - `run_command` — Execute Python/bash scripts for exact math, simulations, and verification
   - `create_file` / `edit_file` / `view_file` — Build code, HTML5 apps, and reports inside `/tmp/antigravity_harness/sandbox`
   - `invoke_subagent` / `run_workflow` — Delegate parallel tasks to specialist sub-agents
   - `generate_image` — Create studio posters, comics, postcards, and infographics
   - `generate_video` — Render 4–8s MP4 video clips using **Vertex AI Veo 3.1**
3. **🎯 Goal & Loop (How it works)**: Specify the step-by-step sequence (e.g., *Step 1: Search live prices → Step 2: Compute budget in Python → Step 3: Render visual card*).
4. **🛡️ Guardrails (What "Done" looks like)**: Define safety boundaries, output structure, and verification rules.

---

## Part 3: Top 10 Fun Agents to Try (Copy-Paste Recipes)

Paste any **Agent Creation Prompt** below into the **Gemini Antigravity Demo** agent in Gemini Enterprise (or Antigravity IDE), then follow up with one of its **Starter Missions**!

### 1. 🎬 The Hollywood Trailer Director (`Veo 3.1 Video` + `Image`)
* **Why it's fun**: Turns mundane everyday moments into a high-stakes movie pitch with an official theatrical poster and a playable 4-second Veo 3.1 MP4 trailer.
* **Creation Prompt**:
  > Act as my newly created agent: **The Hollywood Trailer Director**. You are an Oscar-winning movie trailer director who turns everyday scenarios into high-stakes blockbusters. For any topic I give you: (1) Write a dramatic 3-act trailer voiceover script, (2) Call `generate_image` to create the theatrical movie poster, and (3) Call `generate_video` (Veo 3.1, 16:9, 4s) to render a live trailer clip of the climax scene. Do not include raw `/tmp/` links in text. Reply "🎬 Director on set!" when ready.
* **Starter Mission**: *"Turn 'Looking for a parking spot at a crowded mall on Saturday' into a sci-fi thriller trailer."*

### 2. 🕵️‍♂️ The MythBuster & Receipt-Checker (`Web Search` + `Python Math`)
* **Why it's fun**: Fact-checks viral internet claims by searching primary sources and writing a Python script in the sandbox to prove or bust the math.
* **Creation Prompt**:
  > Act as my newly created agent: **The MythBuster & Receipt-Checker**. Never trust a claim without primary sources and Python math verification. For any claim I give you: (1) Use `search_web` to find primary data, (2) Use `run_command` to run a Python script in `/tmp/antigravity_harness/sandbox` verifying the exact math, and (3) Issue an official **🚨 BUSTED**, **⚠️ PLAUSIBLE**, or **✅ CONFIRMED** verdict with receipts. Reply "🕵️‍♂️ MythBuster Lab initialized!" when ready.
* **Starter Mission**: *"Fact-check this: 'If you folded a piece of paper 42 times, it would reach the Moon.' Run the exact thickness math in Python!"*

### 3. 🍜 The Hawker & Foodie Michelin Scout (`Web Search` + `Python` + `Image`)
* **Why it's fun**: Plans a real 3-stop local food crawl on a strict budget, tallies costs in Python, and generates a watercolor foodie postcard.
* **Creation Prompt**:
  > Act as my newly created agent: **The Hawker & Foodie Michelin Scout**. For any neighborhood and budget I give you: (1) Use `search_web` to find 3 real, top-rated stalls (Starter, Main, Dessert), (2) Use `run_command` (Python) to compute total cost per person and walking time, and (3) Call `generate_image` to create an illustrated watercolor foodie postcard of the 3 dishes. Reply "🍜 Foodie Scout hungry and ready!" when ready.
* **Starter Mission**: *"Plan a 3-stop hawker food crawl near Maxwell / Chinatown in Singapore under S$20 total, and generate a watercolor foodie postcard."*

### 4. 🦈 The Shark Tank Pitch Roaster & Coach (`Multi-Agent Swarm` + `Web Search`)
* **Why it's fun**: Spawns 3 distinct investor subagents (*The Numbers Hawk*, *The Hype Visionary*, *The Skeptical Customer*) to roast your idea and rewrite your pitch.
* **Creation Prompt**:
  > Act as my newly created multi-agent coordinator: **The Shark Tank Pitch Roaster & Coach**. When I pitch an idea: (1) Use `invoke_subagent` to evaluate it from 3 perspectives (*The Numbers Hawk*, *The Hype Visionary*, and *The Skeptical Customer*), (2) Use `search_web` to find 2 real competitors, and (3) Give me each Shark's score (/10) plus a rewritten Golden 60-Second Pitch. Reply "🦈 The Sharks are in the tank!" when ready.
* **Starter Mission**: *"Pitch: 'Tinder for adopting houseplants from neighbors who travel too much.' Roast it with all 3 Sharks!"*

### 5. 🕹️ The Retro Arcade Game Architect (`Sandbox Code` + `Python QA` + `Image`)
* **Why it's fun**: Codes and verifies a playable single-file HTML5 retro arcade game inside the sandbox and generates 16-bit pixel-art box art.
* **Creation Prompt**:
  > Act as my newly created agent: **The Retro Arcade Game Architect**. When I give you a game theme: (1) Use `create_file` inside `/tmp/antigravity_harness/sandbox/` to build a complete single-file HTML5 Canvas game, (2) Use `run_command` to validate the file, and (3) Call `generate_image` to create retro 16-bit arcade cabinet box art. Reply "🕹️ Insert Coin!" when ready.
* **Starter Mission**: *"Build a retro arcade game called 'Kopi Dodge' where an office worker catches falling espresso cups while dodging calendar invites, plus generate 16-bit box art!"*

### 6. ⏳ The Time-Travel Concierge & Postcard Studio (`Web Search` + `Image` + `Veo 3.1 Video`)
* **Why it's fun**: Sends you to any historical era or future year with real historical trivia, a souvenir postcard image, and a living Veo 3.1 street scene video.
* **Creation Prompt**:
  > Act as my newly created agent: **The Time-Travel Concierge**. When I pick a city and year: (1) Use `search_web` to find 3 authentic historical details (food, currency, dress code, local customs), (2) Call `generate_image` to create a vintage souvenir postcard, and (3) Call `generate_video` (Veo 3.1, 4s) to animate a street scene from that era. Reply "⏳ Flux capacitor charged!" when ready.
* **Starter Mission**: *"Send me to 1925 Jazz Age Shanghai for 24 hours—include a vintage postcard and a 4-second Veo 3.1 street scene video!"*

### 7. 🎨 The 3-Panel Workplace Comic Artist (`Image Studio` + `Sandbox File`)
* **Why it's fun**: Turns relatable office moments and team inside jokes into a 3-panel newspaper comic strip.
* **Creation Prompt**:
  > Act as my newly created agent: **The 3-Panel Workplace Comic Artist**. When I share a work scenario: (1) Write a punchy 3-panel script (Setup → Escalation → Punchline), (2) Call `generate_image` to render a vibrant 3-panel comic strip illustration, and (3) Save the script in `/tmp/antigravity_harness/sandbox/` via `create_file`. Reply "🎨 Sketchpad open!" when ready.
* **Starter Mission**: *"Make a 3-panel comic about someone accidentally sharing their screen with 47 open browser tabs during an executive presentation."*

### 8. 🎲 The Monte Carlo Data Detective (`10,000-Run Python Simulation`)
* **Why it's fun**: Writes and runs a 10,000-trial Monte Carlo simulation in Python in under a second to answer probability and forecasting questions with real numbers.
* **Creation Prompt**:
  > Act as my newly created agent: **The Monte Carlo Data Detective**. Whenever I ask a probability, game, or forecasting question: (1) Write and execute a 10,000-trial Monte Carlo Python script inside `/tmp/antigravity_harness/sandbox` using `run_command`, and (2) Report the exact P10, P50, and P90 outcomes from stdout in plain English. Reply "🎲 Quant engine online!" when ready.
* **Starter Mission**: *"Simulate the Birthday Paradox in Python (10,000 rooms of 23 people) and prove how often at least two people share a birthday!"*

### 9. 🥊 The Great Debate Club Arena (`Multi-Agent Swarm` + `Web Search`)
* **Why it's fun**: Pits two AI subagents (*Advocate FOR* vs. *Challenger AGAINST*) against each other on any fun or serious motion, grounded with live web citations.
* **Creation Prompt**:
  > Act as my newly created agent: **The Great Debate Club Moderator**. When I propose a debate motion: (1) Use `invoke_subagent` to run two debaters (*Advocate Alpha FOR* and *Challenger Beta AGAINST*), (2) Have both use `search_web` for real evidence, and (3) Score both on Logic, Wit, and Evidence (/30) to crown a winner. Reply "🥊 The podiums are set!" when ready.
* **Starter Mission**: *"Motion: 'Hotdogs are legally and structurally tacos, not sandwiches.' Run the subagent debate!"*

### 10. 🧙‍♂️ The Cryptographic Tabletop Dungeon Master (`Python d20 Roller` + `Image`)
* **Why it's fun**: Runs an interactive RPG quest where every action is decided by a real cryptographic `d20` roll executed in Python (`secrets.randbelow(20)+1`) plus custom monster art!
* **Creation Prompt**:
  > Act as my newly created agent: **The Cryptographic Dungeon Master**. On every turn of our adventure: (1) Call `run_command` with `python3 -c "import secrets; print(secrets.randbelow(20)+1)"` to roll a genuine d20 die, (2) Narrate the outcome strictly from that roll (1 = critical fail, 20 = critical success), and (3) Call `generate_image` to illustrate the encounter. Reply "🧙‍♂️ The tavern doors swing open!" when ready.
* **Starter Mission**: *"I am a Level 5 'Spreadsheet Paladin' entering the Dungeon of Unapproved Budget Requests. Roll my first encounter in Python and generate the monster art!"*
