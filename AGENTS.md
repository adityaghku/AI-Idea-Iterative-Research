# AGENTS.md – Multi-Agent AI App Idea Harvester

## Overview
This project implements a multi‑agent system that continuously scrapes the internet for AI application ideas. The agents collaborate to discover, extract, evaluate, and learn from sources, iteratively improving their search strategies.

## Agent Roles

| Agent       | Responsibility |
|-------------|----------------|
| Orchestrator | Coordinates workflow, routes messages, manages state. |
| Planner     | Generates search plans based on high‑level goals and past learning. |
| Researcher  | Uses search APIs and scraping to find candidate sources (URLs, forums, etc.). |
| Scraper     | Writes and executes code to extract structured data from sources. |
| Evaluator   | Scores extracted ideas using novelty, feasibility, market potential, etc. |
| Learner     | Analyzes results to update heuristics for the Planner. |

## Communication
Agents communicate via a message queue. Messages are JSON objects with fields: `from_agent`, `to_agent`, `task_id`, `payload`.

## Workflow
1. **Init** – User provides initial prompt.
2. **Plan** – Planner creates a list of search queries and target sources.
3. **Research** – Researcher finds relevant URLs.
4. **Scrape** – Scraper extracts text and structures.
5. **Evaluate** – Evaluator produces scored ideas.
6. **Learn** – Learner updates knowledge base.
7. **Loop** – Repeat steps 2–6 for N iterations or until convergence.
8. **Finish** – Output final ideas.

## Code Execution
Agents that need to execute code (e.g., scraping scripts) send code to a dedicated **Sandbox** skill, which runs it safely and returns results. The sandbox supports Python with common libraries.

## Getting Started
This repository is set up to run under OpenCode using the `idea-harvester` skill (iterative autoresearch paradigm).

1. Load/start the skill:
   - start your OpenCode session and run `/idea-harvester`
2. The agent will create:
   - `idea-harvester.md` (session config)
   - `idea_harvester.sqlite` (persistent queue + results DB)
3. At the end (or on early stop), the agent should write:
   - `idea-harvester-top10.json`
   - `idea-harvester-top10.md`

## Configuration
Configuration is controlled via fields in `idea-harvester.md`:
- `max_iterations` (default 5)
- `plateau_window` (default 2)
- `min_improvement` (default 0.0)

Persistent queue + state:
- `idea_harvester.sqlite`

DB schema:
- `idea_harvester_schema.sql`