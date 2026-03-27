# Idea Harvester DB Reference (SQLite)

The idea-harvester skill stores all persistent state in:
- `idea_harvester.sqlite`

## Tables

### `runs`
One row per overall research run.

Key fields:
- `task_id`: stable run id (UUID-like string)
- `goal`: your objective
- `max_iterations`, `plateau_window`, `min_improvement`: stop conditions

### `iterations`
One row per iteration number within a run.

Key fields:
- `iteration_number`
- `status`: `active|complete|stopped`
- `avg_score`: computed from `ideas` table
- `validation_score`: learner-provided validation metric
- `validation_explain`: explanation for the validation metric

### `queue_messages`
This is the durable queue that enables safe resume.

Key fields:
- `status`: `pending|processing|done|failed`
- `from_agent`, `to_agent`, `stage`: stage routing
- `iteration_number`: which iteration it belongs to
- `payload`: JSON string (inputs to the destination agent)
- `result`: JSON string (agent output)
- `available_at`: epoch seconds; the skill only dequeues when `now >= available_at`
- `locked_at`, `locked_by`: set when dequeued

### `knowledge_kv`
Key-value knowledge items produced by the Learner stage (used by the Planner stage).

### `ideas`
Evaluator-produced idea records, one row per idea.

Key fields:
- `idea_fingerprint`: sha256 fingerprint used for dedup
- `score`: 0-100
- `source_urls`: JSON string array
- `idea_payload`: structured idea object JSON

### `sources`
Deduplicated URLs per run used to avoid scraping the same source repeatedly.

Key fields:
- `url_fingerprint`: sha256 fingerprint used for dedup
- `status`: `queued|scraped|failed`

## How stop is computed

The dashboard script uses:
- last window average avg_score over `plateau_window`
- previous window average avg_score
- `improvement = last_avg - prev_avg`
- stop if `improvement <= min_improvement`

## Schema

The canonical schema is in:
- `idea_harvester_schema.sql`

