# Continuous Accumulation & Tagging System

## TL;DR

> **Quick Summary**: Transform the idea harvester from run-based to continuously accumulating knowledge base with comprehensive tagging, semantic duplicate detection, and unified database storage.
> 
> **Deliverables**:
> - Tags table with many-to-many junction to ideas
> - Semantic similarity merge using embeddings
> - Separate Tagger agent for extracting tags
> - Database as single source of truth (JSON becomes backup)
> - Dashboard with All Ideas (filterable), Top by Category, and Trends views
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves with 5-7 tasks each
> **Critical Path**: Schema Migration → Tagger Agent → Semantic Merge → Dashboard Update

---

## Context

### Original Request
"Don't split by 'run'. Keep accumulating data and keep some memory of what is already done. Add some tagging to each idea so that the ideas can be grouped and looked at by industry type and any other relevant criteria. Update the dashboard to also account for this. The aim is to have one large wealth of information that is continuously iterated upon."

### Interview Summary

**Key Discussions**:
- **Tagging scope**: All useful tags (industry/type, technology, business model, founder fit)- **Run tracking**: Keep run_task_id internally for debugging/resume, but UI shows continuous accumulation
- **Duplicate handling**: Merge with very high similarity, use semantic embeddings
- **Dashboard views**: All Ideas (filterable), Top by Category, Trends view

**Research Findings**:
- **Critical Bug**: Deduplication mismatch - DB uses SHA256 fingerprint, cross-run merge uses title string match
- **Schema**: Ideas table has `idea_fingerprint`, `run_task_id` FK; tags don't exist yet
- **Dashboard**: Flask web app (port 8133) + CLI markdown generator, no filtering capabilities

### Metis Review

**Identified Gaps** (addressed):
- Tag extraction source → **Separate Tagger Agent** (user decided)
- Merge threshold → **Semantic similarity with embeddings** (user decided)
- Hierarchy depth → **Flat tags** (user decided)
- Accumulation strategy → **Database as source of truth** (user decided)

---

## Work Objectives

### Core Objective
Transform the idea harvester into a continuously accumulating knowledge base where:
1. Ideas accumulate across runs (no run splitting in UI)
2. Tags enable grouping by industry, technology, business model, founder fit
3. Duplicate ideas are merged using semantic similarity
4. Database is the single source of truth
5. Dashboard provides unified view with filtering and trends

### Concrete Deliverables

1. **Database Schema**: Add `tags`, `idea_tags`, `idea_merges` tables + columns to `ideas`
2. **Tagger Agent**: New agent that extracts tags from evaluated ideas
3. **Semantic Merge**: Use embeddings for duplicate detection with configurable threshold
4. **Cross-Run Accumulation**: Database-first storage, JSON becomes backup/export
5. **Dashboard Update**: All Ideas view with tag filtering, Top by Category, Trends

### Definition of Done

- [ ] `sqlite3 idea_harvester.sqlite ".schema tags"` shows tags table
- [ ] Tagger agent runs after Evaluator and populates `idea_tags`
- [ ] Unit test for semantic merge passes with 0.95 similarity threshold
- [ ] Dashboard shows accumulated ideas across all runs (not just one run)
- [ ] Tag filter dropdown works and filters ideas correctly
- [ ] Trends view shows tag distribution over iterations

### Must Have

- Tags table with many-to-many junction (follow Discourse/Forem pattern)
- Semantic similarity merge (embeddings-based with 0.95 threshold)
- Separate Tagger agent (not integrated into Evaluator)
- Database as primary source (JSON file as backup only)
- Dashboard default to "All Ideas" accumulated view
- Flat tags (no hierarchy)

### Must NOT Have (Guardrails)

- **No tag management UI**: Tags are read-only in dashboard (created by Tagger only)
- **No export functionality**: Not in this phase
- **No idea editing**: Dashboard is read-only
- **No embedding storage overhead**: Compute on-demand, cache results
- **No run comparison UI**: Focus on unified accumulation view
- **No tag hierarchy**: Flat tags only (user decided)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES - pytest with conftest.py fixtures
- **Automated tests**: YES (Tests after)- **Framework**: pytest
- **Test location**: `tests/test_*.py`

### QA Policy

Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Database/Schema**: Use Bash (sqlite3) — Run queries, assert table/column existence
- **Agent Logic**: Use pytest — Unit tests for new agents
- **Dashboard**: Use Playwright — Navigate, interact, assert DOM, screenshot
- **API**: Use curl — Send requests, assert JSON response fields

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — schema foundation):
├── Task 1: Add tags table with category and usage_count columns
├── Task 2: Add idea_tags junction table (many-to-many)
├── Task 3: Add idea_merges audit table + canonical_idea_id column
├── Task 4: Add schema_version table for migrations
├── Task 5: Create migration script with backward compatibility
└── Task 6: Add db functions for tag CRUD operations

Wave 2 (After Wave 1 — tagger agent):
├── Task 7: Define TaggerAgent input/output dataclasses
├── Task 8: Implement TaggerAgent LLM prompt for tag extraction
├── Task 9: Add TaggerAgent to orchestrator pipeline (after Evaluator)
├── Task 10: Implement tag storage in store_ideas()
├── Task 11: Add embedding generation for ideas (for semantic merge)
└── Task 12: Implement semantic similarity merge function

Wave 3 (After Wave 2 — cross-run accumulation):
├── Task 13: Modify orchestrator to skip JSON file, use DB as source
├── Task 14: Update _finalize() to write DB instead of JSON
├── Task 15: Add get_all_ideas() function for accumulated view
├── Task 16: Add get_ideas_by_tags() function for filtering
├── Task 17: Implement merge_duplicate_ideas() with similarity tracking
└── Task 18: Add accumulated_knowledge tracking in DB (not just knowledge_kv)

Wave 4 (After Wave 3 — dashboard):
├── Task 19: Add /api/ideas/all endpoint with tag filtering
├── Task 20: Add /api/tags endpoint for tag list with counts
├── Task 21: Update dashboard HTML for "All Ideas" default view
├── Task 22: Add tag filter dropdown component
├── Task 23: Add Trends view with tag distribution chart
└── Task 24: Add Top by Category view (top 5 per tag category)

Wave FINAL (After ALL implementation tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high + playwright)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 1-6 | — | 7-18 |
| 7-12 | 1-6 | 13-18 |
| 13-18 | 7-12 | 19-24 |
| 19-24 | 13-18 | F1-F4 |
| F1-F4 | 1-24 | user okay |

### Agent Dispatch Summary

- **Wave 1**: 6 tasks → all `quick`
- **Wave 2**: 6 tasks → T7-8 `deep`, T9-10 `unspecified-high`, T11-12 `deep`
- **Wave 3**: 6 tasks → all `unspecified-high`
- **Wave 4**: 6 tasks → all `visual-engineering`
- **FINAL**: 4 tasks → F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

- [x] 1. Add tags table to schema

  **What to do**:
  - Add `tags` table to `db/idea_harvester_schema.sql`
  - Columns: `id` (PK), `name` (TEXT UNIQUE), `slug` (TEXT), `category` (TEXT), `usage_count` (INTEGER DEFAULT 0), `created_at` (INTEGER)
  - Categories: 'industry', 'technology', 'business_model', 'founder_fit'
  - Update `init_db()` in `db/idea_harvester_db.py` to create table

  **Must NOT do**:
  - Do NOT add `parent_id` or hierarchy columns (flat tags only)
  - Do NOT add `alias_for` column (no tag merging yet)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single schema file change, straightforward DDL
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-6)
  - **Blocks**: Tasks 7-12 (TaggerAgent)
  - **Blocked By**: None

  **References**:
  - `db/idea_harvester_schema.sql:1-120` - Existing schema structure for DDL patterns
  - `db/idea_harvester_db.py:154-190` - `init_db()` function for table creation
  - Discourse tag schema: `tags` table with name, slug, count - follow this pattern

  **Acceptance Criteria**:
  - [ ] `tags` table DDL exists in schema file
  - [ ] `init_db()` creates `tags` table on fresh database
  - [ ] Categories defined as: industry, technology, business_model, founder_fit

  **QA Scenarios**:
  ```
  Scenario: Tags table creation
    Tool: Bash (sqlite3)
    Preconditions: Fresh database file
    Steps:
      1. python3 -c "from db.idea_harvester_db import init_db; import sqlite3; conn = sqlite3.connect('test_tags.sqlite'); init_db(conn)"
      2. sqlite3 test_tags.sqlite ".schema tags"
    Expected Result: Output contains "CREATE TABLE tags" with columns id, name, slug, category, usage_count, created_at
    Evidence: .sisyphus/evidence/task-01-tags-table.txt
  ```

  **Commit**: YES (Wave 1 group)
  - Message: `feat(schema): add tags table`
  - Files: `db/idea_harvester_schema.sql`, `db/idea_harvester_db.py`

---

- [x] 2. Add idea_tags junction table

  **What to do**:
  - Add `idea_tags` junction table to schema
  - Columns: `idea_id` (FK to ideas), `tag_id` (FK to tags), `source` (TEXT DEFAULT 'tagger'), `created_at` (INTEGER)
  - Primary key: `(idea_id, tag_id)`
  - Add foreign key constraints with ON DELETE CASCADE
  - Update `init_db()` to create table

  **Must NOT do**:
  - Do NOT add extra columns like confidence score yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single schema file change, junction table pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-6)
  - **Blocks**: Tasks 7-12
  - **Blocked By**: None

  **References**:
  - `db/idea_harvester_schema.sql:83-98` - Ideas table structure for FK pattern
  - `db/idea_harvester_db.py:154-190` - `init_db()` for table creation
  - Discourse/Forem pattern: Many-to-many junction with composite PK

  **Acceptance Criteria**:
  - [ ] `idea_tags` table DDL exists
  - [ ] Composite primary key on `(idea_id, tag_id)`
  - [ ] Foreign keys with CASCADE delete

  **QA Scenarios**:
  ```
  Scenario: Junction table creation
    Tool: Bash (sqlite3)
    Preconditions: Database with tags and ideas tables
    Steps:
      1. sqlite3 test.sqlite ".schema idea_tags"
    Expected Result: Output contains PRIMARY KEY (idea_id, tag_id) and FOREIGN KEY constraints
    Evidence: .sisyphus/evidence/task-02-junction-table.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 3. Add idea_merges table and canonical_idea_id column

  **What to do**:
  - Add `idea_merges` table: `id` (PK), `source_idea_id` (FK), `target_idea_id` (FK), `source_fingerprint` (TEXT), `target_fingerprint` (TEXT), `similarity_score` (REAL), `merged_at` (INTEGER)
  - Add `canonical_idea_id` column to `ideas` table (nullable FK to self)
  - Add `merged_at` column to `ideas` table (nullable INTEGER)
  - Update `init_db()` to handle schema migration for existing databases

  **Must NOT do**:
  - Do NOT delete or migrate existing data yet (Wave 3 task)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Schema additions only, no data migration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 13-18 (merge logic)
  - **Blocked By**: None

  **References**:
  - `db/idea_harvester_schema.sql:83-98` - Ideas table for ALTER TABLE pattern
  - `db/idea_harvester_db.py:104-113` - Existing `_idea_fingerprint()` function

  **Acceptance Criteria**:
  - [ ] `idea_merges` table DDL exists
  - [ ] `ideas` table has `canonical_idea_id` column
  - [ ] `ideas` table has `merged_at` column
  - [ ] Migration handles existing databases

  **QA Scenarios**:
  ```
  Scenario: Merge tracking schema
    Tool: Bash (sqlite3)
    Preconditions: Existing database from previous run
    Steps:
      1. python3 -c "from db.idea_harvester_db import init_db; import sqlite3; conn = sqlite3.connect('existing.sqlite'); init_db(conn)"
      2. sqlite3 existing.sqlite ".schema idea_merges"
      3. sqlite3 existing.sqlite "PRAGMA table_info(ideas)"
    Expected Result: idea_merges table exists, ideas table shows canonical_idea_id and merged_at columns
    Evidence: .sisyphus/evidence/task-03-merge-schema.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 4. Add schema_version table for migrations

  **What to do**:
  - Add `schema_version` table: `version` (INTEGER PK), `applied_at` (INTEGER), `description` (TEXT)
  - Add `get_schema_version()` and `set_schema_version()` functions in `db/idea_harvester_db.py`
  - Update `init_db()` to check version and apply migrations incrementally
  - Insert version 1 for existing schema, bump to version 2 for new tables

  **Must NOT do**:
  - Do NOT use external migration library (Alembic, etc.) - keep it simple

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple version tracking table
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: None (foundation)
  - **Blocked By**: None

  **References**:
  - `db/idea_harvester_db.py:154-190` - `init_db()` function for integration
  - SQLite PRAGMA pattern for schema introspection

  **Acceptance Criteria**:
  - [ ] `schema_version` table exists
  - [ ] `get_schema_version(conn)` returns current version
  - [ ] `set_schema_version(conn, version, description)` updates version
  - [ ] Fresh DB starts at version 2, existing DB migrates to version 2

  **QA Scenarios**:
  ```
  Scenario: Version tracking
    Tool: Bash (sqlite3)
    Preconditions: Fresh database
    Steps:
      1. sqlite3 test.sqlite "SELECT * FROM schema_version"
    Expected Result: Row with version=2, description="add tags, idea_tags, idea_merges, canonical columns"
    Evidence: .sisyphus/evidence/task-04-version-table.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 5. Create migration script with backward compatibility

  **What to do**:
  - Create `db/migrate_v1_to_v2.sql` with ALTER TABLE statements
  - Add `migrate_schema(conn, from_version, to_version)` function in `db/idea_harvester_db.py`
  - Ensure migration is idempotent (can run multiple times safely)
  - Test migration on existing `idea_harvester.sqlite` file

  **Must NOT do**:
  - Do NOT lose any existing data
  - Do NOT require database rebuild

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: SQL migration script with transaction safety
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Wave 2-4 (migrations needed first)
  - **Blocked By**: Tasks 1-4 (schema DDL must exist)

  **References**:
  - `db/idea_harvester_db.py:init_db()` - Where to call migrations
  - SQLite ALTER TABLE limitations (can't drop columns, etc.)

  **Acceptance Criteria**:
  - [ ] Migration script exists and runs without error
  - [ ] Existingideas preserved
  - [ ] New tables created
  - [ ] Migration idempotent (safe to re-run)

  **QA Scenarios**:
  ```
  Scenario: Migration preserves data
    Tool: Bash (sqlite3 + python)
    Preconditions: Existing database with ideas
    Steps:
      1. sqlite3 idea_harvester.sqlite "SELECT COUNT(*) FROM ideas" > count_before.txt
      2. python3 -c "from db.idea_harvester_db import migrate_schema; import sqlite3; conn = sqlite3.connect('idea_harvester.sqlite'); migrate_schema(conn, 1, 2)"
      3. sqlite3 idea_harvester.sqlite "SELECT COUNT(*) FROM ideas" > count_after.txt
      4. diff count_before.txt count_after.txt
    Expected Result: No difference (counts match)
    Evidence: .sisyphus/evidence/task-05-migration-data.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 6. Add db functions for tag CRUD operations

  **What to do**:
  - Add to `db/idea_harvester_db.py`:
    - `create_tag(conn, name, category)` → returns tag_id
    - `get_or_create_tag(conn, name, category)` → returns tag_id
    - `get_tags_by_idea(conn, idea_id)` → returns list of tags
    - `get_ideas_by_tags(conn, tag_names)` → returns list of ideas
    - `add_tag_to_idea(conn, idea_id, tag_id, source='tagger')`
    - `increment_tag_usage(conn, tag_id)`
  - Add appropriate indexes on `idea_tags` for efficient queries

  **Must NOT do**:
  - Do NOT add tag editing/deleting functions yet

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: CRUD functions following existing patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 7-12 (TaggerAgent needs these)
  - **Blocked By**: Tasks 1-2 (schema must exist)

  **References**:
  - `db/idea_harvester_db.py:528-641` - `store_ideas()` function for pattern
  - `db/idea_harvester_db.py:350-410` - Query patterns for ideas

  **Acceptance Criteria**:
  - [ ] `create_tag()` inserts tag and returns ID
  - [ ] `get_or_create_tag()` creates if not exists
  - [ ] `get_tags_by_idea()` returns correct tags
  - [ ] `get_ideas_by_tags()` filters correctly
  - [ ] `increment_tag_usage()` updates counter

  **QA Scenarios**:
  ```
  Scenario: Tag CRUD operations
    Tool: Python (pytest)
    Preconditions: Database with tags and ideas tables
    Steps:
      1. pytest tests/test_tag_crud.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-06-tag-crud.txt
  ```

  **Commit**: YES (Wave 1 group)

---

- [x] 7. Define TaggerAgent input/output dataclasses

  **What to do**:
  - Add to `agents/config.py`:
    - `TaggerInput` dataclass with fields: `ideas: list[dict]`, `categories: list[str]`
    - `TaggerOutput` dataclass with fields: `tagged_ideas: list[dict]`, `tag_counts: dict[str, int]`
    - Update `Stage` enum to include `TAGGER` after `EVALUATOR`
  - Each tagged idea must have `tags: list[str]` and `tag_categories: dict[str, str]` (tag -> category mapping)

  **Must NOT do**:
  - Do NOT modify Evaluator to output tags (separate agent)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Dataclass definitions only
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8-12)
  - **Blocks**: Tasks 9-10 (orchestrator needs dataclasses)
  - **Blocked By**: Task 1-6 (schema must exist)

  **References**:
  - `agents/config.py:50-100` - Existing dataclass patterns (PlannerInput, ResearcherInput, etc.)
  - `agents/config.py:15-25` - Stage enum for adding TAGGER

  **Acceptance Criteria**:
  - [ ] `TaggerInput` dataclass defined
  - [ ] `TaggerOutput` dataclass defined
  - [ ] `Stage.TAGGER` added to enum
  - [ ] Stage order: PLANNER → RESEARCHER → SCRAPER → EVALUATOR → TAGGER → LEARNER

  **QA Scenarios**:
  ```
  Scenario: Dataclass definitions
    Tool: Python (pytest)
    Steps:
      1. python3 -c "from agents.config import TaggerInput, TaggerOutput, Stage; print(Stage.TAGGER)"
    Expected Result: Output shows "Stage.TAGGER" and dataclasses can be instantiated
    Evidence: .sisyphus/evidence/task-07-tagger-dataclasses.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [x] 8. Implement TaggerAgent LLM prompt for tag extraction

  **What to do**:
  - Create `agents/tagger.py` with `TaggerAgent` class
  - Implement `execute()` method that:
    - Takes `TaggerInput` with evaluated ideas
    - Calls LLM with prompt to extract tags for each idea
    - Returns `TaggerOutput` with tagged ideas
  - Prompt should instruct LLM to extract:
    - Industry (vertical): e.g., Healthcare, Finance, E-commerce
    - Technology: e.g., LLM, Computer Vision, Automation
    - Business model: e.g., SaaS, Marketplace, API
    - Founder fit: e.g., Solo-founder, Requires-team
  - Use batch processing (multiple ideas per LLM call) for efficiency

  **Must NOT do**:
  - Do NOT call LLM once per idea (inefficient)
  - Do NOT hardcode tag lists (LLM should infer from context)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: LLM prompt engineering and output parsing
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9 (orchestrator integration)
  - **Blocked By**: Task 7 (dataclasses)

  **References**:
  - `agents/evaluator.py:80-180` - LLM call pattern for structured output
  - `agents/llm_client.py:complete_json()` - JSON completion function
  - `agents/config.py:50-100` - Input/output dataclass patterns

  **Acceptance Criteria**:
  - [ ] `TaggerAgent` class exists with `execute()` method
  - [ ] LLM prompt extracts all 4 tag categories
  - [ ] Output includes tag_categories mapping
  - [ ] Batch processing (multiple ideas per call)

  **QA Scenarios**:
  ```
  Scenario: Tagger extracts tags
    Tool: Python (pytest)
    Preconditions: Mock LLM returning tags
    Steps:
      1. pytest tests/test_tagger.py::test_tagger_extraction -v
    Expected Result: TaggerOutput contains ideas with correct tags
    Evidence: .sisyphus/evidence/task-08-tagger-extraction.txt

  Scenario: Tagger handles empty input
    Tool: Python (pytest)
    Preconditions: Empty idea list
    Steps:
      1. pytest tests/test_tagger.py::test_tagger_empty -v
    Expected Result: Returns empty tagged_ideas list, empty tag_counts
    Evidence: .sisyphus/evidence/task-08-tagger-empty.txt
  ```

  **Commit**: YES (Wave 2 group)
  - Message: `feat(tagger): implement TaggerAgent for idea tagging`
  - Files: `agents/tagger.py`

---

- [x] 9. Add TaggerAgent to orchestrator pipeline

  **What to do**:
  - Add TaggerAgent to orchestrator's `_execute_agent()` routing in `agents/orchestrator.py`
  - Stage order: PLANNER → RESEARCHER → SCRAPER → EVALUATOR → TAGGER → LEARNER
  - Pass EvaluatorOutput to TaggerAgent as TaggerInput
  - Store TaggerOutput in knowledge_kv for iteration tracking
  - Add logging with `log_structured("tagger_complete", ...)`

  **Must NOT do**:
  - Do NOT skip Evaluator (tags extracted from evaluated ideas)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integration in orchestrator pipeline
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 8)
  - **Parallel Group**: Sequential
  - **Blocks**: Task 10 (storage)
  - **Blocked By**: Tasks 7-8 (dataclasses + agent implementation)

  **References**:
  - `agents/orchestrator.py:380-520` - `_execute_agent()` routing
  - `agents/orchestrator.py:486-497` - Learner pattern for storing output

  **Acceptance Criteria**:
  - [ ] TaggerAgent added to Stage enum execution
  - [ ] EvaluatorOutput passed to TaggerAgent
  - [ ] TaggerOutput stored in knowledge_kv
  - [ ] Logging structured with iteration number

  **QA Scenarios**:
  ```
  Scenario: Tagger runs after Evaluator
    Tool: Python
    Preconditions: Mock scheduler, database with evaluated ideas
    Steps:
      1. python3 -c "from agents.orchestrator import Orchestrator; o = Orchestrator(':memory:'); print([s.name for s in Stage])"
    Expected Result: Output includes "TAGGER" after "EVALUATOR" before "LEARNER"
    Evidence: .sisyphus/evidence/task-09-tagger-pipeline.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [x] 10. Implement tag storage in store_ideas()

  **What to do**:
  - Modify `store_ideas()` in `db/idea_harvester_db.py` to:
    - Extract tags from tagged_ideas
    - Call `get_or_create_tag()` for each tag
    - Insert into `idea_tags` junction table
    - Call `increment_tag_usage()` for each tag assignment
  - Handle case where idea already has tags (skip or update based on source)

  **Must NOT do**:
  - Do NOT store duplicate tag assignments

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Database integration, transaction handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 6, 9)
  - **Parallel Group**: Sequential
  - **Blocks**: Task 16 (filtering)
  - **Blocked By**: Tasks 6 (tag CRUD), 9 (orchestrator)

  **References**:
  - `db/idea_harvester_db.py:528-641` - Existing `store_ideas()` function
  - `db/idea_harvester_db.py:589-619` - Upsert pattern for deduplication

  **Acceptance Criteria**:
  - [ ] Tags stored in `tags` table
  - [ ] Junction records created in `idea_tags`
  - [ ] `usage_count` incremented
  - [ ] No duplicate tag assignments

  **QA Scenarios**:
  ```
  Scenario: Tags stored correctly
    Tool: Python (sqlite3)
    Preconditions: Database with tagged ideas
    Steps:
      1. python3 -c "from db.idea_harvester_db import store_ideas, get_tags_by_idea; ..."1. sqlite3 test.sqlite "SELECT t.name FROM tags t JOIN idea_tags it ON t.id = it.tag_id"
    Expected Result: Tags appear in output, usage_count > 0
    Evidence: .sisyphus/evidence/task-10-tag-storage.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [x] 11. Add embedding generation for ideas

  **What to do**:
  - Create `agents/embeddings.py` with:
    - `generate_idea_embedding(idea: dict) -> list[float]` using LLM or local model
  - Consider using sentence-transformers for local embedding (no API cost)
  - Cache embeddings in a new `idea_embeddings` table: `idea_id` (FK), `embedding` (BLOB), `model_version` (TEXT), `created_at` (INTEGER)
  - Add `get_or_create_embedding(conn, idea_id, idea)` function

  **Must NOT do**:
  - Do NOT store embeddings in idea_payload (keep separate)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: New embedding infrastructure, model selection
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 12 (semantic merge)
  - **Blocked By**: Task 3 (canonical_idea_id column)

  **References**:
  - Sentence-transformers library: `pip install sentence-transformers`
  - `db/idea_harvester_schema.sql` - Add idea_embeddings table
  - Embedding caching pattern: compute once, store BLOB

  **Acceptance Criteria**:
  - [ ] `generate_idea_embedding()` returns embedding vector
  - [ ] `idea_embeddings` table created
  - [ ] Embeddings cached per idea
  - [ ] Model version tracked for future updates

  **QA Scenarios**:
  ```
  Scenario: Embedding generation
    Tool: Python
    Steps:
      1. python3 -c "from agents.embeddings import generate_idea_embedding; emb = generate_idea_embedding({'title': 'Test', 'summary': 'Summary'}); print(len(emb))"
    Expected Result: Output shows embedding length (e.g., 384 or 768)
    Evidence: .sisyphus/evidence/task-11-embeddings.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [x] 12. Implement semantic similarity merge function

  **What to do**:
  - Create `db/idea_harvester_db.py` function:
    - `find_similar_ideas(conn, idea_id, threshold=0.95) -> list[dict]` returns similar ideas above threshold
    - `merge_ideas(conn, source_id, target_id, similarity_score) -> None` records merge in `idea_merges`
  - Use cosine similarity between embeddings
  - For each new idea, check against existing ideas using embeddings
  - If similarity >= threshold, merge and record in `idea_merges`
  - Set `canonical_idea_id` on merged idea

  **Must NOT do**:
  - Do NOT delete merged ideas (keep with canonical_idea_id set)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Similarity algorithm, careful merge logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 11)
  - **Parallel Group**: Sequential
  - **Blocks**: Task 17 (merge call in orchestrator)
  - **Blocked By**: Task 11 (embeddings)

  **References**:
  - `db/idea_harvester_db.py:528-641` - `store_ideas()` pattern
  - Cosine similarity: `dot(a, b) / (norm(a) * norm(b))`
  - `idea_merges` table for audit trail

  **Acceptance Criteria**:
  - [ ] `find_similar_ideas()` returns ideas above threshold
  - [ ] `merge_ideas()` updates canonical_idea_id
  - [ ] Merge recorded in `idea_merges`
  - [ ] Threshold configurable (default 0.95)

  **QA Scenarios**:
  ```
  Scenario: Semantic similarity detection
    Tool: Python (sqlite3)
    Preconditions: Database with embedded ideas
    Steps:
      1. python3 -c "from db.idea_harvester_db import find_similar_ideas; print(len(find_similar_ideas(conn, 1, 0.9)))"
    Expected Result: Returns list of similar ideas (may be empty)
    Evidence: .sisyphus/evidence/task-12-similarity.txt

  Scenario: Merge recording
    Tool: Python (sqlite3)
    Preconditions: Two similar ideas
    Steps:
      1. merge_ideas(conn, source_id=2, target_id=1, similarity=0.97)
      2. sqlite3 test.sqlite "SELECT * FROM idea_merges"
    Expected Result: Row with source_idea_id=2, target_idea_id=1, similarity_score=0.97
    Evidence: .sisyphus/evidence/task-12-merge-record.txt
  ```

  **Commit**: YES (Wave 2 group)

---

- [ ] 13. Modify orchestrator to use DB as source of truth

  **What to do**:
  - Update `agents/orchestrator.py`:
    - Remove JSON file reading in `_load_accumulated_ideas()`
    - Change `_finalize()` to write ONLY to database
    - Keep JSON file for backup/export, but don't read from it
  - Add `get_all_ideas(db_path)` function call to get accumulated ideas from DB

  **Must NOT do**:
  - Do NOT remove JSON export (keep for backup)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Core orchestrator logic modification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 14-18
  - **Blocked By**: Tasks 9-12 (TaggerAgent + merge)

  **References**:
  - `agents/orchestrator.py:535-567` - `_load_accumulated_ideas()` and `_finalize()`
  - `db/idea_harvester_db.py:get_top_ideas()` - Pattern for DB retrieval

  **Acceptance Criteria**:
  - [ ] JSON file not read at startup
  - [ ] Ideas loaded from database
  - [ ] JSON file still written for backup

  **QA Scenarios**:
  ```
  Scenario: Database is source of truth
    Tool: Python
    Preconditions: Database with accumulated ideas
    Steps:
      1. python3 -c "from agents.orchestrator import Orchestrator; o = Orchestrator(':memory:'); ideas = o._load_accumulated_ideas(); print(len(ideas))"
    Expected Result: Ideas loaded from DB, not JSON file
    Evidence: .sisyphus/evidence/task-13-db-source.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 14. Update _finalize() to write DB instead of JSON

  **What to do**:
  - Modify `_finalize()` in `agents/orchestrator.py`:
    - Remove JSON file creation or move to separate backup function
    - Write accumulated ideas to database via `store_ideas()`
    - Keep `idea-harvester.json` and `idea-harvester.md` as export formats
  - Add `export_ideas_to_json(db_path, output_file)` utility function

  **Must NOT do**:
  - Do NOT lose existing JSON/MD export functionality

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Finalization logic modification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 13)
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 13

  **References**:
  - `agents/orchestrator.py:570-650` - `_finalize()` implementation
  - `db/idea_harvester_db.py:store_ideas()` - Storage pattern

  **Acceptance Criteria**:
  - [ ] Ideas written to database
  - [ ] JSON file still created for backup
  - [ ] MD file still created for reading

  **QA Scenarios**:
  ```
  Scenario: Finalization writes to DB
    Tool: Python (sqlite3)
    Preconditions: Orchestrator with accumulated ideas
    Steps:
      1. orchestrator._finalize()
      2. sqlite3 idea_harvester.sqlite "SELECT COUNT(*) FROM ideas WHERE canonical_idea_id IS NULL"
    Expected Result: Count matches accumulated ideas
    Evidence: .sisyphus/evidence/task-14-finalize-db.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 15. Add get_all_ideas() function for accumulated view

  **What to do**:
  - Add `get_all_ideas(db_path, limit=None, offset=0, tag_filter=None) -> list[dict]` to `db/idea_harvester_db.py`
  - Query all non-merged ideas (where `canonical_idea_id IS NULL` or same as idea_id)
  - Sort by score DESC
  - Include tags in each idea dict
  - Support pagination with limit/offset
  - Support tag filtering via JOIN with `idea_tags`

  **Must NOT do**:
  - Do NOT include merged ideas (canonical_idea_id set)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Database query function
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 19-24 (dashboard)
  - **Blocked By**: Tasks 1-6 (schema)

  **References**:
  - `db/idea_harvester_db.py:350-410` - Existing query patterns
  - `db/idea_harvester_db.py:528-641` - `store_ideas()` for dict assembly

  **Acceptance Criteria**:
  - [ ] Returns all non-merged ideas
  - [ ] Sorted by score DESC
  - [ ] Includes tags in each idea dict
  - [ ] Supports pagination
  - [ ] Supports tag filtering

  **QA Scenarios**:
  ```
  Scenario: All ideas retrieval
    Tool: Python
    Preconditions: Database with 100+ ideas
    Steps:
      1. python3 -c "from db.idea_harvester_db import get_all_ideas; ideas = get_all_ideas('idea_harvester.sqlite'); print(len(ideas))"
    Expected Result: Returns all non-merged ideas
    Evidence: .sisyphus/evidence/task-15-all-ideas.txt

  Scenario: Tag filtering
    Tool: Python
    Preconditions: Ideas with tags
    Steps:
      1. python3 -c "from db.idea_harvester_db import get_all_ideas; ideas = get_all_ideas('idea_harvester.sqlite', tag_filter=['SaaS']); print([i['idea_title'] for i in ideas])"
    Expected Result: Returns only ideas with 'SaaS' tag
    Evidence: .sisyphus/evidence/task-15-tag-filter.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 16. Add get_ideas_by_tags() function for filtering

  **What to do**:
  - Add `get_ideas_by_tags(db_path, tag_names: list[str], match_all=False) -> list[dict]` to `db/idea_harvester_db.py`
  - If `match_all=True`, return ideas that have ALL specified tags
  - If `match_all=False`, return ideas that have ANY specified tags
  - Sort by score DESC
  - Include all idea fields + tags

  **Must NOT do**:
  - Do NOT modify `get_all_ideas()` (separate function)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Database query function
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 19-24 (dashboard)
  - **Blocked By**: Task 6 (tag CRUD)

  **References**:
  - `db/idea_harvester_db.py:528-641` - Query patterns
  - `db/idea_harvester_schema.sql:idea_tags` - Junction table for JOIN

  **Acceptance Criteria**:
  - [ ] `match_all=True` returns ideas with all tags
  - [ ] `match_all=False` returns ideas with any tag
  - [ ] Sorted by score DESC

  **QA Scenarios**:
  ```
  Scenario: Match all tags
    Tool: Python
    Preconditions: Ideas with multiple tags
    Steps:
      1. python3 -c "from db.idea_harvester_db import get_ideas_by_tags; ideas = get_ideas_by_tags('idea_harvester.sqlite', ['SaaS', 'B2B'], match_all=True); print(len(ideas))"
    Expected Result: Returns only ideas with both SaaS AND B2B tags
    Evidence: .sisyphus/evidence/task-16-match-all.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 17. Implement merge_duplicate_ideas() with similarity tracking

  **What to do**:
  - Add `merge_duplicate_ideas(db_path, threshold=0.95) -> int` to `db/idea_harvester_db.py`
  - For each idea, find similar ideas using `find_similar_ideas()`
  - Merge if similarity >= threshold
  - Record merge in `idea_merges` table
  - Set `canonical_idea_id` on merged idea
  - Return number of merges performed
  - Call this function in orchestrator after storing new ideas

  **Must NOT do**:
  - Do NOT merge across different categories (keep industry/tech separation)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex merge logic with database operations
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 12)
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 12 (similarity function)

  **References**:
  - `db/idea_harvester_db.py:528-641` - `store_ideas()` pattern
  - `db/idea_harvester_db.py:find_similar_ideas()` - From Task 12

  **Acceptance Criteria**:
  - [ ] Finds similar ideas above threshold
  - [ ] Records merge in `idea_merges`
  - [ ] Sets `canonical_idea_id` on merged idea
  - [ ] Returns count of merges
  - [ ] Called in orchestrator after store_ideas()

  **QA Scenarios**:
  ```
  Scenario: Merge duplicates
    Tool: Python
    Preconditions: Database with similar ideas
    Steps:
      1. python3 -c "from db.idea_harvester_db import merge_duplicate_ideas; count = merge_duplicate_ideas('idea_harvester.sqlite', 0.95); print(count)"
      2. sqlite3 idea_harvester.sqlite "SELECT COUNT(*) FROM idea_merges"
    Expected Result: Returns merge count, idea_merges has records
    Evidence: .sisyphus/evidence/task-17-merge-duplicates.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 18. Add accumulated_knowledge tracking in DB

  **What to do**:
  - Update knowledge accumulation in `agents/orchestrator.py`:
    - Instead of `knowledge_kv`, store accumulated insights in a dedicated table
  - Add `accumulated_learnings` table: `id` (PK), `run_task_id` (FK), `category` (TEXT), `insight` (TEXT), `iteration` (INTEGER), `created_at` (INTEGER)
  - Modify Learner agent output to include structured learnings
  - Add `get_all_learnings(db_path) -> list[dict]` function

  **Must NOT do**:
  - Do NOT remove `knowledge_kv` (keep for backward compatibility)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Schema change + integration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: Task 4 (schema_version)

  **References**:
  - `agents/orchestrator.py:486-497` - Current knowledge accumulation
  - `db/idea_harvester_schema.sql` - Add learnings table

  **Acceptance Criteria**:
  - [ ] `accumulated_learnings` table created
  - [ ] Learnings stored per iteration
  - [ ] `get_all_learnings()` returns all learnings

  **QA Scenarios**:
  ```
  Scenario: Learnings accumulation
    Tool: Python (sqlite3)
    Preconditions: Multiple iterations with learnings
    Steps:
      1. python3 -c "from db.idea_harvester_db import get_all_learnings; print(len(get_all_learnings('idea_harvester.sqlite')))"
      2. sqlite3 idea_harvester.sqlite "SELECT category, insight FROM accumulated_learnings"
    Expected Result: Returns learnings from all iterations
    Evidence: .sisyphus/evidence/task-18-learnings.txt
  ```

  **Commit**: YES (Wave 3 group)

---

- [ ] 19. Add /api/ideas/all endpoint with tag filtering

  **What to do**:
  - Add route `/api/ideas/all` to `dashboard.py`
  - Query parameters: `tags` (comma-separated), `limit`, `offset`
  - Use `get_all_ideas()` with tag_filter parameter
  - Return JSON: `{ideas: [...], total: N, tags: [...]}`
  - Include pagination metadata

  **Must NOT do**:
  - Do NOT return merged ideas (only canonical)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Flask route implementation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Tasks 21-24
  - **Blocked By**: Tasks 15-16 (DB functions)

  **References**:
  - `dashboard.py:265-290` - Existing `/api/run/<id>/ideas` route pattern
  - `db/idea_harvester_db.py:get_all_ideas()` - From Task 15

  **Acceptance Criteria**:
  - [ ] Endpoint returns all accumulated ideas
  - [ ] `tags` query parameter filters correctly
  - [ ] Pagination works with `limit` and `offset`
  - [ ] Response includes total count

  **QA Scenarios**:
  ```
  Scenario: API returns all ideas
    Tool: Bash (curl)
    Preconditions: Dashboard running, database with ideas
    Steps:
      1. curl http://localhost:8133/api/ideas/all | jq '.ideas | length'
    Expected Result: Returns all non-merged ideas
    Evidence: .sisyphus/evidence/task-19-api-all.txt

  Scenario: Tag filtering works
    Tool: Bash (curl)
    Preconditions: Ideas with SaaS tag
    Steps:
      1. curl "http://localhost:8133/api/ideas/all?tags=SaaS" | jq '.ideas[].tags'
    Expected Result: All returned ideas have 'SaaS' tag
    Evidence: .sisyphus/evidence/task-19-api-filter.txt
  ```

  **Commit**: YES (Wave 4 group)

---

- [ ] 20. Add /api/tags endpoint for tag list with counts

  **What to do**:
  - Add route `/api/tags` to `dashboard.py`
  - Query `tags` table with `usage_count`
  - Return JSON: `{tags: [{name, category, usage_count}, ...]}`
  - Support `category` query parameter to filter by category

  **Must NOT do**:
  - Do NOT return tags with 0 usage

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Flask route implementation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Tasks 21-24
  - **Blocked By**: Task 6 (tag CRUD)

  **References**:
  - `dashboard.py:265-290` - Existing route pattern
  - `db/idea_harvester_db.py` - Add `get_all_tags()` function

  **Acceptance Criteria**:
  - [ ] Endpoint returns all tags with counts
  - [ ] `category` parameter filters correctly
  - [ ] Sorted by usage_count DESC

  **QA Scenarios**:
  ```
  Scenario: API returns tags
    Tool: Bash (curl)
    Preconditions: Database with tagged ideas
    Steps:
      1. curl http://localhost:8133/api/tags | jq '.tags[].name'
    Expected Result: Returns all used tags
    Evidence: .sisyphus/evidence/task-20-api-tags.txt
  ```

  **Commit**: YES (Wave 4 group)

---

- [ ] 21. Update dashboard HTML for "All Ideas" default view

  **What to do**:
  - Modify `DASHBOARD_TEMPLATE` in `dashboard.py`:
    - Change default view to show all accumulated ideas (not just current run)
    - Add "All Ideas" tab/button as default active tab
    - Keep "Current Run" view as secondary option
  - Update JavaScript to call `/api/ideas/all` instead of `/api/run/<id>/ideas`for default view
  - Add stats summary: Total Ideas, Total Runs, Top Tags

  **Must NOT do**:
  - Do NOT remove run-specific view (keep as option)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: HTML/CSS/JS dashboard updates
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 19)
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 22-24
  - **Blocked By**: Tasks 19-20 (API endpoints)

  **References**:
  - `dashboard.py:18-258` - DASHBOARD_TEMPLATE
  - `dashboard.py:340-400` - JavaScript fetch logic

  **Acceptance Criteria**:
  - [ ] Default view shows all accumulated ideas
  - [ ] "Current Run" button to switch to run-specific view
  - [ ] Stats summary shows Total Ideas, Total Runs, Top Tags

  **QA Scenarios**:
  ```
  Scenario: Default view shows all ideas
    Tool: Playwright
    Preconditions: Dashboard running
    Steps:
      1. await page.goto('http://localhost:8133/')
      2. const count = await page.locator('.stat-card').first().textContent()
    Expected Result: Count matches total ideas across all runs
    Evidence: .sisyphus/evidence/task-21-default-view.png
  ```

  **Commit**: YES (Wave 4 group)

---

- [ ] 22. Add tag filter dropdown component

  **What to do**:
  - Add tag filter dropdown to dashboard HTML
  - Fetch tags from `/api/tags` on page load
  - Multi-select dropdown with checkboxes for each category
  - On selection change, call `/api/ideas/all?tags=...`
  - Update idea list dynamically without page reload

  **Must NOT do**:
  - Do NOT use external UI library (use vanilla JS or simple CSS)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI component implementation
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 21)
  - **Parallel Group**: Sequential
  - **Blocks**: Task 24
  - **Blocked By**: Task 19-21

  **References**:
  - `dashboard.py:18-258` - DASHBOARD_TEMPLATE
  - Vanilla JS pattern: `<select multiple>` or checkbox group

  **Acceptance Criteria**:
  - [ ] Dropdown shows all tags grouped by category
  - [ ] Multi-select with checkboxes
  - [ ] Selection filters ideas dynamically
  - [ ] Clear all filters button

  **QA Scenarios**:
  ```
  Scenario: Tag filter works
    Tool: Playwright
    Preconditions: Dashboard running with tagged ideas
    Steps:
      1. await page.goto('http://localhost:8133/')
      2. await page.selectOption('#tag-filter', 'SaaS')
      3. const titles = await page.locator('.idea-card .title').allTextContents()
    Expected Result: All displayed ideas have 'SaaS' tag
    Evidence: .sisyphus/evidence/task-22-tag-filter.png
  ```

  **Commit**: YES (Wave 4 group)

---

- [ ] 23. Add Trends view with tag distribution chart

  **What to do**:
  - Add "Trends" tab in dashboard HTML
  - Create chart showing tag frequency distribution
  - Fetch data from `/api/tags` and calculate percentages
  - Use simple CSS/HTML bar chart (no external library)
  - Show: Top 10 tags by usage, tag distribution by category

  **Must NOT do**:
  - Do NOT use Chart.js or D3 (keep it simple)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Data visualization component
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: Task20 (API endpoint)

  **References**:
  - `dashboard.py:18-258` - DASHBOARD_TEMPLATE
  - CSS flexbox bar chart pattern

  **Acceptance Criteria**:
  - [ ] "Trends" tab navigation
  - [ ] Bar chart showing tag distribution
  - [ ] Percentage labels on bars

  **QA Scenarios**:
  ```
  Scenario: Trends view loads
    Tool: Playwright
    Preconditions: Dashboard running
    Steps:
      1. await page.goto('http://localhost:8133/')
      2. await page.click('text=Trends')
      3. const chartVisible = await page.locator('.trends-chart').isVisible()
    Expected Result: Chart is visible
    Evidence: .sisyphus/evidence/task-23-trends-view.png
  ```

  **Commit**: YES (Wave 4 group)

---

- [ ] 24. Add Top by Category view

  **What to do**:
  - Add "Top by Category" tab in dashboard HTML
  - Show top 5 ideas per tag category (industry, technology, business_model, founder_fit)
  - Use `/api/ideas/all?tags=...` with filtering
  - Display in card grid format
  - Update when tag filter changes

  **Must NOT do**:
  - Do NOT hardcode tag names (fetch from API)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI component with API integration
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: None
  - **Blocked By**: Tasks 19-22

  **References**:
  - `dashboard.py:18-258` - DASHBOARD_TEMPLATE
  - Card grid CSS pattern

  **Acceptance Criteria**:
  - [ ] "Top by Category" tab navigation
  - [ ] 4 sections: Industry, Technology, Business Model, Founder Fit
  - [ ] Top 5 ideas per section
  - [ ] Syncs with tag filter

  **QA Scenarios**:
  ```
  Scenario: Top by Category view loads
    Tool: Playwright
    Preconditions: Dashboard running with tagged ideas
    Steps:
      1. await page.goto('http://localhost:8133/')
      2. await page.click('text=Top by Category')
      3. const sections = await page.locator('.category-section').count()
    Expected Result: 4 sections visible (industry, technology, business_model, founder_fit)
    Evidence: .sisyphus/evidence/task-24-top-category.png
  ```

  **Commit**: YES (Wave 4 group)

---

## Final Verification Wave

>4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `tsc --noEmit` + linter + `bun test`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state. Execute EVERY QA scenario from EVERY task. Test cross-task integration. Test edge cases: empty state, no tags, merge conflict. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT Have" compliance.Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(schema): add tags, idea_tags, idea_merges tables` — db/idea_harvester_schema.sql, db/idea_harvester_db.py
- **Wave 2**: `feat(tagger): add TaggerAgent for idea tagging` — agents/tagger.py, agents/config.py
- **Wave 3**: `feat(accumulation): database-first cross-run accumulation` — agents/orchestrator.py, db/idea_harvester_db.py
- **Wave 4**: `feat(dashboard): add All Ideas, Trends, and tag filtering` — dashboard.py, db/idea_harvester_dashboard.py

---

## Success Criteria

### Verification Commands

```bash
# Schema verification
sqlite3 idea_harvester.sqlite ".schema tags"
sqlite3 idea_harvester.sqlite ".schema idea_tags"
sqlite3 idea_harvester.sqlite ".schema idea_merges"

# Tag extraction verification
sqlite3 idea_harvester.sqlite "SELECT t.name, COUNT(*) FROM tags t JOIN idea_tags it ON t.id = it.tag_id GROUP BY t.name"

# Merge verification
sqlite3 idea_harvester.sqlite "SELECT COUNT(*) FROM idea_merges"

# Dashboard verification
curl http://localhost:8133/api/ideas/all | jq '.ideas | length'
curl http://localhost:8133/api/tags | jq '.tags'
```

### Final Checklist

- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Dashboard shows accumulated ideas across runs
- [ ] Tag filtering works
- [ ] Trends view loads
- [ ] Semantic merge works with 0.95 threshold