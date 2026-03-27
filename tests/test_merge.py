"""Merge function tests for idea_harvester_db.py."""
import sys
import sqlite3
import tempfile
import os

sys.path.insert(0, ".")

from db.idea_harvester_db import (
    find_similar_ideas,
    merge_ideas,
    merge_duplicate_ideas,
    get_embedding_for_idea,
    init_db,
    _connect,
)


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE ideas (
            idea_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_task_id TEXT NOT NULL,
            iteration_number INTEGER NOT NULL,
            source_urls TEXT NOT NULL DEFAULT '[]',
            idea_title TEXT NOT NULL,
            idea_summary TEXT,
            idea_payload TEXT NOT NULL DEFAULT '{}',
            idea_fingerprint TEXT,
            score REAL NOT NULL DEFAULT 0,
            score_breakdown TEXT,
            evaluator_explain TEXT,
            created_at INTEGER NOT NULL DEFAULT 0,
            canonical_idea_id INTEGER,
            merged_at INTEGER,
            FOREIGN KEY (canonical_idea_id) REFERENCES ideas(idea_id)
        );
        CREATE TABLE idea_embeddings (
            idea_id INTEGER PRIMARY KEY,
            embedding BLOB NOT NULL,
            model_version TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
        );
        CREATE TABLE idea_merges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_idea_id INTEGER NOT NULL,
            target_idea_id INTEGER NOT NULL,
            source_fingerprint TEXT,
            target_fingerprint TEXT,
            similarity_score REAL,
            merged_at INTEGER NOT NULL,
            FOREIGN KEY (source_idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
            FOREIGN KEY (target_idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
        );
        CREATE INDEX idx_idea_merges_target ON idea_merges(target_idea_id);
    """)
    return conn


def _make_temp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    conn = _connect(path)
    conn.execute(
        """
        INSERT INTO runs (task_id, goal, created_at, updated_at)
        VALUES ('test-run', 'test goal', 0, 0)
        """
    )
    conn.commit()
    conn.close()
    return path


def _insert_idea(
    conn: sqlite3.Connection,
    idea_id: int,
    title: str,
    fingerprint: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ideas (idea_id, run_task_id, iteration_number, idea_title, idea_fingerprint, source_urls, idea_payload, score, created_at)
        VALUES (?, 'test-run', 1, ?, ?, '[]', '{}', 0, 0)
        """,
        (idea_id, title, fingerprint),
    )


def _insert_embedding(
    conn: sqlite3.Connection,
    idea_id: int,
    embedding: list[float],
) -> None:
    import struct
    data = struct.pack(f"{len(embedding)}f", *embedding)
    conn.execute(
        """
        INSERT INTO idea_embeddings (idea_id, embedding, model_version, created_at)
        VALUES (?, ?, 'test-model', 0)
        """,
        (idea_id, data),
    )


def test_find_similar_ideas_no_embedding() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A")
    similar = find_similar_ideas(conn, 1, threshold=0.95)
    assert similar == []


def test_find_similar_ideas_single_idea() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A")
    _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
    similar = find_similar_ideas(conn, 1, threshold=0.95)
    assert similar == []


def test_find_similar_ideas_below_threshold() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A")
    _insert_idea(conn, 2, "Idea B")
    _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
    _insert_embedding(conn, 2, [0.0, 1.0, 0.0])
    similar = find_similar_ideas(conn, 1, threshold=0.95)
    assert similar == []


def test_find_similar_ideas_above_threshold() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A")
    _insert_idea(conn, 2, "Idea B")
    _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
    _insert_embedding(conn, 2, [0.99, 0.01, 0.0])
    similar = find_similar_ideas(conn, 1, threshold=0.95)
    assert len(similar) == 1
    assert similar[0]["idea_id"] == 2
    assert similar[0]["similarity"] > 0.95


def test_find_similar_ideas_sorted_by_similarity() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A")
    _insert_idea(conn, 2, "Idea B")
    _insert_idea(conn, 3, "Idea C")
    _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
    _insert_embedding(conn, 2, [0.99, 0.01, 0.0])
    _insert_embedding(conn, 3, [0.98, 0.02, 0.0])
    similar = find_similar_ideas(conn, 1, threshold=0.95)
    assert len(similar) == 2
    assert similar[0]["similarity"] >= similar[1]["similarity"]


def test_find_similar_ideas_excludes_merged() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A")
    _insert_idea(conn, 2, "Idea B")
    _insert_idea(conn, 3, "Idea C")
    conn.execute("UPDATE ideas SET canonical_idea_id = 1 WHERE idea_id = 2")
    _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
    _insert_embedding(conn, 2, [0.99, 0.01, 0.0])
    _insert_embedding(conn, 3, [0.98, 0.02, 0.0])
    similar = find_similar_ideas(conn, 1, threshold=0.95)
    assert len(similar) == 1
    assert similar[0]["idea_id"] == 3


def test_merge_ideas_sets_canonical() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A", fingerprint="fp-a")
    _insert_idea(conn, 2, "Idea B", fingerprint="fp-b")
    merge_ideas(conn, source_id=2, target_id=1, similarity_score=0.98)
    row = conn.execute(
        "SELECT canonical_idea_id, merged_at FROM ideas WHERE idea_id = 2"
    ).fetchone()
    assert row["canonical_idea_id"] == 1
    assert row["merged_at"] is not None


def test_merge_ideas_records_merge() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A", fingerprint="fp-a")
    _insert_idea(conn, 2, "Idea B", fingerprint="fp-b")
    merge_ideas(conn, source_id=2, target_id=1, similarity_score=0.98)
    row = conn.execute(
        """
        SELECT source_idea_id, target_idea_id, source_fingerprint, target_fingerprint, similarity_score
        FROM idea_merges WHERE source_idea_id = 2
        """
    ).fetchone()
    assert row["source_idea_id"] == 2
    assert row["target_idea_id"] == 1
    assert row["source_fingerprint"] == "fp-b"
    assert row["target_fingerprint"] == "fp-a"
    assert row["similarity_score"] == 0.98


def test_merge_ideas_preserves_target() -> None:
    conn = _make_db()
    _insert_idea(conn, 1, "Idea A", fingerprint="fp-a")
    _insert_idea(conn, 2, "Idea B", fingerprint="fp-b")
    merge_ideas(conn, source_id=2, target_id=1, similarity_score=0.98)
    row = conn.execute(
        "SELECT canonical_idea_id FROM ideas WHERE idea_id = 1"
    ).fetchone()
    assert row["canonical_idea_id"] is None


def test_merge_duplicate_ideas_no_matches() -> None:
    db_path = _make_temp_db()
    try:
        conn = _connect(db_path)
        _insert_idea(conn, 1, "Idea A")
        _insert_idea(conn, 2, "Idea B")
        _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
        _insert_embedding(conn, 2, [0.0, 1.0, 0.0])
        conn.commit()
        conn.close()
        count = merge_duplicate_ideas(db_path, threshold=0.95)
        assert count == 0
    finally:
        os.unlink(db_path)


def test_merge_duplicate_ideas_merges_similar() -> None:
    db_path = _make_temp_db()
    try:
        conn = _connect(db_path)
        _insert_idea(conn, 1, "Idea A")
        _insert_idea(conn, 2, "Idea B")
        _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
        _insert_embedding(conn, 2, [0.99, 0.01, 0.0])
        conn.commit()
        conn.close()
        count = merge_duplicate_ideas(db_path, threshold=0.95)
        assert count == 1
        conn = _connect(db_path)
        row = conn.execute(
            "SELECT canonical_idea_id FROM ideas WHERE idea_id = 2"
        ).fetchone()
        assert row["canonical_idea_id"] == 1
        conn.close()
    finally:
        os.unlink(db_path)


def test_merge_duplicate_ideas_lower_id_becomes_canonical() -> None:
    db_path = _make_temp_db()
    try:
        conn = _connect(db_path)
        _insert_idea(conn, 5, "Idea A")
        _insert_idea(conn, 3, "Idea B")
        _insert_embedding(conn, 5, [1.0, 0.0, 0.0])
        _insert_embedding(conn, 3, [0.99, 0.01, 0.0])
        conn.commit()
        conn.close()
        count = merge_duplicate_ideas(db_path, threshold=0.95)
        assert count == 1
        conn = _connect(db_path)
        row = conn.execute(
            "SELECT canonical_idea_id FROM ideas WHERE idea_id = 5"
        ).fetchone()
        assert row["canonical_idea_id"] == 3
        conn.close()
    finally:
        os.unlink(db_path)


def test_merge_duplicate_ideas_skips_already_merged() -> None:
    db_path = _make_temp_db()
    try:
        conn = _connect(db_path)
        _insert_idea(conn, 1, "Idea A")
        _insert_idea(conn, 2, "Idea B")
        _insert_idea(conn, 3, "Idea C")
        conn.execute("UPDATE ideas SET canonical_idea_id = 1 WHERE idea_id = 2")
        _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
        _insert_embedding(conn, 2, [0.99, 0.01, 0.0])
        _insert_embedding(conn, 3, [0.98, 0.02, 0.0])
        conn.commit()
        conn.close()
        count = merge_duplicate_ideas(db_path, threshold=0.95)
        assert count == 1
        conn = _connect(db_path)
        row = conn.execute(
            "SELECT canonical_idea_id FROM ideas WHERE idea_id = 3"
        ).fetchone()
        assert row["canonical_idea_id"] == 1
        conn.close()
    finally:
        os.unlink(db_path)


def test_merge_duplicate_ideas_multiple_pairs() -> None:
    db_path = _make_temp_db()
    try:
        conn = _connect(db_path)
        _insert_idea(conn, 1, "Idea A")
        _insert_idea(conn, 2, "Idea B")
        _insert_idea(conn, 3, "Idea C")
        _insert_idea(conn, 4, "Idea D")
        _insert_embedding(conn, 1, [1.0, 0.0, 0.0])
        _insert_embedding(conn, 2, [0.99, 0.01, 0.0])
        _insert_embedding(conn, 3, [0.0, 1.0, 0.0])
        _insert_embedding(conn, 4, [0.0, 0.99, 0.01])
        conn.commit()
        conn.close()
        count = merge_duplicate_ideas(db_path, threshold=0.95)
        assert count == 2
        conn = _connect(db_path)
        row1 = conn.execute(
            "SELECT canonical_idea_id FROM ideas WHERE idea_id = 2"
        ).fetchone()
        row2 = conn.execute(
            "SELECT canonical_idea_id FROM ideas WHERE idea_id = 4"
        ).fetchone()
        assert row1["canonical_idea_id"] == 1
        assert row2["canonical_idea_id"] == 3
        conn.close()
    finally:
        os.unlink(db_path)


def test_merge_duplicate_ideas_no_embeddings() -> None:
    db_path = _make_temp_db()
    try:
        conn = _connect(db_path)
        _insert_idea(conn, 1, "Idea A")
        _insert_idea(conn, 2, "Idea B")
        conn.commit()
        conn.close()
        count = merge_duplicate_ideas(db_path, threshold=0.95)
        assert count == 0
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    tests = [
        test_find_similar_ideas_no_embedding,
        test_find_similar_ideas_single_idea,
        test_find_similar_ideas_below_threshold,
        test_find_similar_ideas_above_threshold,
        test_find_similar_ideas_sorted_by_similarity,
        test_find_similar_ideas_excludes_merged,
        test_merge_ideas_sets_canonical,
        test_merge_ideas_records_merge,
        test_merge_ideas_preserves_target,
        test_merge_duplicate_ideas_no_matches,
        test_merge_duplicate_ideas_merges_similar,
        test_merge_duplicate_ideas_lower_id_becomes_canonical,
        test_merge_duplicate_ideas_skips_already_merged,
        test_merge_duplicate_ideas_multiple_pairs,
        test_merge_duplicate_ideas_no_embeddings,
    ]
    for t in tests:
        try:
            t()
            print(f"✓ {t.__name__}")
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            raise
    print(f"\nAll {len(tests)} tests passed!")