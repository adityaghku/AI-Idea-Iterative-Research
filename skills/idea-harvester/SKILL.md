---
name: idea-harvester
description: Iterative AI app idea discovery with a persistent SQLite queue + validation loop.
---

# Idea Harvester (iterative autoresearch, DB-backed)

## Hard Constraints
1. **No scraper-generated code** may be written into any directory named `autoresearch` (including `autoresearch-opencode/`).
2. **Scraper cooldown:** scrape no more frequently than once every ~20 minutes per `run_task_id`.
3. **No duplicates:** dedup URLs in DB; store ideas via DB fingerprints (upsert/merge).

## Stop / Self-Improvement
- Stop early when average evaluation score plateaus.
- Each iteration must answer:
  - `did_improve` (and why)
  - `what_failed` (top failure modes with evidence)
  - `next_highest_value_action` (`fix_scraper` | `refine_queries` | `improve_filters`)

## Persistent State (SQLite)
- Session config: `idea-harvester.md` (goal, run_task_id, max_iterations, stop params)
- Pause sentinel: `.idea-harvester-off` (if present, stop immediately)
- DB file: `idea_harvester.sqlite`
- Use `python3 db/idea_harvester_db.py` for all DB operations.

## DB Helper CLI (paths)
- init: `python3 db/idea_harvester_db.py init --db idea_harvester.sqlite`
- enqueue/dequeue + marking done: `enqueue`, `dequeue`, `mark-done`, `mark-failed`
- URL dedup:
  - `filter-new-urls`
  - `mark-sources-status --status queued|scraped|failed`
- Idea persistence: `store-ideas` (upsert/merge via `ideas.idea_fingerprint`)
- Validation persistence: `store-iteration-validation`
- Knowledge KV: `upsert-kv` / `get-kv`

## Stages
- Planner (`planner`): output `search_plan`
- Researcher (`researcher`): output `candidate_urls` + `coverage_notes`
- Scraper (`scraper`): output `extracted` + `scrape_quality` + `scrape_failures` + `dedup_removed_count`
- Evaluator (`evaluator`): output `ideas` + `iteration_summary`
- Learner (`learner`): output `validation` + `iteration_report` + `knowledge_updates`

JSON-only rule:
- Every stage output must be valid JSON only (no Markdown/code fences/trailing text).

## Final Outputs
- `idea-harvester-top10.json`
- `idea-harvester-top10.md`
- `idea-harvester-last-iteration-report.md`

