"""Tag CRUD tests for idea_harvester_db.py."""
import sys
import sqlite3

sys.path.insert(0, ".")

from db.idea_harvester_db import (
    create_tag,
    get_or_create_tag,
    get_tags_by_idea,
    get_ideas_by_tags,
    add_tag_to_idea,
    increment_tag_usage,
    get_all_tags,
)


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL,
            category TEXT NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX idx_tags_category ON tags(category);
        CREATE TABLE ideas (
            idea_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_task_id TEXT NOT NULL,
            iteration_number INTEGER NOT NULL,
            idea_title TEXT,
            score REAL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE idea_tags (
            idea_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'tagger',
            created_at INTEGER NOT NULL,
            PRIMARY KEY (idea_id, tag_id),
            FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
        );
        CREATE INDEX idx_idea_tags_tag_id ON idea_tags(tag_id);
        CREATE INDEX idx_idea_tags_idea_id ON idea_tags(idea_id);
    """)
    return conn


def test_create_tag_returns_id() -> None:
    conn = _make_db()
    tag_id = create_tag(conn, "SaaS", "business_model")
    assert isinstance(tag_id, int) and tag_id > 0


def test_create_tag_duplicate_raises() -> None:
    conn = _make_db()
    create_tag(conn, "SaaS", "business_model")
    try:
        create_tag(conn, "SaaS", "business_model")
        raise AssertionError("Expected IntegrityError")
    except sqlite3.IntegrityError:
        pass


def test_create_tag_sets_slug() -> None:
    conn = _make_db()
    create_tag(conn, "Machine Learning", "technology")
    row = conn.execute("SELECT slug FROM tags WHERE name = ?", ("Machine Learning",)).fetchone()
    assert row["slug"] == "machine-learning"


def test_get_or_create_existing() -> None:
    conn = _make_db()
    existing_id = create_tag(conn, "SaaS", "business_model")
    found_id = get_or_create_tag(conn, "SaaS", "business_model")
    assert found_id == existing_id


def test_get_or_create_new() -> None:
    conn = _make_db()
    tag_id = get_or_create_tag(conn, "B2B", "business_model")
    assert tag_id > 0
    row = conn.execute("SELECT name FROM tags WHERE tag_id = ?", (tag_id,)).fetchone()
    assert row["name"] == "B2B"


def test_get_tags_by_idea_empty() -> None:
    conn = _make_db()
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, 0)")
    tags = get_tags_by_idea(conn, 1)
    assert tags == []


def test_get_tags_by_idea_returns_tags() -> None:
    conn = _make_db()
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, 0)")
    tag_id = create_tag(conn, "SaaS", "business_model")
    add_tag_to_idea(conn, 1, tag_id, "manual")
    tags = get_tags_by_idea(conn, 1)
    assert len(tags) == 1
    assert tags[0]["name"] == "SaaS"
    assert tags[0]["source"] == "manual"


def test_add_tag_to_idea() -> None:
    conn = _make_db()
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, 0)")
    tag_id = create_tag(conn, "SaaS", "business_model")
    add_tag_to_idea(conn, 1, tag_id)
    rows = conn.execute("SELECT * FROM idea_tags WHERE idea_id = 1").fetchall()
    assert len(rows) == 1


def test_add_tag_to_idea_ignores_duplicate() -> None:
    conn = _make_db()
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, created_at) VALUES (1, 'task1', 1, 0)")
    tag_id = create_tag(conn, "SaaS", "business_model")
    add_tag_to_idea(conn, 1, tag_id)
    add_tag_to_idea(conn, 1, tag_id)
    rows = conn.execute("SELECT * FROM idea_tags WHERE idea_id = 1").fetchall()
    assert len(rows) == 1


def test_increment_tag_usage() -> None:
    conn = _make_db()
    tag_id = create_tag(conn, "SaaS", "business_model")
    initial = conn.execute("SELECT usage_count FROM tags WHERE tag_id = ?", (tag_id,)).fetchone()
    assert initial["usage_count"] == 0
    increment_tag_usage(conn, tag_id)
    updated = conn.execute("SELECT usage_count FROM tags WHERE tag_id = ?", (tag_id,)).fetchone()
    assert updated["usage_count"] == 1


def test_get_all_tags_empty() -> None:
    conn = _make_db()
    tags = get_all_tags(conn)
    assert tags == []


def test_get_all_tags_with_data() -> None:
    conn = _make_db()
    create_tag(conn, "SaaS", "business_model")
    create_tag(conn, "B2B", "business_model")
    tags = get_all_tags(conn)
    assert len(tags) == 2
    assert all("name" in t and "category" in t and "usage_count" in t for t in tags)


def test_get_all_tags_filtered_by_category() -> None:
    conn = _make_db()
    create_tag(conn, "SaaS", "business_model")
    create_tag(conn, "Python", "technology")
    tags = get_all_tags(conn, category="business_model")
    assert len(tags) == 1
    assert tags[0]["name"] == "SaaS"


def test_get_ideas_by_tags_match_any() -> None:
    conn = _make_db()
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, idea_title, score, created_at) VALUES (1, 'task1', 1, 'Idea A', 80, 0)")
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, idea_title, score, created_at) VALUES (2, 'task1', 1, 'Idea B', 60, 0)")
    tag1 = create_tag(conn, "SaaS", "business_model")
    tag2 = create_tag(conn, "B2B", "business_model")
    add_tag_to_idea(conn, 1, tag1)
    add_tag_to_idea(conn, 2, tag2)
    ideas = get_ideas_by_tags(conn, ["SaaS", "B2B"], match_all=False)
    assert len(ideas) == 2


def test_get_ideas_by_tags_match_all() -> None:
    conn = _make_db()
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, idea_title, score, created_at) VALUES (1, 'task1', 1, 'Idea A', 80, 0)")
    conn.execute("INSERT INTO ideas (idea_id, run_task_id, iteration_number, idea_title, score, created_at) VALUES (2, 'task1', 1, 'Idea B', 60, 0)")
    tag1 = create_tag(conn, "SaaS", "business_model")
    tag2 = create_tag(conn, "B2B", "business_model")
    add_tag_to_idea(conn, 1, tag1)
    add_tag_to_idea(conn, 1, tag2)
    add_tag_to_idea(conn, 2, tag1)
    ideas = get_ideas_by_tags(conn, ["SaaS", "B2B"], match_all=True)
    assert len(ideas) == 1
    assert ideas[0]["idea_title"] == "Idea A"


def test_get_ideas_by_tags_empty_list() -> None:
    conn = _make_db()
    ideas = get_ideas_by_tags(conn, [], match_all=False)
    assert ideas == []


if __name__ == "__main__":
    tests = [
        test_create_tag_returns_id,
        test_create_tag_duplicate_raises,
        test_create_tag_sets_slug,
        test_get_or_create_existing,
        test_get_or_create_new,
        test_get_tags_by_idea_empty,
        test_get_tags_by_idea_returns_tags,
        test_add_tag_to_idea,
        test_add_tag_to_idea_ignores_duplicate,
        test_increment_tag_usage,
        test_get_all_tags_empty,
        test_get_all_tags_with_data,
        test_get_all_tags_filtered_by_category,
        test_get_ideas_by_tags_match_any,
        test_get_ideas_by_tags_match_all,
        test_get_ideas_by_tags_empty_list,
    ]
    for t in tests:
        try:
            t()
            print(f"✓ {t.__name__}")
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            raise
    print(f"\nAll {len(tests)} tests passed!")
