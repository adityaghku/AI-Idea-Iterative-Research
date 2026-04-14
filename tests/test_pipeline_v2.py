from types import SimpleNamespace

import pytest

from agents.analyser import AnalyserAgent
from agents.critic import CriticAgent
from agents.deep_dive import DeepDiveAgent
from agents.synthesizer import SynthesizerAgent
from db import Signal


class FakeSession:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    async def commit(self):
        return None

    async def scalar(self, *_args, **_kwargs):
        return None


@pytest.mark.asyncio
async def test_synthesizer_persists_business_fields(monkeypatch):
    seen_prompts: list[str] = []

    async def fake_llm(*args, **kwargs):
        seen_prompts.append(args[0])
        return [
            {
                "title": "DeskFlow",
                "problem": "Teams lose time rewriting meeting notes into tasks.",
                "target_user": "Small agency operators",
                "solution": "Desktop app that turns meeting recordings into tracked follow-ups.",
                "monetization_hypothesis": "Agencies pay monthly to reduce admin time.",
                "payer": "Agency owner",
                "pricing_model": "subscription",
                "wedge": "Post-client-call follow-up workflow",
                "why_now": "Teams are overloaded with meetings and AI summaries are newly expected.",
                "supporting_signal_indices": [0],
            }
        ]

    monkeypatch.setattr("agents.synthesizer.async_llm_complete_json", fake_llm)

    session = FakeSession()
    signals = [
        Signal(
            content="Freelancers complain about missed follow-ups after calls",
            source_url=None,
            signal_type="complaint",
            signal_metadata={},
        )
    ]

    ideas = await SynthesizerAgent(
        portfolio_guidance="Avoid low-urgency ideas. Prefer teams already paying for workarounds."
    ).run(session, signals)

    assert ideas[0].monetization_hypothesis == "Agencies pay monthly to reduce admin time."
    assert ideas[0].payer == "Agency owner"
    assert ideas[0].pricing_model == "subscription"
    assert ideas[0].wedge == "Post-client-call follow-up workflow"
    assert ideas[0].why_now == "Teams are overloaded with meetings and AI summaries are newly expected."
    assert "Avoid low-urgency ideas" in seen_prompts[0]


@pytest.mark.asyncio
async def test_analyser_persists_structured_subscores(monkeypatch):
    seen_prompts: list[str] = []

    async def fake_llm(*args, **kwargs):
        seen_prompts.append(args[0])
        return {
            "score": 78,
            "subscores": {
                "demand": 81,
                "gtm": 70,
                "build_risk": 52,
                "retention": 76,
                "monetization": 84,
                "validation": 68,
            },
            "monetization_potential": "high",
            "complexity": "medium",
            "tags": ["b2b", "desktop"],
            "assumptions": ["Agency owners will connect recordings."],
            "comments": "Solid paid workflow if onboarding friction stays low.",
        }

    monkeypatch.setattr("agents.analyser.async_llm_complete_json", fake_llm)

    session = FakeSession()
    idea = SimpleNamespace(
        id=123,
        title="DeskFlow",
        problem="Ops teams lose notes.",
        target_user="Agency operators",
        solution="Turn calls into tasks.",
        monetization_hypothesis="Agencies pay to remove admin work.",
        payer="Agency owner",
        pricing_model="subscription",
        wedge="Meeting follow-up automation",
        why_now="AI summaries changed buyer expectations.",
        status="new",
    )

    analyses = await AnalyserAgent().run(session, [idea])

    assert analyses[0].demand_score == 81
    assert analyses[0].gtm_score == 70
    assert analyses[0].build_risk_score == 52
    assert analyses[0].retention_score == 76
    assert analyses[0].monetization_score == 84
    assert analyses[0].validation_score == 68
    assert "Monetization Hypothesis: Agencies pay to remove admin work." in seen_prompts[0]


@pytest.mark.asyncio
async def test_critic_persists_monetization_and_validation_blockers(monkeypatch):
    async def fake_llm(*args, **kwargs):
        return {
            "saturation_issues": ["MEDIUM: Several adjacent tools exist | Mitigation: narrow to agencies"],
            "distribution_blockers": ["HIGH: Hard to acquire cold | Mitigation: partner with agencies"],
            "technical_blockers": ["LOW: Standard transcription stack | Mitigation: use managed APIs"],
            "monetization_blockers": ["HIGH: Buyer may see this as a nice-to-have | Mitigation: prove time saved"],
            "validation_blockers": ["MEDIUM: Unknown if owners trust auto-created tasks | Mitigation: run concierge pilot"],
            "additional_concerns": "Trust and workflow fit matter more than raw AI quality.",
        }

    monkeypatch.setattr("agents.critic.async_llm_complete_json", fake_llm)

    session = FakeSession()
    enrichment = SimpleNamespace(
        additional_notes="Extra notes",
        competitor_details=[{"name": "Foo", "summary": "Bar", "url": None}],
        monetization_strategies=["Subscription"],
        evidence_snippets=["Agencies complain about follow-up admin."],
        risks=["Users may not trust automation."],
        go_to_market_hypotheses=["Sell through agency communities."],
    )
    idea = SimpleNamespace(
        id=77,
        title="DeskFlow",
        problem="Ops teams lose notes.",
        target_user="Agency operators",
        solution="Turn calls into tasks.",
        enrichment=enrichment,
        status="enriched",
    )

    critiques = await CriticAgent().run(session, [idea])

    assert critiques[0].monetization_blockers == [
        "HIGH: Buyer may see this as a nice-to-have | Mitigation: prove time saved"
    ]
    assert critiques[0].validation_blockers == [
        "MEDIUM: Unknown if owners trust auto-created tasks | Mitigation: run concierge pilot"
    ]


def test_portfolio_guidance_uses_only_recurring_crossout_patterns():
    from agents.portfolio import summarize_crossout_feedback

    feedback = [
        {"reason_code": "too_crowded", "reason_text": "Too many incumbents already."},
        {"reason_code": "too_crowded", "reason_text": "Feels crowded and hard to differentiate."},
        {"reason_code": "platform_risk", "reason_text": "Depends on Apple allowing private APIs."},
    ]

    summary = summarize_crossout_feedback(feedback, min_count=2)

    assert summary["recurring_patterns"] == [
        {
            "reason_code": "too_crowded",
            "count": 2,
            "examples": [
                "Too many incumbents already.",
                "Feels crowded and hard to differentiate.",
            ],
        }
    ]


def test_portfolio_filters_to_latest_feedback_for_current_crossed_ideas():
    from agents.portfolio import select_active_crossout_feedback

    filtered = select_active_crossout_feedback(
        [
            {"idea_id": 1, "reason_code": "too_crowded", "reason_text": "older", "is_crossed_out": True, "created_at": 1},
            {"idea_id": 1, "reason_code": "bad_distribution", "reason_text": "latest", "is_crossed_out": True, "created_at": 2},
            {"idea_id": 2, "reason_code": "platform_risk", "reason_text": "ignored", "is_crossed_out": False, "created_at": 3},
        ]
    )

    assert filtered == [
        {
            "idea_id": 1,
            "reason_code": "bad_distribution",
            "reason_text": "latest",
            "is_crossed_out": True,
            "created_at": 2,
        }
    ]


def test_scout_extracts_optional_business_metadata():
    from agents.scout import _signal_metadata_from_llm

    meta = _signal_metadata_from_llm(
        {
            "payment_context": "Teams already pay for Zapier workarounds.",
            "current_spend_or_workaround": "Manual admin plus $40/mo tools",
            "urgency": "high",
            "score": 0.72,
            "ignored": "nope",
        }
    )

    assert meta == {
        "payment_context": "Teams already pay for Zapier workarounds.",
        "current_spend_or_workaround": "Manual admin plus $40/mo tools",
        "urgency": "high",
        "score": 0.72,
    }


@pytest.mark.asyncio
async def test_deep_dive_persists_pricing_and_validation_fields(monkeypatch):
    async def fake_llm(*args, **kwargs):
        return {
            "competitors": [
                {"name": "Comp A", "summary": "Helps with follow-ups.", "url": "https://a.example"},
                {"name": "Comp B", "summary": "Tracks admin workflows.", "url": "https://b.example"},
            ],
            "app_landscape": {"ios_apps": 2},
            "pricing_landscape": {"subscription_monthly_usd": [19, 49]},
            "monetization_strategies": ["Subscription"],
            "paid_alternatives": ["Comp A $19/mo"],
            "tech_stack": ["Python"],
            "feasibility": "medium",
            "confidence": 0.8,
            "evidence_snippets": ["Agencies complain about follow-up admin.", "Users already pay for patchwork tools."],
            "risks": ["Users may stay with existing tools."],
            "go_to_market_hypotheses": ["Sell via agency operator communities."],
            "validation_tests": ["Run concierge pilot with 5 agencies."],
            "switching_cost_notes": "Switching cost is moderate because workflows are sticky.",
            "additional_notes": "Promising if setup friction is low.",
        }

    monkeypatch.setattr("agents.deep_dive.async_llm_complete_json", fake_llm)

    session = FakeSession()
    idea = SimpleNamespace(
        id=5,
        title="DeskFlow",
        problem="Ops teams lose notes.",
        target_user="Agency operators",
        solution="Turn calls into tasks.",
        status="analysed",
    )

    enrichments = await DeepDiveAgent().run(session, [idea])

    assert enrichments[0].pricing_landscape == {"subscription_monthly_usd": [19, 49]}
    assert enrichments[0].paid_alternatives == ["Comp A $19/mo"]
    assert enrichments[0].validation_tests == ["Run concierge pilot with 5 agencies."]
    assert enrichments[0].switching_cost_notes == "Switching cost is moderate because workflows are sticky."


def test_deep_dive_candidate_selection_prefers_feedback_gap_then_weighted_scores():
    from main import select_deep_dive_candidates

    ideas = [
        SimpleNamespace(
            id=1,
            title="Unknown Monetization",
            analysis=SimpleNamespace(
                score=65,
                monetization_potential="unknown",
                monetization_score=40,
                validation_score=45,
                demand_score=70,
                gtm_score=55,
            ),
        ),
        SimpleNamespace(
            id=2,
            title="High Monetization",
            analysis=SimpleNamespace(
                score=78,
                monetization_potential="high",
                monetization_score=92,
                validation_score=80,
                demand_score=84,
                gtm_score=76,
            ),
        ),
        SimpleNamespace(
            id=3,
            title="Medium Option",
            analysis=SimpleNamespace(
                score=81,
                monetization_potential="medium",
                monetization_score=70,
                validation_score=65,
                demand_score=82,
                gtm_score=60,
            ),
        ),
    ]

    selected = select_deep_dive_candidates(ideas, max_candidates=2)

    assert [idea.id for idea in selected] == [1, 2]


def test_embedding_text_includes_business_fields_when_present():
    from utils.embeddings import idea_to_text

    text = idea_to_text(
        "DeskFlow",
        "Ops teams lose notes.",
        "Agency operators",
        "Turn calls into tasks.",
        monetization_hypothesis="Agencies pay monthly to reduce admin time.",
        payer="Agency owner",
        pricing_model="subscription",
        wedge="Meeting follow-up workflow",
        why_now="AI summaries changed expectations.",
    )

    assert "Agencies pay monthly to reduce admin time." in text
    assert "Agency owner" in text
    assert "Meeting follow-up workflow" in text
