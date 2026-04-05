---
name: idea-harvester
description: Iterative AI app idea discovery with a persistent SQLite queue + validation loop.
---

# Idea Harvester (iterative autoresearch, DB-backed)

## Hard Constraints
1. **No scraper-generated code** may be written into any directory named `autoresearch` (including `autoresearch-opencode/`).
   - If code/temp files are needed, use `./.idea-harvester-tmp/` at repo root or the sandbox ephemeral workspace.
2. **Scraper cooldown:** scrape no more frequently than once every ~2 minutes per `run_task_id`.
3. **No duplicates:**
   - Do not enqueue duplicate URLs (dedup via DB).
   - Do not store duplicate ideas (upsert/merge via DB fingerprints).

## Stop / Loop Behavior
- Iterate up to `max_iterations` with early stop when average evaluation score plateaus.
- After each iteration, produce a short report that answers:
  - `did_improve` (and why)
  - `what_failed` (top failure modes with evidence)
  - `next_highest_value_action` (`fix_scraper` | `refine_queries` | `improve_filters`)

## Persistent State (SQLite)
- Session config: `idea-harvester.md` (goal, run_task_id, max_iterations, stop params)
- Pause sentinel: `.idea-harvester-off` (if present, stop immediately)
- DB file: `idea_harvester.sqlite`
- Use `idea_harvester_db.py` CLI commands below.

## DB Helper CLI (paths)
Use the reorganized locations:
- `python3 db/idea_harvester_db.py ...`
- `python3 db/idea_harvester_dashboard.py ...` (optional report)

Key commands:
- init: `python3 db/idea_harvester_db.py init --db idea_harvester.sqlite`
- create run: `python3 db/idea_harvester_db.py create-run --db idea_harvester.sqlite --task-id <RUN_TASK_ID> --goal <GOAL> --max-iterations <N> --plateau-window <W> --min-improvement <X>`
- enqueue/dequeue + marking done: use `enqueue`, `dequeue`, `mark-done`, `mark-failed`
- URL dedup:
  - `filter-new-urls` (candidate -> keep_urls / skipped_urls)
  - `mark-sources-status --status queued|scraped|failed`
- Idea persistence: `store-ideas` (uses `ideas.idea_fingerprint` for upsert/merge)
- Validation persistence:
  - `store-iteration-validation` (store `iterations.validation_score` + `iterations.validation_explain`)
- Knowledge KV:
  - `upsert-kv` / `get-kv`

## Stages (Planner → Researcher → Scraper → Evaluator → Learner)
Queue stages use `to_agent` = `planner|researcher|scraper|evaluator|learner`.

JSON-only rule:
- Every stage output must be **valid JSON only** (no Markdown/code fences/trailing text).

### Orchestrator Core Steps (per iteration)
- For each `iteration_number` from `1..max_iterations`, process stages in this order: `planner → researcher → scraper → evaluator → learner`.
- After `researcher` output: deduplicate `candidate_urls` using `filter-new-urls`, pass `keep_urls` to `scraper`, and mark kept URLs as `queued`.
- Before `scraper` runs: enforce cooldown by reading `scraper_last_completed_epoch` via `get-kv` and using the ~20-minute wait.
- After scraping: mark each URL as `scraped` or `failed` in `sources` and update `scraper_last_completed_epoch`.
- After `evaluator`: call `store-ideas`.
- After `learner`: call `store-iteration-validation` and `upsert-kv` with all `knowledge_updates`.

### Planner (output JSON)
Output a `search_plan` with:
- `queries` (list)
- `target_sources` (list)
- `scraping_depth` (int)
- `max_candidates` (int)
- `novelty_filters` / `feasibility_filters`
- `filter_policy_updates` (what to change next iter)

### Researcher (output JSON)
- `candidate_urls`: list of `{ "url": "...", "category": "...", "reason": "...", "source_type": "blog|forum|..." }`
- `coverage_notes`

### Scraper (output JSON; include evidence + throttle signals)
- `extracted`: list of objects with:
  - `url`, `key_claims`, `relevant_quotes`
  - `extraction_success` (boolean)
  - `extraction_notes`
- `scrape_failures`: list of `{url, failure_mode, evidence}`
- `scrape_quality` including `coverage_score` and `extraction_success_rate`
- `dedup_removed_count`

Scraper throttle:
- Before scraping, enforce cooldown (~20 minutes) using `knowledge_kv` key `scraper_last_completed_epoch`.

### Evaluator (output JSON)
- `ideas`: list of ideas with:
  - `idea_title`, `idea_summary`, `source_urls`
  - `score` (0-100)
  - `score_breakdown` (novelty/feasibility/market)
  - `evaluator_explain`

### Learner (output JSON)
Must include:
- `validation.validation_metric` (0-100)
- `validation.validation_explain` (tie metric to scraper/query/filter quality)
- `iteration_report` with:
  - `did_improve` + `did_improve_reason`
  - `what_failed`: top failure modes (by stage) with evidence
  - `next_highest_value_action`: one of `fix_scraper|refine_queries|improve_filters` + why
- `knowledge_updates` (list of KV updates for planner)

## Final Outputs
Write:
- `idea-harvester.md` (markdown report with top ideas)
- `idea-harvester-last-iteration-report.md` (detailed iteration report)

All data is stored in `idea_harvester.sqlite` (primary source of truth).

