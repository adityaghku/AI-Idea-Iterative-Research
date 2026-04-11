import pytest

from agents.db import Signal
from agents.synthesizer import SynthesizerAgent


class FakeSession:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_synthesizer_uses_supporting_signal_indices(monkeypatch):
    async def fake_llm(*args, **kwargs):
        return [
            {
                "title": "Idea One",
                "problem": "P1",
                "target_user": "U1",
                "solution": "S1",
                "supporting_signal_indices": [1],
            },
            {
                "title": "Idea Two",
                "problem": "P2",
                "target_user": "U2",
                "solution": "S2",
                "supporting_signal_indices": [0, 2],
            },
        ]

    monkeypatch.setattr("agents.synthesizer.async_llm_complete_json", fake_llm)

    signals = [
        Signal(content="s0", source_url=None, signal_type="problem_statement", metadata={}),
        Signal(content="s1", source_url=None, signal_type="complaint", metadata={}),
        Signal(content="s2", source_url=None, signal_type="unmet_need", metadata={}),
    ]
    session = FakeSession()
    ideas = await SynthesizerAgent().run(session, signals)

    assert len(ideas) == 2
    assert [s.content for s in ideas[0].signals] == ["s1"]
    assert [s.content for s in ideas[1].signals] == ["s0", "s2"]
