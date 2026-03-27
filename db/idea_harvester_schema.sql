-- Persistent state for the "idea-harvester" OpenCode skill.
-- SQLite is used so the queue + results survive restarts/resume.
--
-- Usage:
--   python3 db/idea_harvester_db.py init --db idea_harvester.sqlite
--
-- Notes:
-- - All JSON payloads/results are stored as TEXT and should be valid JSON.
-- - The orchestrator is responsible for setting iteration_number and stage.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
  run_id              INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id             TEXT NOT NULL UNIQUE,
  goal                TEXT NOT NULL,
  model               TEXT,
  max_iterations     INTEGER NOT NULL DEFAULT 5,
  plateau_window     INTEGER NOT NULL DEFAULT 2,
  min_improvement    REAL NOT NULL DEFAULT 0.0,
  created_at          INTEGER NOT NULL,
  updated_at          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS iterations (
  iteration_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  run_task_id         TEXT NOT NULL,
  iteration_number   INTEGER NOT NULL,
  status              TEXT NOT NULL DEFAULT 'active', -- active|complete|stopped
  avg_score          REAL,
  validation_score  REAL,
  validation_explain TEXT,
  planner_output     TEXT,  -- JSON string
  researcher_output  TEXT,  -- JSON string
  scraper_output     TEXT,  -- JSON string
  evaluator_output   TEXT,  -- JSON string
  learner_output     TEXT,  -- JSON string
  started_at         INTEGER NOT NULL,
  finished_at        INTEGER,
  UNIQUE (run_task_id, iteration_number),
  FOREIGN KEY (run_task_id) REFERENCES runs(task_id) ON DELETE CASCADE
);

-- Generic message queue so the "Orchestrator" can resume safely.
CREATE TABLE IF NOT EXISTS queue_messages (
  message_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  run_task_id         TEXT NOT NULL,
  iteration_number   INTEGER, -- nullable during initialization/finalization
  from_agent          TEXT NOT NULL,
  to_agent            TEXT NOT NULL,
  stage               TEXT, -- planner|researcher|scraper|evaluator|learner|finalize
  payload             TEXT NOT NULL, -- JSON string
  available_at       INTEGER NOT NULL DEFAULT 0, -- epoch seconds; only dequeue when now >= available_at
  status              TEXT NOT NULL DEFAULT 'pending', -- pending|processing|done|failed
  attempts            INTEGER NOT NULL DEFAULT 0,
  created_at          INTEGER NOT NULL,
  locked_at           INTEGER,
  processed_at        INTEGER,
  locked_by           TEXT, -- optional: model name / worker id
  result              TEXT, -- JSON string
  error               TEXT,
  FOREIGN KEY (run_task_id) REFERENCES runs(task_id) ON DELETE CASCADE
);

-- Prevent accidental duplicate enqueues for the same stage/iteration.
-- Note: iteration_number can be NULL; duplicates may still be possible for initialization/finalize.
CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_unique_iter_stage
  ON queue_messages(run_task_id, iteration_number, to_agent, stage);

CREATE INDEX IF NOT EXISTS idx_queue_messages_run_status
  ON queue_messages(run_task_id, status, to_agent, iteration_number, message_id);

CREATE TABLE IF NOT EXISTS knowledge_kv (
  run_task_id         TEXT NOT NULL,
  key                 TEXT NOT NULL,
  value               TEXT NOT NULL, -- JSON string
  updated_at          INTEGER NOT NULL,
  PRIMARY KEY (run_task_id, key),
  FOREIGN KEY (run_task_id) REFERENCES runs(task_id) ON DELETE CASCADE
);

-- Store evaluated ideas (top-N can be computed from this table).
CREATE TABLE IF NOT EXISTS ideas (
  idea_id             INTEGER PRIMARY KEY AUTOINCREMENT,
  run_task_id         TEXT NOT NULL,
  iteration_number   INTEGER NOT NULL,
  source_urls        TEXT NOT NULL, -- JSON string array
  idea_title         TEXT NOT NULL,
  idea_summary       TEXT,
  idea_payload       TEXT NOT NULL, -- JSON string (full structured idea object)
  idea_fingerprint   TEXT, -- sha256 fingerprint used for dedup (nullable for old DBs)
  score               REAL NOT NULL,
  score_breakdown    TEXT, -- JSON string (novelty/feasibility/market etc)
  evaluator_explain  TEXT, -- freeform
  created_at          INTEGER NOT NULL,
  canonical_idea_id   INTEGER, -- self-reference for merged ideas
  merged_at           INTEGER, -- timestamp when merged
  FOREIGN KEY (run_task_id) REFERENCES runs(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ideas_run_score
  ON ideas(run_task_id, score DESC, iteration_number);

-- Deduplicated sources (URLs) per run.
-- Used to avoid scraping the same URL repeatedly.
CREATE TABLE IF NOT EXISTS sources (
  source_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  run_task_id       TEXT NOT NULL,
  url_normalized    TEXT NOT NULL,
  url_fingerprint   TEXT NOT NULL,
  category          TEXT,
  status            TEXT NOT NULL DEFAULT 'queued', -- queued|scraped|failed
  attempts          INTEGER NOT NULL DEFAULT 0,
  last_attempt_at   INTEGER,
  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL,
  UNIQUE (run_task_id, url_fingerprint),
  FOREIGN KEY (run_task_id) REFERENCES runs(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sources_run_status
  ON sources(run_task_id, status);

-- Flat tags for categorizing ideas (industry, technology, business_model, founder_fit).
CREATE TABLE IF NOT EXISTS tags (
  tag_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT NOT NULL UNIQUE,
  slug             TEXT NOT NULL,
  category         TEXT NOT NULL, -- industry|technology|business_model|founder_fit
  usage_count      INTEGER NOT NULL DEFAULT 0,
  created_at       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tags_name
  ON tags(name);

CREATE INDEX IF NOT EXISTS idx_tags_category
  ON tags(category);

CREATE TABLE IF NOT EXISTS idea_tags (
  idea_id     INTEGER NOT NULL,
  tag_id      INTEGER NOT NULL,
  source      TEXT NOT NULL DEFAULT 'tagger',
  created_at  INTEGER NOT NULL,
  PRIMARY KEY (idea_id, tag_id),
  FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_idea_tags_tag_id
  ON idea_tags(tag_id);

-- Tracks idea merge operations (dedup audit trail).
CREATE TABLE IF NOT EXISTS idea_merges (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  source_idea_id       INTEGER NOT NULL,
  target_idea_id       INTEGER NOT NULL,
  source_fingerprint   TEXT,
  target_fingerprint   TEXT,
  similarity_score    REAL,
  merged_at            INTEGER NOT NULL,
  FOREIGN KEY (source_idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
  FOREIGN KEY (target_idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_idea_merges_target
  ON idea_merges(target_idea_id);

-- Embeddings for semantic similarity detection.
CREATE TABLE IF NOT EXISTS idea_embeddings (
  idea_id         INTEGER PRIMARY KEY,
  embedding       BLOB NOT NULL,
  model_version   TEXT NOT NULL,
  created_at      INTEGER NOT NULL,
  FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_idea_embeddings_idea_id
  ON idea_embeddings(idea_id);

-- Schema version tracking for incremental migrations.
CREATE TABLE IF NOT EXISTS schema_version (
  version         INTEGER PRIMARY KEY,
  applied_at      INTEGER NOT NULL,
  description     TEXT
);

