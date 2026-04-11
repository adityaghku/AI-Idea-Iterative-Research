from types import SimpleNamespace

import pytest

from agents.librarian import LibrarianAgent


def _idea(idea_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=idea_id,
        title=title,
        problem=f"{title} problem",
        target_user=f"{title} user",
        solution=f"{title} solution",
        is_active=True,
        is_duplicate=False,
        merged_into_id=None,
    )


@pytest.mark.asyncio
async def test_apply_decisions_uses_pair_index_for_multi_pair_merge():
    agent = LibrarianAgent()
    refresh_calls: list[int] = []

    async def _refresh(_session, idea):
        refresh_calls.append(idea.id)

    agent._refresh_embedding = _refresh  # type: ignore[method-assign]

    idea_a = _idea(1, "A")
    idea_b = _idea(2, "B")
    idea_c = _idea(3, "C")
    pairs = [
        {"pair_index": 0, "source": idea_a, "target": idea_b, "similarity": 0.93},
        {"pair_index": 1, "source": idea_b, "target": idea_c, "similarity": 0.91},
    ]
    decisions = [
        {
            "pair_index": 1,
            "action": "merge",
            "keep_idea_id": 3,
            "merged_title": "C merged",
            "merged_problem": "C merged problem",
            "merged_target_user": "C merged user",
            "merged_solution": "C merged solution",
        }
    ]

    merged, dropped = await agent._apply_decisions(session=None, decisions=decisions, potential_pairs=pairs)

    assert merged == 1
    assert dropped == 0
    assert idea_b.is_active is False
    assert idea_b.merged_into_id == 3
    assert idea_c.title == "C merged"
    assert refresh_calls == [3]


@pytest.mark.asyncio
async def test_apply_decisions_drop_handles_target_side_drop_id():
    agent = LibrarianAgent()
    async def _refresh(_session, _idea):
        return None

    agent._refresh_embedding = _refresh  # type: ignore[method-assign]

    idea_a = _idea(10, "A")
    idea_b = _idea(11, "B")
    pairs = [{"pair_index": 0, "source": idea_a, "target": idea_b, "similarity": 0.88}]
    decisions = [{"pair_index": 0, "action": "drop", "keep_idea_id": 10, "drop_idea_id": 11}]

    merged, dropped = await agent._apply_decisions(session=None, decisions=decisions, potential_pairs=pairs)

    assert merged == 0
    assert dropped == 1
    assert idea_b.is_active is False
    assert idea_b.is_duplicate is True
    assert idea_b.merged_into_id == 10


@pytest.mark.asyncio
async def test_apply_decisions_skips_invalid_decisions():
    agent = LibrarianAgent()
    refresh_calls: list[int] = []

    async def _refresh(_session, idea):
        refresh_calls.append(idea.id)

    agent._refresh_embedding = _refresh  # type: ignore[method-assign]

    idea_a = _idea(21, "A")
    idea_b = _idea(22, "B")
    pairs = [{"pair_index": 0, "source": idea_a, "target": idea_b, "similarity": 0.95}]
    decisions = [
        {"pair_index": 4, "action": "merge", "keep_idea_id": 21},
        {"pair_index": 0, "action": "drop", "keep_idea_id": 22, "drop_idea_id": 99},
    ]

    merged, dropped = await agent._apply_decisions(session=None, decisions=decisions, potential_pairs=pairs)

    assert merged == 0
    assert dropped == 0
    assert idea_a.is_active is True
    assert idea_b.is_active is True
    assert refresh_calls == []
