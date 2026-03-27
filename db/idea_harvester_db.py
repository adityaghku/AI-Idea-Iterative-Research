#!/usr/bin/env python3
"""
SQLite persistence + queue utilities for the idea-harvester OpenCode skill.

Design goals:
- Deterministic schema, minimal dependencies (stdlib only).
- Safe resume: queue_messages status lets an "Orchestrator" pick up where it left off.
- Easy LLM usage: all CLI args are explicit and JSON is passed as a string.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse


def _utc_epoch_seconds() -> int:
    return int(time.time())


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "idea_harvester_schema.sql")
    schema_path = os.path.abspath(schema_path)
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Missing schema file: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = _connect(db_path)
    try:
        existing_tables = {
            x["name"]
            for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

        clean_sql = _remove_sql_comments(schema_sql)
        for statement in clean_sql.split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            if stmt.upper().startswith("PRAGMA"):
                continue
            table_name = _extract_table_name(stmt)
            if table_name and table_name in existing_tables:
                continue
            if stmt.upper().startswith("CREATE INDEX") or stmt.upper().startswith("CREATE UNIQUE INDEX"):
                idx_name = _extract_index_name(stmt)
                if idx_name:
                    idx_exists = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                        (idx_name,),
                    ).fetchone()
                    if idx_exists:
                        continue
                    idx_table = _extract_index_table(stmt)
                    if idx_table:
                        if idx_table not in existing_tables:
                            continue
                        idx_cols = _extract_index_columns(stmt)
                        table_cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({idx_table})")}
                        if not idx_cols.issubset(table_cols):
                            continue
            conn.execute(stmt)

        version = get_schema_version(conn)

        if version < 1:
            _apply_v1_migrations(conn)
            set_schema_version(conn, 1, "initial schema with runs, iterations, queue, ideas, sources")

        if version < 2:
            _apply_v2_migrations(conn)
            set_schema_version(conn, 2, "add tags, idea_tags, idea_merges, canonical columns")

        if version < 3:
            _apply_v3_migrations(conn)
            set_schema_version(conn, 3, "add idea_embeddings table for semantic similarity")

        conn.commit()
    finally:
        conn.close()


def _extract_table_name(stmt: str) -> str | None:
    import re
    match = re.match(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", stmt, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_index_name(stmt: str) -> str | None:
    import re
    match = re.match(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", stmt, re.IGNORECASE)
    return match.group(1) if match else None


def _remove_sql_comments(sql: str) -> str:
    import re
    return re.sub(r"--[^\n]*", "", sql)


def _extract_index_table(stmt: str) -> str | None:
    import re
    match = re.search(r"ON\s+(\w+)\s*\(", stmt, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_index_columns(stmt: str) -> set[str]:
    import re
    match = re.search(r"ON\s+\w+\s*\(([^)]+)\)", stmt, re.IGNORECASE)
    if match:
        cols = match.group(1)
        return {c.strip().split()[-1] for c in cols.split(",")}
    return set()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for r in rows:
        if r["name"] == column:
            return True
    return False


def _apply_v1_migrations(conn: sqlite3.Connection) -> None:
    if "queue_messages" in [
        x["name"]
        for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]:
        if not _has_column(conn, "queue_messages", "available_at"):
            conn.execute(
                "ALTER TABLE queue_messages ADD COLUMN available_at INTEGER NOT NULL DEFAULT 0;"
            )

    if not _has_column(conn, "iterations", "validation_score"):
        conn.execute("ALTER TABLE iterations ADD COLUMN validation_score REAL;")
    if not _has_column(conn, "iterations", "validation_explain"):
        conn.execute("ALTER TABLE iterations ADD COLUMN validation_explain TEXT;")


def _apply_v2_migrations(conn: sqlite3.Connection) -> None:
    existing_tables = [
        x["name"]
        for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]

    if "ideas" in existing_tables:
        if not _has_column(conn, "ideas", "idea_fingerprint"):
            conn.execute("ALTER TABLE ideas ADD COLUMN idea_fingerprint TEXT;")
        if not _has_column(conn, "ideas", "canonical_idea_id"):
            conn.execute(
                "ALTER TABLE ideas ADD COLUMN canonical_idea_id INTEGER REFERENCES ideas(idea_id);"
            )
        if not _has_column(conn, "ideas", "merged_at"):
            conn.execute("ALTER TABLE ideas ADD COLUMN merged_at INTEGER;")

    if "tags" not in existing_tables:
        conn.executescript(
            """
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
            """
        )

    if "idea_tags" not in existing_tables:
        conn.executescript(
            """
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
            CREATE INDEX IF NOT EXISTS idx_idea_tags_idea_id ON idea_tags(idea_id);
            """
        )

    if "idea_merges" not in existing_tables:
        conn.executescript(
            """
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
            """
        )

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ideas_unique_fingerprint ON ideas(run_task_id, idea_fingerprint);"
    )


def _apply_v3_migrations(conn: sqlite3.Connection) -> None:
    existing_tables = [
        x["name"]
        for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]

    if "idea_embeddings" not in existing_tables:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idea_embeddings (
              idea_id         INTEGER PRIMARY KEY,
              embedding       BLOB NOT NULL,
              model_version   TEXT NOT NULL,
              created_at      INTEGER NOT NULL,
              FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
            );
            """
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_idea_embeddings_idea_id ON idea_embeddings(idea_id);"
    )


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return result is not None


def get_schema_version(conn: sqlite3.Connection) -> int:
    if not _has_table(conn, "schema_version"):
        return 0
    row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    return int(row["version"]) if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int, description: str = "") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
        (version, _utc_epoch_seconds(), description)
    )


def _normalize_url(url: str) -> str:
    # URL normalization for stable fingerprinting.
    # Keep query, remove fragments, lower-case scheme/host, trim trailing slashes.
    u = (url or "").strip()
    if not u:
        return ""
    parsed = urlparse(u)
    scheme = (parsed.scheme or "http").lower()
    netloc = (parsed.netloc or "").lower()
    parsed = parsed._replace(scheme=scheme, netloc=netloc, fragment="")
    rebuilt = urlunparse(parsed)
    while rebuilt.endswith("/"):
        rebuilt = rebuilt[:-1]
    return rebuilt


def _url_fingerprint(url_normalized: str) -> str:
    return hashlib.sha256(url_normalized.encode("utf-8")).hexdigest()


def _idea_fingerprint(idea: dict[str, Any]) -> str:
    # Fingerprint using title + summary + payload (truncated) to reduce near-duplicates.
    title = str(idea.get("idea_title") or idea.get("title") or "").strip().lower()
    summary = str(idea.get("idea_summary") or idea.get("summary") or "").strip().lower()
    score_part = str(idea.get("score") or idea.get("rating") or "").strip()
    payload_part = json.dumps(
        idea.get("idea_payload") or idea, sort_keys=True, ensure_ascii=False
    )[:4000]
    raw = f"{title}\n{summary}\n{score_part}\n{payload_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_run(
    db_path: str,
    task_id: str,
    goal: str,
    model: Optional[str],
    max_iterations: int,
    plateau_window: int,
    min_improvement: float,
) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        conn.execute(
            """
            INSERT INTO runs(task_id, goal, model, max_iterations, plateau_window, min_improvement, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
              goal=excluded.goal,
              model=excluded.model,
              max_iterations=excluded.max_iterations,
              plateau_window=excluded.plateau_window,
              min_improvement=excluded.min_improvement,
              updated_at=excluded.updated_at
            """,
            (
                task_id,
                goal,
                model,
                int(max_iterations),
                int(plateau_window),
                float(min_improvement),
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_iteration_row(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        conn.execute(
            """
            INSERT INTO iterations(run_task_id, iteration_number, status, started_at)
            VALUES(?, ?, 'active', ?)
            ON CONFLICT(run_task_id, iteration_number) DO UPDATE SET
              status=excluded.status,
              started_at=COALESCE(iterations.started_at, excluded.started_at),
              finished_at=NULL
            """,
            (run_task_id, int(iteration_number), now),
        )
        conn.commit()
    finally:
        conn.close()


def enqueue_message(
    db_path: str,
    run_task_id: str,
    iteration_number: Optional[int],
    from_agent: str,
    to_agent: str,
    stage: str,
    payload: dict[str, Any],
    available_at: Optional[int] = None,
) -> int:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        avail = int(available_at) if available_at is not None else now
        cur = conn.execute(
            """
            INSERT INTO queue_messages(run_task_id, iteration_number, from_agent, to_agent, stage, payload, status, attempts, created_at, available_at)
            VALUES(?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
            """,
            (
                run_task_id,
                int(iteration_number) if iteration_number is not None else None,
                from_agent,
                to_agent,
                stage,
                json.dumps(payload),
                now,
                avail,
            ),
        )
        conn.commit()
        return int(cur.lastrowid) if cur.lastrowid is not None else 0
    finally:
        conn.close()


def dequeue_message(
    db_path: str,
    run_task_id: str,
    to_agent: str,
    iteration_number: Optional[int],
    stage: Optional[str],
    locked_by: Optional[str],
) -> Optional[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()

        # Note: We don't implement "FOR UPDATE" semantics here (sqlite limited), but we do
        # an atomic update-by-id pattern to reduce double-processing.
        where_clauses: list[str] = [
            "run_task_id = ?",
            "status = 'pending'",
            "to_agent = ?",
        ]
        params: list[Any] = [run_task_id, to_agent]
        if iteration_number is not None:
            where_clauses.append("iteration_number = ?")
            params.append(int(iteration_number))
        if stage is not None:
            where_clauses.append("stage = ?")
            params.append(stage)

        row = conn.execute(
            f"""
            SELECT * FROM queue_messages
            WHERE {" AND ".join(where_clauses)}
              AND available_at <= ?
            ORDER BY message_id ASC
            LIMIT 1
            """,
            params + [now],
        ).fetchone()

        if row is None:
            return None

        msg_id = int(row["message_id"])
        conn.execute(
            """
            UPDATE queue_messages
            SET status='processing', locked_at=?, locked_by=?, attempts=attempts+1
            WHERE message_id=? AND status='pending'
            """,
            (now, locked_by or None, msg_id),
        )
        conn.commit()

        out: dict[str, Any] = dict(row)
        out["payload"] = json.loads(out["payload"])
        if out.get("result"):
            out["result"] = json.loads(out["result"])
        return out
    finally:
        conn.close()


def mark_done(db_path: str, message_id: int, result: dict[str, Any]) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        conn.execute(
            """
            UPDATE queue_messages
            SET status='done', processed_at=?, result=?
            WHERE message_id=? AND status IN ('processing','pending')
            """,
            (now, json.dumps(result), int(message_id)),
        )
        conn.commit()
    finally:
        conn.close()


def mark_failed(db_path: str, message_id: int, error: str) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        conn.execute(
            """
            UPDATE queue_messages
            SET status='failed', processed_at=?, error=?
            WHERE message_id=? AND status IN ('processing','pending')
            """,
            (now, error, int(message_id)),
        )
        conn.commit()
    finally:
        conn.close()


def store_iteration_output(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    stage: str,
    json_output: dict[str, Any],
) -> None:
    stage_to_col = {
        "planner": "planner_output",
        "researcher": "researcher_output",
        "scraper": "scraper_output",
        "evaluator": "evaluator_output",
        "learner": "learner_output",
    }
    if stage not in stage_to_col:
        raise ValueError(
            f"Unknown stage: {stage}. Expected one of {sorted(stage_to_col.keys())}"
        )

    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        col = stage_to_col[stage]
        conn.execute(
            f"""
            UPDATE iterations
            SET {col}=?, status='active', planner_output=planner_output
            WHERE run_task_id=? AND iteration_number=?
            """,
            (json.dumps(json_output), run_task_id, int(iteration_number)),
        )
        conn.execute(
            """
            UPDATE runs
            SET updated_at=?
            WHERE task_id=?
            """,
            (now, run_task_id),
        )
        conn.commit()
    finally:
        conn.close()


def store_iteration_validation(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    validation_score: float,
    validation_explain: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            UPDATE iterations
            SET validation_score=?, validation_explain=?
            WHERE run_task_id=? AND iteration_number=?
            """,
            (
                float(validation_score),
                validation_explain or "",
                run_task_id,
                int(iteration_number),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def store_iteration_complete(
    db_path: str, run_task_id: str, iteration_number: int, status: str
) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        conn.execute(
            """
            UPDATE iterations
            SET status=?, finished_at=?
            WHERE run_task_id=? AND iteration_number=?
            """,
            (status, now, run_task_id, int(iteration_number)),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_knowledge_kv(
    db_path: str,
    run_task_id: str,
    key: str,
    value: dict[str, Any],
) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        conn.execute(
            """
            INSERT INTO knowledge_kv(run_task_id, key, value, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(run_task_id, key) DO UPDATE SET
              value=excluded.value,
              updated_at=excluded.updated_at
            """,
            (run_task_id, key, json.dumps(value), now),
        )
        conn.commit()
    finally:
        conn.close()


def get_knowledge_kv(
    db_path: str, run_task_id: str, key: str
) -> Optional[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT value
            FROM knowledge_kv
            WHERE run_task_id=? AND key=?
            """,
            (run_task_id, key),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])
    finally:
        conn.close()


def now_epoch_seconds() -> int:
    return _utc_epoch_seconds()


def get_iteration_avg_scores(db_path: str, run_task_id: str) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT iteration_number, avg_score
            FROM iterations
            WHERE run_task_id=?
            ORDER BY iteration_number ASC
            """,
            (run_task_id,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "iteration_number": int(r["iteration_number"]),
                    "avg_score": r["avg_score"],
                }
            )
        return out
    finally:
        conn.close()


def list_pending_messages(
    db_path: str,
    run_task_id: str,
    to_agent: Optional[str],
    stage: Optional[str],
    iteration_number: Optional[int],
) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        params: list[Any] = [run_task_id]
        clauses: list[str] = ["run_task_id = ? AND status = 'pending'"]
        if to_agent is not None:
            clauses.append("to_agent = ?")
            params.append(to_agent)
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if iteration_number is not None:
            clauses.append("iteration_number = ?")
            params.append(int(iteration_number))

        where_clause = " AND ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT message_id, from_agent, to_agent, stage, iteration_number, payload, attempts, created_at
            FROM queue_messages
            WHERE {where_clause}
            ORDER BY message_id ASC
            """,
            params,
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "message_id": int(r["message_id"]),
                    "from_agent": r["from_agent"],
                    "to_agent": r["to_agent"],
                    "stage": r["stage"],
                    "iteration_number": (
                        r["iteration_number"]
                        if r["iteration_number"] is None
                        else int(r["iteration_number"])
                    ),
                    "payload": json.loads(r["payload"]),
                    "attempts": int(r["attempts"]),
                    "created_at": int(r["created_at"]),
                }
            )
        return out
    finally:
        conn.close()


# ─── Tag CRUD ─────────────────────────────────────────────────────────────────


def create_tag(conn: sqlite3.Connection, name: str, category: str) -> int:
    """Create a new tag. Returns tag_id. Raises on duplicate."""
    now = _utc_epoch_seconds()
    slug = name.lower().replace(" ", "-")
    cur = conn.execute(
        """
        INSERT INTO tags (name, slug, category, usage_count, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (name, slug, category, now),
    )
    return int(cur.lastrowid)


def get_or_create_tag(conn: sqlite3.Connection, name: str, category: str) -> int:
    """Get existing tag or create new. Returns tag_id."""
    row = conn.execute(
        "SELECT tag_id FROM tags WHERE name = ?", (name,)
    ).fetchone()
    if row is not None:
        return int(row["tag_id"])
    return create_tag(conn, name, category)


def get_tags_by_idea(conn: sqlite3.Connection, idea_id: int) -> list[dict]:
    """Get all tags for an idea. Returns list of {id, name, category, source}."""
    rows = conn.execute(
        """
        SELECT t.tag_id AS id, t.name, t.category, it.source
        FROM tags t
        JOIN idea_tags it ON t.tag_id = it.tag_id
        WHERE it.idea_id = ?
        ORDER BY t.name
        """,
        (idea_id,),
    ).fetchall()
    return [
        {"id": int(r["id"]), "name": r["name"], "category": r["category"], "source": r["source"]}
        for r in rows
    ]


def get_ideas_by_tags(
    conn: sqlite3.Connection,
    tag_names: list[str],
    match_all: bool = False,
) -> list[dict]:
    """Get ideas matching tags. If match_all, idea must have ALL tags."""
    if not tag_names:
        return []

    placeholders = ",".join("?" * len(tag_names))
    if match_all:
        rows = conn.execute(
            f"""
            SELECT i.idea_id, i.idea_title, i.score, i.created_at,
                   GROUP_CONCAT(t.name) AS tag_names
            FROM ideas i
            JOIN idea_tags it ON i.idea_id = it.idea_id
            JOIN tags t ON it.tag_id = t.tag_id
            WHERE t.name IN ({placeholders})
            GROUP BY i.idea_id
            HAVING COUNT(DISTINCT t.tag_id) = ?
            ORDER BY i.score DESC, i.created_at DESC
            """,
            tag_names + [len(tag_names)],
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT i.idea_id, i.idea_title, i.score, i.created_at,
                   GROUP_CONCAT(DISTINCT t.name) AS tag_names
            FROM ideas i
            JOIN idea_tags it ON i.idea_id = it.idea_id
            JOIN tags t ON it.tag_id = t.tag_id
            WHERE t.name IN ({placeholders})
            GROUP BY i.idea_id
            ORDER BY i.score DESC, i.created_at DESC
            """,
            tag_names,
        ).fetchall()

    return [
        {
            "idea_id": int(r["idea_id"]),
            "idea_title": r["idea_title"],
            "score": float(r["score"]) if r["score"] else None,
            "created_at": int(r["created_at"]),
            "tag_names": r["tag_names"].split(",") if r["tag_names"] else [],
        }
        for r in rows
    ]


def add_tag_to_idea(
    conn: sqlite3.Connection,
    idea_id: int,
    tag_id: int,
    source: str = "tagger",
) -> None:
    """Add tag to idea. Ignores if already exists."""
    now = _utc_epoch_seconds()
    conn.execute(
        """
        INSERT OR IGNORE INTO idea_tags (idea_id, tag_id, source, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (idea_id, tag_id, source, now),
    )


def increment_tag_usage(conn: sqlite3.Connection, tag_id: int) -> None:
    """Increment usage_count for a tag."""
    conn.execute(
        "UPDATE tags SET usage_count = usage_count + 1 WHERE tag_id = ?",
        (tag_id,),
    )


def get_all_tags(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
) -> list[dict]:
    """Get all tags with usage counts. Optionally filter by category."""
    if category is not None:
        rows = conn.execute(
            """
            SELECT tag_id AS id, name, category, usage_count, created_at
            FROM tags
            WHERE category = ?
            ORDER BY usage_count DESC, name ASC
            """,
            (category,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT tag_id AS id, name, category, usage_count, created_at
            FROM tags
            ORDER BY usage_count DESC, name ASC
            """
        ).fetchall()

    return [
        {
            "id": int(r["id"]),
            "name": r["name"],
            "category": r["category"],
            "usage_count": int(r["usage_count"]),
            "created_at": int(r["created_at"]),
        }
        for r in rows
    ]


def get_or_create_embedding(
    conn: sqlite3.Connection,
    idea_id: int,
    idea: dict[str, Any],
) -> list[float]:
    from agents.embeddings import (
        generate_idea_embedding,
        embedding_to_bytes,
        bytes_to_embedding,
        get_model_version,
    )

    row = conn.execute(
        "SELECT embedding, model_version FROM idea_embeddings WHERE idea_id = ?",
        (idea_id,),
    ).fetchone()

    if row is not None:
        return bytes_to_embedding(row["embedding"])

    embedding = generate_idea_embedding(idea)
    model_version = get_model_version()
    now = _utc_epoch_seconds()

    conn.execute(
        """
        INSERT OR REPLACE INTO idea_embeddings (idea_id, embedding, model_version, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (idea_id, embedding_to_bytes(embedding), model_version, now),
    )

    return embedding


def get_embedding_for_idea(conn: sqlite3.Connection, idea_id: int) -> list[float] | None:
    from agents.embeddings import bytes_to_embedding

    row = conn.execute(
        "SELECT embedding FROM idea_embeddings WHERE idea_id = ?",
        (idea_id,),
    ).fetchone()

    if row is None:
        return None

    return bytes_to_embedding(row["embedding"])


def get_all_embeddings_for_ideas(
    conn: sqlite3.Connection,
    idea_ids: list[int],
) -> list[tuple[int, list[float]]]:
    from agents.embeddings import bytes_to_embedding

    if not idea_ids:
        return []

    placeholders = ",".join("?" * len(idea_ids))
    rows = conn.execute(
        f"SELECT idea_id, embedding FROM idea_embeddings WHERE idea_id IN ({placeholders})",
        idea_ids,
    ).fetchall()

    return [(int(r["idea_id"]), bytes_to_embedding(r["embedding"])) for r in rows]


def find_similar_ideas(
    conn: sqlite3.Connection,
    idea_id: int,
    threshold: float = 0.95,
) -> list[dict[str, Any]]:
    """
    Find ideas similar to given idea above threshold.

    Args:
        conn: Database connection
        idea_id: Source idea ID to find similar ideas for
        threshold: Minimum similarity score (default 0.95)

    Returns:
        List of dicts with idea_id and similarity, sorted by similarity descending
    """
    from agents.embeddings import compute_similarity, bytes_to_embedding

    source_emb = get_embedding_for_idea(conn, idea_id)
    if source_emb is None:
        return []

    # Get all other non-merged ideas with embeddings
    rows = conn.execute(
        """
        SELECT i.idea_id, ie.embedding
        FROM ideas i
        JOIN idea_embeddings ie ON i.idea_id = ie.idea_id
        WHERE i.idea_id != ?
          AND i.canonical_idea_id IS NULL
        """,
        (idea_id,),
    ).fetchall()

    similar: list[dict[str, Any]] = []
    for row in rows:
        target_emb = bytes_to_embedding(row["embedding"])
        similarity = compute_similarity(source_emb, target_emb)
        if similarity >= threshold:
            similar.append({
                "idea_id": int(row["idea_id"]),
                "similarity": similarity,
            })

    # Sort by similarity descending
    similar.sort(key=lambda x: x["similarity"], reverse=True)
    return similar


def merge_ideas(
    conn: sqlite3.Connection,
    source_id: int,
    target_id: int,
    similarity_score: float,
) -> None:
    """
    Record merge of source idea into target idea.

    Sets canonical_idea_id on source idea and records in idea_merges table.
    Does NOT delete the source idea.

    Args:
        conn: Database connection
        source_id: Idea ID to be merged (will have canonical_idea_id set)
        target_id: Idea ID to merge into (the canonical idea)
        similarity_score: Similarity score between the ideas
    """
    now = _utc_epoch_seconds()

    # Get fingerprints
    source_fp = conn.execute(
        "SELECT idea_fingerprint FROM ideas WHERE idea_id = ?",
        (source_id,),
    ).fetchone()

    target_fp = conn.execute(
        "SELECT idea_fingerprint FROM ideas WHERE idea_id = ?",
        (target_id,),
    ).fetchone()

    source_fingerprint = source_fp["idea_fingerprint"] if source_fp else None
    target_fingerprint = target_fp["idea_fingerprint"] if target_fp else None

    # Record in idea_merges
    conn.execute(
        """
        INSERT INTO idea_merges
        (source_idea_id, target_idea_id, source_fingerprint, target_fingerprint, similarity_score, merged_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_id, target_id, source_fingerprint, target_fingerprint, similarity_score, now),
    )

    # Mark source as merged
    conn.execute(
        "UPDATE ideas SET canonical_idea_id = ?, merged_at = ? WHERE idea_id = ?",
        (target_id, now, source_id),
    )


def merge_duplicate_ideas(
    db_path: str,
    threshold: float = 0.95,
) -> int:
    """
    Find and merge all duplicate ideas above threshold.

    For each non-merged idea, finds similar ideas and merges them.
    Lower ID becomes the canonical (target) idea.

    Args:
        db_path: Path to SQLite database
        threshold: Minimum similarity score for merging (default 0.95)

    Returns:
        Number of merges performed
    """
    conn = _connect(db_path)
    merge_count = 0

    try:
        # Get all non-merged ideas
        ideas = conn.execute(
            "SELECT idea_id FROM ideas WHERE canonical_idea_id IS NULL"
        ).fetchall()

        for row in ideas:
            idea_id = int(row["idea_id"])

            # Check if this idea was already merged during this batch
            current_canonical = conn.execute(
                "SELECT canonical_idea_id FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()

            if current_canonical["canonical_idea_id"] is not None:
                continue

            # Find similar ideas
            similar = find_similar_ideas(conn, idea_id, threshold)

            for sim in similar:
                target_id = int(sim["idea_id"])
                similarity = float(sim["similarity"])

                # Check if target is already merged
                target_canonical = conn.execute(
                    "SELECT canonical_idea_id FROM ideas WHERE idea_id = ?",
                    (target_id,),
                ).fetchone()

                if target_canonical["canonical_idea_id"] is not None:
                    continue

                # Merge: lower ID becomes canonical (target)
                if idea_id < target_id:
                    merge_ideas(conn, target_id, idea_id, similarity)
                else:
                    merge_ideas(conn, idea_id, target_id, similarity)

                merge_count += 1
                break  # Only merge with highest similarity match

        conn.commit()
    finally:
        conn.close()

    return merge_count


def store_ideas(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    ideas: list[dict[str, Any]],
) -> list[int]:
    """
    Persist evaluated ideas with tags and return idea IDs.
    Updates iterations.avg_score as the mean of idea scores.
    """
    conn = _connect(db_path)
    idea_ids: list[int] = []
    try:
        now = _utc_epoch_seconds()
        cur = conn.cursor()
        for idea in ideas:
            source_urls = idea.get("source_urls") or idea.get("sourceUrl") or []
            fingerprint = _idea_fingerprint(idea)

            # Merge sources for the same idea fingerprint so later iterations enrich context.
            existing = conn.execute(
                """
                SELECT source_urls, score, idea_id
                FROM ideas
                WHERE run_task_id=? AND idea_fingerprint=?
                """,
                (run_task_id, fingerprint),
            ).fetchone()

            if existing is None:
                merged_source_urls = list(dict.fromkeys(source_urls))
                existing_score = None
                existing_idea_id = None
            else:
                try:
                    prev_sources = json.loads(existing["source_urls"])
                    if not isinstance(prev_sources, list):
                        prev_sources = []
                except Exception:
                    prev_sources = []
                merged_source_urls = list(
                    dict.fromkeys(prev_sources + list(source_urls))
                )
                existing_score = existing["score"]
                existing_idea_id = existing["idea_id"]

            incoming_score = (
                float(idea["score"])
                if "score" in idea
                else float(idea.get("rating") or 0)
            )
            incoming_title = str(
                idea.get("idea_title") or idea.get("title") or "Untitled"
            )
            incoming_summary = idea.get("idea_summary") or idea.get("summary")
            incoming_payload = json.dumps(
                idea.get("idea_payload") or idea, ensure_ascii=False
            )
            incoming_score_breakdown = json.dumps(
                idea.get("score_breakdown") or {}, ensure_ascii=False
            )
            incoming_explain = (
                idea.get("evaluator_explain") or idea.get("explanation") or ""
            )

            cur.execute(
                """
                INSERT INTO ideas(
                  run_task_id, iteration_number, source_urls, idea_title, idea_summary,
                  idea_payload, idea_fingerprint, score, score_breakdown, evaluator_explain, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_task_id, idea_fingerprint) DO UPDATE SET
                  source_urls=excluded.source_urls,
                  score=CASE WHEN excluded.score > score THEN excluded.score ELSE score END,
                  score_breakdown=CASE WHEN excluded.score > score THEN excluded.score_breakdown ELSE score_breakdown END,
                  evaluator_explain=CASE WHEN excluded.score > score THEN excluded.evaluator_explain ELSE evaluator_explain END,
                  idea_title=CASE WHEN excluded.score > score THEN excluded.idea_title ELSE idea_title END,
                  idea_summary=CASE WHEN excluded.score > score THEN excluded.idea_summary ELSE idea_summary END,
                  idea_payload=CASE WHEN excluded.score > score THEN excluded.idea_payload ELSE idea_payload END,
                  iteration_number=CASE WHEN excluded.score > score THEN excluded.iteration_number ELSE iteration_number END
                """,
                (
                    run_task_id,
                    int(iteration_number),
                    json.dumps(merged_source_urls, ensure_ascii=False),
                    incoming_title,
                    incoming_summary,
                    incoming_payload,
                    fingerprint,
                    incoming_score,
                    incoming_score_breakdown,
                    incoming_explain,
                    now,
                ),
            )

            # Get the idea_id (either newly inserted or existing)
            if existing_idea_id is not None:
                idea_id = int(existing_idea_id)
            else:
                last_id = cur.lastrowid
                assert last_id is not None  # INSERT always sets lastrowid
                idea_id = last_id
            idea_ids.append(idea_id)

            tags = idea.get("tags", [])
            tag_categories = idea.get("tag_categories", {})

            if tags and isinstance(tags, list):
                for tag_name in tags:
                    if not isinstance(tag_name, str) or not tag_name.strip():
                        continue
                    tag_name = tag_name.strip()
                    category = tag_categories.get(tag_name, "industry")

                    tag_id = get_or_create_tag(conn, tag_name, category)

                    # Check if tag is already assigned to this idea
                    existing_assignment = conn.execute(
                        """
                        SELECT 1 FROM idea_tags WHERE idea_id=? AND tag_id=?
                        """,
                        (idea_id, tag_id),
                    ).fetchone()

                    # Link tag to idea (INSERT OR IGNORE handles duplicates)
                    add_tag_to_idea(conn, idea_id, tag_id, source="tagger")

                    # Only increment usage if this is a new assignment
                    if existing_assignment is None:
                        increment_tag_usage(conn, tag_id)

        # Update avg score for iteration.
        avg_row = conn.execute(
            """
            SELECT AVG(score) AS avg_score
            FROM ideas
            WHERE run_task_id=? AND iteration_number=?
            """,
            (run_task_id, int(iteration_number)),
        ).fetchone()
        avg_score = avg_row["avg_score"]
        conn.execute(
            """
            UPDATE iterations
            SET avg_score=?, status='active'
            WHERE run_task_id=? AND iteration_number=?
            """,
            (avg_score, run_task_id, int(iteration_number)),
        )
        conn.commit()
    finally:
        conn.close()

    return idea_ids


def get_top_ideas(db_path: str, run_task_id: str, limit: int) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
              idea_id,
              iteration_number,
              source_urls,
              idea_title,
              idea_summary,
              idea_payload,
              score,
              score_breakdown,
              evaluator_explain
            FROM ideas
            WHERE run_task_id=?
            ORDER BY score DESC, iteration_number ASC
            LIMIT ?
            """,
            (run_task_id, int(limit)),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "idea_id": int(r["idea_id"]),
                    "iteration_number": int(r["iteration_number"]),
                    "source_urls": json.loads(r["source_urls"]),
                    "idea_title": r["idea_title"],
                    "idea_summary": r["idea_summary"],
                    "idea_payload": json.loads(r["idea_payload"]),
                    "score": float(r["score"]),
                    "score_breakdown": json.loads(r["score_breakdown"]),
                    "evaluator_explain": r["evaluator_explain"],
                }
            )
        return out
    finally:
        conn.close()


def filter_new_urls(
    db_path: str,
    run_task_id: str,
    urls: list[str],
    retry_limit: int,
) -> dict[str, Any]:
    """
    Deduplicate URLs using the `sources` table.

    keep_urls:
    - not seen at all
    - OR previously failed with attempts < retry_limit
    skipped_urls:
    - previously queued or scraped
    - OR failed with attempts >= retry_limit
    """
    conn = _connect(db_path)
    try:
        normalized_rows: list[tuple[str, str, str]] = []
        for u in urls:
            nu = _normalize_url(u)
            if not nu:
                continue
            normalized_rows.append((u, nu, _url_fingerprint(nu)))

        if not normalized_rows:
            return {"keep_urls": [], "skipped_urls": []}

        fps = [fp for _, _, fp in normalized_rows]
        placeholders = ",".join(["?"] * len(fps))
        rows = conn.execute(
            f"""
            SELECT url_fingerprint, status, attempts
            FROM sources
            WHERE run_task_id=? AND url_fingerprint IN ({placeholders})
            """,
            [run_task_id] + fps,
        ).fetchall()
        seen: dict[str, sqlite3.Row] = {r["url_fingerprint"]: r for r in rows}

        keep_urls: list[str] = []
        skipped_urls: list[str] = []
        for original, _nu, fp in normalized_rows:
            r = seen.get(fp)
            if r is None:
                keep_urls.append(original)
            else:
                st = r["status"]
                attempts = int(r["attempts"])
                if st in ("queued", "scraped"):
                    skipped_urls.append(original)
                elif st == "failed" and attempts < int(retry_limit):
                    keep_urls.append(original)
                else:
                    skipped_urls.append(original)

        return {"keep_urls": keep_urls, "skipped_urls": skipped_urls}
    finally:
        conn.close()


def mark_sources_status(
    db_path: str,
    run_task_id: str,
    urls: list[str],
    status: str,
) -> None:
    conn = _connect(db_path)
    try:
        now = _utc_epoch_seconds()
        for u in urls:
            nu = _normalize_url(u)
            if not nu:
                continue
            fp = _url_fingerprint(nu)
            conn.execute(
                """
                INSERT INTO sources(run_task_id, url_normalized, url_fingerprint, category, status, attempts, last_attempt_at, created_at, updated_at)
                VALUES(?, ?, ?, NULL, ?, 1, ?, ?, ?)
                ON CONFLICT(run_task_id, url_fingerprint) DO UPDATE SET
                  status=excluded.status,
                  attempts=sources.attempts + 1,
                  last_attempt_at=excluded.last_attempt_at,
                  updated_at=excluded.updated_at
                """,
                (run_task_id, nu, fp, status, now, now, now),
            )
        conn.commit()
    finally:
        conn.close()


def parse_json_arg(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}\nInput was: {s[:2000]}") from e


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Idea-harvester SQLite DB helper")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_init = subparsers.add_parser("init", help="Initialize DB + schema")
    p_init.add_argument("--db", required=True)

    p_run = subparsers.add_parser("create-run", help="Create or update a run row")
    p_run.add_argument("--db", required=True)
    p_run.add_argument("--task-id", required=True)
    p_run.add_argument("--goal", required=True)
    p_run.add_argument("--model", default=None)
    p_run.add_argument("--max-iterations", type=int, default=5)
    p_run.add_argument("--plateau-window", type=int, default=2)
    p_run.add_argument("--min-improvement", type=float, default=0.0)

    p_iter = subparsers.add_parser(
        "ensure-iteration", help="Create iteration row if missing"
    )
    p_iter.add_argument("--db", required=True)
    p_iter.add_argument("--run-task-id", required=True)
    p_iter.add_argument("--iteration-number", type=int, required=True)

    p_enq = subparsers.add_parser("enqueue", help="Enqueue a queue message")
    p_enq.add_argument("--db", required=True)
    p_enq.add_argument("--run-task-id", required=True)
    p_enq.add_argument("--iteration-number", type=int, default=None)
    p_enq.add_argument("--from-agent", required=True)
    p_enq.add_argument("--to-agent", required=True)
    p_enq.add_argument("--stage", required=True)
    p_enq.add_argument("--payload", required=True, help="JSON string")
    p_enq.add_argument(
        "--available-at",
        type=int,
        default=None,
        help="epoch seconds; only dequeue when now >= available_at",
    )

    p_deq = subparsers.add_parser("dequeue", help="Dequeue one pending message")
    p_deq.add_argument("--db", required=True)
    p_deq.add_argument("--run-task-id", required=True)
    p_deq.add_argument("--to-agent", required=True)
    p_deq.add_argument("--iteration-number", type=int, default=None)
    p_deq.add_argument("--stage", default=None)
    p_deq.add_argument("--locked-by", default=None)

    p_done = subparsers.add_parser("mark-done", help="Mark message done")
    p_done.add_argument("--db", required=True)
    p_done.add_argument("--message-id", type=int, required=True)
    p_done.add_argument("--result", required=True, help="JSON string")

    p_fail = subparsers.add_parser("mark-failed", help="Mark message failed")
    p_fail.add_argument("--db", required=True)
    p_fail.add_argument("--message-id", type=int, required=True)
    p_fail.add_argument("--error", required=True)

    p_kv = subparsers.add_parser("upsert-kv", help="Upsert knowledge base kv")
    p_kv.add_argument("--db", required=True)
    p_kv.add_argument("--run-task-id", required=True)
    p_kv.add_argument("--key", required=True)
    p_kv.add_argument("--value", required=True, help="JSON string")

    p_out = subparsers.add_parser(
        "store-iteration-output", help="Store agent stage output in iteration row"
    )
    p_out.add_argument("--db", required=True)
    p_out.add_argument("--run-task-id", required=True)
    p_out.add_argument("--iteration-number", type=int, required=True)
    p_out.add_argument(
        "--stage", required=True, help="planner|researcher|scraper|evaluator|learner"
    )
    p_out.add_argument("--json", required=True, help="JSON string")

    p_ideas = subparsers.add_parser("store-ideas", help="Store evaluator's ideas array")
    p_ideas.add_argument("--db", required=True)
    p_ideas.add_argument("--run-task-id", required=True)
    p_ideas.add_argument("--iteration-number", type=int, required=True)
    p_ideas.add_argument("--ideas", required=True, help="JSON array string")

    p_top = subparsers.add_parser("top-ideas", help="List top N ideas")
    p_top.add_argument("--db", required=True)
    p_top.add_argument("--run-task-id", required=True)
    p_top.add_argument("--limit", type=int, default=10)

    p_scores = subparsers.add_parser(
        "iteration-scores", help="List iteration avg scores"
    )
    p_scores.add_argument("--db", required=True)
    p_scores.add_argument("--run-task-id", required=True)

    p_pending = subparsers.add_parser(
        "pending-messages", help="List pending queue messages (for resume safety)"
    )
    p_pending.add_argument("--db", required=True)
    p_pending.add_argument("--run-task-id", required=True)
    p_pending.add_argument("--to-agent", default=None)
    p_pending.add_argument("--stage", default=None)
    p_pending.add_argument("--iteration-number", type=int, default=None)

    p_now = subparsers.add_parser("now-epoch", help="Get current epoch seconds")
    p_now.add_argument(
        "--db",
        required=True,
        help="DB path (used only for schema initialization consistency)",
    )

    p_getkv = subparsers.add_parser("get-kv", help="Get a knowledge_kv value")
    p_getkv.add_argument("--db", required=True)
    p_getkv.add_argument("--run-task-id", required=True)
    p_getkv.add_argument("--key", required=True)

    p_filter = subparsers.add_parser(
        "filter-new-urls", help="Dedup URLs already seen for this run"
    )
    p_filter.add_argument("--db", required=True)
    p_filter.add_argument("--run-task-id", required=True)
    p_filter.add_argument(
        "--urls", required=True, help="JSON array string of URL strings"
    )
    p_filter.add_argument("--retry-limit", type=int, default=2)

    p_mark = subparsers.add_parser(
        "mark-sources-status",
        help="Mark URLs as queued/scraped/failed in sources table",
    )
    p_mark.add_argument("--db", required=True)
    p_mark.add_argument("--run-task-id", required=True)
    p_mark.add_argument(
        "--urls", required=True, help="JSON array string of URL strings"
    )
    p_mark.add_argument("--status", required=True, help="queued|scraped|failed")

    p_val = subparsers.add_parser(
        "store-iteration-validation", help="Store validation metric for an iteration"
    )
    p_val.add_argument("--db", required=True)
    p_val.add_argument("--run-task-id", required=True)
    p_val.add_argument("--iteration-number", type=int, required=True)
    p_val.add_argument("--score", type=float, required=True)
    p_val.add_argument("--explain", default="", help="validation explanation text")

    args = parser.parse_args(argv)

    if args.cmd == "init":
        init_db(args.db)
        print("OK")
        return 0

    # Initialize schema before other operations so skill can call any subcommand safely.
    init_db(args.db)

    if args.cmd == "create-run":
        create_run(
            db_path=args.db,
            task_id=args.task_id,
            goal=args.goal,
            model=args.model,
            max_iterations=args.max_iterations,
            plateau_window=args.plateau_window,
            min_improvement=args.min_improvement,
        )
        print(args.task_id)
        return 0

    if args.cmd == "ensure-iteration":
        ensure_iteration_row(args.db, args.run_task_id, args.iteration_number)
        print("OK")
        return 0

    if args.cmd == "enqueue":
        payload = parse_json_arg(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("--payload must be a JSON object")
        message_id = enqueue_message(
            db_path=args.db,
            run_task_id=args.run_task_id,
            iteration_number=args.iteration_number,
            from_agent=args.from_agent,
            to_agent=args.to_agent,
            stage=args.stage,
            payload=payload,
            available_at=args.available_at,
        )
        print(message_id)
        return 0

    if args.cmd == "dequeue":
        msg = dequeue_message(
            db_path=args.db,
            run_task_id=args.run_task_id,
            to_agent=args.to_agent,
            iteration_number=args.iteration_number,
            stage=args.stage,
            locked_by=args.locked_by,
        )
        if msg is None:
            print("null")
            return 0
        print(json.dumps(msg, ensure_ascii=False))
        return 0

    if args.cmd == "mark-done":
        result = parse_json_arg(args.result)
        if not isinstance(result, dict):
            raise ValueError("--result must be a JSON object")
        mark_done(args.db, args.message_id, result)
        print("OK")
        return 0

    if args.cmd == "mark-failed":
        mark_failed(args.db, args.message_id, args.error)
        print("OK")
        return 0

    if args.cmd == "upsert-kv":
        value = parse_json_arg(args.value)
        if not isinstance(value, dict):
            raise ValueError("--value must be a JSON object")
        upsert_knowledge_kv(args.db, args.run_task_id, args.key, value)
        print("OK")
        return 0

    if args.cmd == "store-iteration-output":
        json_output = parse_json_arg(args.json)
        if not isinstance(json_output, dict):
            raise ValueError("--json must be a JSON object")
        store_iteration_output(
            args.db, args.run_task_id, args.iteration_number, args.stage, json_output
        )
        print("OK")
        return 0

    if args.cmd == "store-ideas":
        ideas = parse_json_arg(args.ideas)
        if not isinstance(ideas, list):
            raise ValueError("--ideas must be a JSON array")
        store_ideas(args.db, args.run_task_id, args.iteration_number, ideas)  # type: ignore[arg-type]
        print("OK")
        return 0

    if args.cmd == "top-ideas":
        ideas = get_top_ideas(args.db, args.run_task_id, args.limit)
        print(json.dumps(ideas, ensure_ascii=False))
        return 0

    if args.cmd == "iteration-scores":
        scores = get_iteration_avg_scores(args.db, args.run_task_id)
        print(json.dumps(scores, ensure_ascii=False))
        return 0

    if args.cmd == "now-epoch":
        print(now_epoch_seconds())
        return 0

    if args.cmd == "get-kv":
        val = get_knowledge_kv(args.db, args.run_task_id, args.key)
        if val is None:
            print("null")
        else:
            print(json.dumps(val, ensure_ascii=False))
        return 0

    if args.cmd == "filter-new-urls":
        urls = parse_json_arg(args.urls)
        if not isinstance(urls, list) or not all(isinstance(x, str) for x in urls):
            raise ValueError("--urls must be a JSON array of strings")
        out = filter_new_urls(
            db_path=args.db,
            run_task_id=args.run_task_id,
            urls=urls,
            retry_limit=int(args.retry_limit),
        )
        print(json.dumps(out, ensure_ascii=False))
        return 0

    if args.cmd == "mark-sources-status":
        urls = parse_json_arg(args.urls)
        if not isinstance(urls, list) or not all(isinstance(x, str) for x in urls):
            raise ValueError("--urls must be a JSON array of strings")
        mark_sources_status(
            db_path=args.db,
            run_task_id=args.run_task_id,
            urls=urls,
            status=args.status,
        )
        print("OK")
        return 0

    if args.cmd == "store-iteration-validation":
        store_iteration_validation(
            db_path=args.db,
            run_task_id=args.run_task_id,
            iteration_number=args.iteration_number,
            validation_score=args.score,
            validation_explain=args.explain,
        )
        print("OK")
        return 0

    if args.cmd == "pending-messages":
        msgs = list_pending_messages(
            db_path=args.db,
            run_task_id=args.run_task_id,
            to_agent=args.to_agent,
            stage=args.stage,
            iteration_number=args.iteration_number,
        )
        print(json.dumps(msgs, ensure_ascii=False))
        return 0

    raise RuntimeError(f"Unhandled command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
