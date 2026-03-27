"""Embedding tests for semantic similarity detection."""
import sys
import sqlite3
import struct

sys.path.insert(0, ".")


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE ideas (
            idea_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_task_id TEXT NOT NULL,
            iteration_number INTEGER NOT NULL,
            idea_title TEXT,
            idea_summary TEXT,
            score REAL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE idea_embeddings (
            idea_id INTEGER PRIMARY KEY,
            embedding BLOB NOT NULL,
            model_version TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
        );
        CREATE INDEX idx_idea_embeddings_idea_id ON idea_embeddings(idea_id);
    """)
    return conn


def test_embedding_to_bytes_roundtrip() -> None:
    from agents.embeddings import embedding_to_bytes, bytes_to_embedding

    original = [0.1, 0.2, 0.3, -0.4, 0.5]
    data = embedding_to_bytes(original)
    recovered = bytes_to_embedding(data)

    assert len(recovered) == len(original)
    for o, r in zip(original, recovered):
        assert abs(o - r) < 1e-6


def test_bytes_to_embedding_correct_size() -> None:
    from agents.embeddings import bytes_to_embedding

    embedding = [0.5] * 384
    data = struct.pack(f"{len(embedding)}f", *embedding)
    recovered = bytes_to_embedding(data)

    assert len(recovered) == 384
    assert all(abs(v - 0.5) < 1e-6 for v in recovered)


def test_compute_similarity_identical() -> None:
    from agents.embeddings import compute_similarity

    emb = [0.1, 0.2, 0.3, 0.4]
    sim = compute_similarity(emb, emb)
    assert abs(sim - 1.0) < 1e-6


def test_compute_similarity_orthogonal() -> None:
    from agents.embeddings import compute_similarity

    emb1 = [1.0, 0.0, 0.0]
    emb2 = [0.0, 1.0, 0.0]
    sim = compute_similarity(emb1, emb2)
    assert abs(sim) < 1e-6


def test_compute_similarity_opposite() -> None:
    from agents.embeddings import compute_similarity

    emb1 = [1.0, 0.0, 0.0]
    emb2 = [-1.0, 0.0, 0.0]
    sim = compute_similarity(emb1, emb2)
    assert abs(sim - (-1.0)) < 1e-6


def test_compute_similarity_zero_vector() -> None:
    from agents.embeddings import compute_similarity

    emb1 = [0.0, 0.0, 0.0]
    emb2 = [1.0, 2.0, 3.0]
    sim = compute_similarity(emb1, emb2)
    assert sim == 0.0


def test_find_similar_ideas_threshold() -> None:
    from agents.embeddings import find_similar_ideas

    query = [1.0, 0.0, 0.0]
    candidates = [
        (1, [0.99, 0.1, 0.0]),
        (2, [0.5, 0.5, 0.5]),
        (3, [-0.9, 0.1, 0.0]),
    ]

    results = find_similar_ideas(query, candidates, threshold=0.8)
    assert len(results) == 1
    assert results[0][0] == 1


def test_find_similar_ideas_sorted_descending() -> None:
    from agents.embeddings import find_similar_ideas

    query = [1.0, 0.0, 0.0]
    candidates = [
        (1, [0.8, 0.6, 0.0]),
        (2, [0.95, 0.3, 0.0]),
        (3, [0.6, 0.8, 0.0]),
    ]

    results = find_similar_ideas(query, candidates, threshold=0.5)
    assert len(results) == 3
    assert results[0][0] == 2
    assert results[1][0] == 1
    assert results[2][0] == 3


def test_find_similar_ideas_empty_candidates() -> None:
    from agents.embeddings import find_similar_ideas

    query = [1.0, 0.0, 0.0]
    results = find_similar_ideas(query, [], threshold=0.8)
    assert results == []


def test_get_model_version() -> None:
    from agents.embeddings import get_model_version

    version = get_model_version()
    assert version == "all-MiniLM-L6-v2"


def test_get_or_create_embedding_returns_cached() -> None:
    from db.idea_harvester_db import get_or_create_embedding, _utc_epoch_seconds
    from agents.embeddings import embedding_to_bytes

    conn = _make_db()
    now = _utc_epoch_seconds()
    conn.execute(
        "INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, ?)",
        (now,),
    )

    cached_embedding = [0.5] * 384
    conn.execute(
        "INSERT INTO idea_embeddings (idea_id, embedding, model_version, created_at) VALUES (?, ?, ?, ?)",
        (1, embedding_to_bytes(cached_embedding), "all-MiniLM-L6-v2", now),
    )

    idea = {"idea_title": "Test", "idea_summary": "Summary"}
    result = get_or_create_embedding(conn, 1, idea)

    assert result == cached_embedding


def test_get_embedding_for_idea_existing() -> None:
    from db.idea_harvester_db import get_embedding_for_idea
    from agents.embeddings import embedding_to_bytes

    conn = _make_db()
    now = 1000
    conn.execute(
        "INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, ?)",
        (now,),
    )

    embedding = [0.25] * 384
    conn.execute(
        "INSERT INTO idea_embeddings (idea_id, embedding, model_version, created_at) VALUES (?, ?, ?, ?)",
        (1, embedding_to_bytes(embedding), "all-MiniLM-L6-v2", now),
    )

    result = get_embedding_for_idea(conn, 1)
    assert result is not None
    assert len(result) == 384
    assert all(abs(v - 0.25) < 1e-6 for v in result)


def test_get_embedding_for_idea_missing() -> None:
    from db.idea_harvester_db import get_embedding_for_idea

    conn = _make_db()
    result = get_embedding_for_idea(conn, 999)
    assert result is None


def test_get_all_embeddings_for_ideas() -> None:
    from db.idea_harvester_db import get_all_embeddings_for_ideas
    from agents.embeddings import embedding_to_bytes

    conn = _make_db()
    now = 1000

    for i in range(1, 4):
        conn.execute(
            "INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (?, 'task1', 1, ?)",
            (i, now),
        )
        embedding = [float(i) * 0.1] * 384
        conn.execute(
            "INSERT INTO idea_embeddings (idea_id, embedding, model_version, created_at) VALUES (?, ?, ?, ?)",
            (i, embedding_to_bytes(embedding), "all-MiniLM-L6-v2", now),
        )

    results = get_all_embeddings_for_ideas(conn, [1, 2, 3])
    assert len(results) == 3

    idea_ids = [r[0] for r in results]
    assert 1 in idea_ids
    assert 2 in idea_ids
    assert 3 in idea_ids


def test_get_all_embeddings_for_ideas_empty_list() -> None:
    from db.idea_harvester_db import get_all_embeddings_for_ideas

    conn = _make_db()
    results = get_all_embeddings_for_ideas(conn, [])
    assert results == []


def test_get_all_embeddings_for_ideas_partial() -> None:
    from db.idea_harvester_db import get_all_embeddings_for_ideas
    from agents.embeddings import embedding_to_bytes

    conn = _make_db()
    now = 1000

    conn.execute(
        "INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, ?)",
        (now,),
    )
    embedding = [0.5] * 384
    conn.execute(
        "INSERT INTO idea_embeddings (idea_id, embedding, model_version, created_at) VALUES (?, ?, ?, ?)",
        (1, embedding_to_bytes(embedding), "all-MiniLM-L6-v2", now),
    )

    results = get_all_embeddings_for_ideas(conn, [1, 2, 3])
    assert len(results) == 1
    assert results[0][0] == 1


if __name__ == "__main__":
    tests = [
        test_embedding_to_bytes_roundtrip,
        test_bytes_to_embedding_correct_size,
        test_compute_similarity_identical,
        test_compute_similarity_orthogonal,
        test_compute_similarity_opposite,
        test_compute_similarity_zero_vector,
        test_find_similar_ideas_threshold,
        test_find_similar_ideas_sorted_descending,
        test_find_similar_ideas_empty_candidates,
        test_get_model_version,
        test_get_or_create_embedding_returns_cached,
        test_get_embedding_for_idea_existing,
        test_get_embedding_for_idea_missing,
        test_get_all_embeddings_for_ideas,
        test_get_all_embeddings_for_ideas_empty_list,
        test_get_all_embeddings_for_ideas_partial,
    ]
    for t in tests:
        try:
            t()
            print(f"✓ {t.__name__}")
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            raise
    print(f"\nAll {len(tests)} tests passed!")