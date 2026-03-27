-- Migration from v1 to v2: idea-harvester schema
-- Adds tags support, merge tracking, and schema versioning

BEGIN;

CREATE TABLE IF NOT EXISTS schema_version (
  version         INTEGER PRIMARY KEY,
  applied_at      INTEGER NOT NULL,
  description     TEXT
);

CREATE TABLE IF NOT EXISTS tags (
  tag_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT NOT NULL UNIQUE,
  slug             TEXT NOT NULL,
  category         TEXT NOT NULL,
  usage_count      INTEGER NOT NULL DEFAULT 0,
  created_at       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);

CREATE TABLE IF NOT EXISTS idea_tags (
  idea_id     INTEGER NOT NULL,
  tag_id      INTEGER NOT NULL,
  source      TEXT NOT NULL DEFAULT 'tagger',
  created_at  INTEGER NOT NULL,
  PRIMARY KEY (idea_id, tag_id),
  FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_idea_tags_tag_id ON idea_tags(tag_id);

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

CREATE INDEX IF NOT EXISTS idx_idea_merges_target ON idea_merges(target_idea_id);

COMMIT;
