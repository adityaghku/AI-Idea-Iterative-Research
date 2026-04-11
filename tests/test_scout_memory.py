from types import SimpleNamespace

from agents.scout import _build_memory_context, _normalize_memory_key


def test_normalize_memory_key_stabilizes_equivalent_text():
    a = _normalize_memory_key("Users complain about long WAIT times!!!")
    b = _normalize_memory_key("users complain about long wait times")
    assert a == b


def test_build_memory_context_is_compact_and_informative():
    signals = [
        SimpleNamespace(
            signal_type="complaint",
            content="Users hate repeated onboarding questions",
            source_url="https://example.com/a",
        ),
        SimpleNamespace(
            signal_type="unmet_need",
            content="Need a quick way to triage customer support tickets",
            source_url=None,
        ),
    ]
    context = _build_memory_context(signals, max_items=1)

    assert "Existing scout memory" in context
    assert "Signal counts by type" in context
    assert "repeated onboarding questions" not in context
    assert "triage customer support tickets" in context
