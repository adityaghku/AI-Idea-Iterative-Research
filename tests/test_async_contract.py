from pathlib import Path


def test_llm_client_has_no_asyncio_run_wrappers():
    llm_client = Path(__file__).resolve().parents[1] / "utils" / "llm_client.py"
    source = llm_client.read_text(encoding="utf-8")
    assert "asyncio.run(" not in source


def test_llm_response_guard_detects_non_json_prefix_and_plan_mode():
    from utils.llm_client import (
        _looks_like_forbidden_worker_behavior,
        _looks_like_plan_mode,
        _response_starts_with_json,
    )

    assert _response_starts_with_json('{"ok": true}')
    assert _response_starts_with_json("\n  [1, 2, 3]")
    assert not _response_starts_with_json("Here is the JSON: {\"ok\": true}")

    assert _looks_like_plan_mode("Let me think this through first.")
    assert _looks_like_plan_mode("Here's a quick plan:\n1. Analyze\n2. Execute")
    assert not _looks_like_plan_mode('{"score": 72, "comments": "Looks feasible"}')
    assert _looks_like_forbidden_worker_behavior(
        "Some of what we're working on might be easier to explain if I can show it to you in a web browser."
    )
    assert _looks_like_forbidden_worker_behavior(
        "I'll inspect the codebase and read a few files before answering."
    )
    assert not _looks_like_forbidden_worker_behavior('{"score": 72, "comments": "Looks feasible"}')


def test_worker_contract_applies_tool_policy():
    from utils.llm_client import _build_worker_contract

    web_only = _build_worker_contract("web_only")
    no_tools = _build_worker_contract("no_tools")

    assert "use only the `websearch` and `webfetch` tools" in web_only
    assert "Do not read local files" in web_only
    assert "Do not use any tools." in no_tools


def test_librarian_validator_requires_one_decision_per_pair():
    from utils.agent_validators import validate_librarian_output

    ok, reason = validate_librarian_output(
        [{"pair_index": 0, "action": "keep_separate", "confidence": 0.8, "keep_idea_id": 1}],
        pair_count=2,
    )

    assert not ok
    assert "pair_count" in reason


def test_synthesizer_validator_rejects_invalid_signal_index():
    from utils.agent_validators import validate_synthesizer_output

    ok, reason = validate_synthesizer_output(
        [
            {
                "title": "Idea",
                "problem": "Problem",
                "target_user": "User",
                "solution": "Solution",
                "monetization_hypothesis": "Users pay",
                "payer": "User",
                "pricing_model": "subscription",
                "wedge": "Small workflow",
                "why_now": "Timely",
                "supporting_signal_indices": [3],
            }
        ],
        signal_count=2,
    )

    assert not ok
    assert "supporting_signal_indices" in reason
