"""Tests for store_ideas() tag handling in idea_harvester_db.py."""
import sys
import tempfile

sys.path.insert(0, ".")

import sqlite3

from db.idea_harvester_db import (
    init_db,
    store_ideas,
    get_tags_by_idea,
)


def _make_db() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    init_db(db_path)
    return db_path


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_run(db_path: str, task_id: str = "test-run") -> None:
    conn = _get_conn(db_path)
    conn.execute(
        """
        INSERT INTO runs (task_id, goal, created_at, updated_at)
        VALUES (?, ?, 0, 0)
        """,
        (task_id, "Test goal"),
    )
    conn.execute(
        """
        INSERT INTO iterations (run_task_id, iteration_number, status, started_at)
        VALUES (?, 1, 'active', 0)
        """,
        (task_id,),
    )
    conn.commit()
    conn.close()


def test_store_ideas_with_tags() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "AI Medical Diagnosis",
            "idea_summary": "AI-powered medical diagnosis tool",
            "score": 0.85,
            "tags": ["Healthcare", "AI"],
            "tag_categories": {"Healthcare": "industry", "AI": "technology"},
        }
    ]

    idea_ids = store_ideas(db_path, "test-run", 1, ideas)
    assert len(idea_ids) == 1

    conn = _get_conn(db_path)
    tags = get_tags_by_idea(conn, idea_ids[0])
    conn.close()
    tag_names = {t["name"] for t in tags}
    assert "Healthcare" in tag_names
    assert "AI" in tag_names


def test_store_ideas_missing_tags_field() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
        }
    ]

    idea_ids = store_ideas(db_path, "test-run", 1, ideas)
    assert len(idea_ids) == 1

    conn = _get_conn(db_path)
    tags = get_tags_by_idea(conn, idea_ids[0])
    conn.close()
    assert tags == []


def test_store_ideas_empty_tags_list() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": [],
        }
    ]

    idea_ids = store_ideas(db_path, "test-run", 1, ideas)
    assert len(idea_ids) == 1

    conn = _get_conn(db_path)
    tags = get_tags_by_idea(conn, idea_ids[0])
    conn.close()
    assert tags == []


def test_store_ideas_default_category() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": ["SaaS"],
        }
    ]

    store_ideas(db_path, "test-run", 1, ideas)

    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT category FROM tags WHERE name = ?", ("SaaS",)
    ).fetchone()
    conn.close()
    assert row["category"] == "industry"


def test_store_ideas_usage_count_incremented() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": ["SaaS"],
        }
    ]

    store_ideas(db_path, "test-run", 1, ideas)

    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT usage_count FROM tags WHERE name = ?", ("SaaS",)
    ).fetchone()
    conn.close()
    assert row["usage_count"] == 1


def test_store_ideas_duplicate_tag_not_duplicated() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": ["SaaS"],
        }
    ]

    store_ideas(db_path, "test-run", 1, ideas)
    store_ideas(db_path, "test-run", 1, ideas)

    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT COUNT(*) as cnt FROM idea_tags WHERE idea_id = 1"
    ).fetchone()
    conn.close()
    assert rows["cnt"] == 1


def test_store_ideas_usage_count_not_incremented_on_duplicate() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": ["SaaS"],
        }
    ]

    store_ideas(db_path, "test-run", 1, ideas)
    store_ideas(db_path, "test-run", 1, ideas)

    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT usage_count FROM tags WHERE name = ?", ("SaaS",)
    ).fetchone()
    conn.close()
    assert row["usage_count"] == 1


def test_store_ideas_multiple_ideas_same_tag() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Idea 1",
            "idea_summary": "First idea",
            "score": 0.8,
            "tags": ["SaaS"],
        },
        {
            "idea_title": "Idea 2",
            "idea_summary": "Second idea",
            "score": 0.7,
            "tags": ["SaaS"],
        },
    ]

    idea_ids = store_ideas(db_path, "test-run", 1, ideas)
    assert len(idea_ids) == 2

    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT usage_count FROM tags WHERE name = ?", ("SaaS",)
    ).fetchone()
    conn.close()
    assert row["usage_count"] == 2


def test_store_ideas_returns_idea_ids() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Idea 1",
            "idea_summary": "First idea",
            "score": 0.8,
        },
        {
            "idea_title": "Idea 2",
            "idea_summary": "Second idea",
            "score": 0.7,
        },
    ]

    idea_ids = store_ideas(db_path, "test-run", 1, ideas)
    assert len(idea_ids) == 2
    assert all(isinstance(i, int) for i in idea_ids)
    assert idea_ids[0] != idea_ids[1]


def test_store_ideas_invalid_tag_skipped() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": ["Valid", "", "  ", None, 123],
        }
    ]

    idea_ids = store_ideas(db_path, "test-run", 1, ideas)

    conn = _get_conn(db_path)
    tags = get_tags_by_idea(conn, idea_ids[0])
    conn.close()
    tag_names = {t["name"] for t in tags}
    assert "Valid" in tag_names
    assert "" not in tag_names


def test_store_ideas_tag_categories_partial() -> None:
    db_path = _make_db()
    _create_run(db_path)

    ideas = [
        {
            "idea_title": "Test Idea",
            "idea_summary": "A test idea",
            "score": 0.75,
            "tags": ["SaaS", "Healthcare"],
            "tag_categories": {"SaaS": "business_model"},
        }
    ]

    store_ideas(db_path, "test-run", 1, ideas)

    conn = _get_conn(db_path)
    saas_row = conn.execute(
        "SELECT category FROM tags WHERE name = ?", ("SaaS",)
    ).fetchone()
    healthcare_row = conn.execute(
        "SELECT category FROM tags WHERE name = ?", ("Healthcare",)
    ).fetchone()
    conn.close()
    assert saas_row["category"] == "business_model"
    assert healthcare_row["category"] == "industry"


if __name__ == "__main__":
    tests = [
        test_store_ideas_with_tags,
        test_store_ideas_missing_tags_field,
        test_store_ideas_empty_tags_list,
        test_store_ideas_default_category,
        test_store_ideas_usage_count_incremented,
        test_store_ideas_duplicate_tag_not_duplicated,
        test_store_ideas_usage_count_not_incremented_on_duplicate,
        test_store_ideas_multiple_ideas_same_tag,
        test_store_ideas_returns_idea_ids,
        test_store_ideas_invalid_tag_skipped,
        test_store_ideas_tag_categories_partial,
    ]
    for t in tests:
        try:
            t()
            print(f"✓ {t.__name__}")
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            raise
    print(f"\nAll {len(tests)} tests passed!")