"""Mock LLM response fixtures for evaluator testing."""
import pytest


@pytest.fixture
def extract_single_candidate():
    """Phase-1 extract output matching the scored valid_idea_response."""
    return [
        {
            "idea_title": "AI-Powered Code Review Assistant",
            "idea_summary": "AI reviews code and suggests improvements using ML.",
            "supporting_quotes": [
                "code changes",
                "machine learning",
            ],
        }
    ]


@pytest.fixture
def extract_two_candidates():
    """Phase-1 extract output matching multiple_ideas_response."""
    return [
        {
            "idea_title": "AI Meeting Summarizer",
            "idea_summary": "Summaries and action items from video calls.",
            "supporting_quotes": ["meeting"],
        },
        {
            "idea_title": "Personalized Nutrition AI",
            "idea_summary": "Meal planning from health goals.",
            "supporting_quotes": ["nutrition"],
        },
    ]


@pytest.fixture
def extract_twenty_candidates():
    """Phase-1 extract: 20 minimal candidates for limit tests."""
    return [
        {
            "idea_title": f"Idea {i}",
            "idea_summary": f"Summary {i}",
            "supporting_quotes": [f"quote{i}"],
        }
        for i in range(20)
    ]


@pytest.fixture
def valid_idea_response():
    """Return a valid single idea LLM response."""
    return [
        {
            "idea_title": "AI-Powered Code Review Assistant",
            "idea_summary": "An AI tool that reviews code changes and suggests improvements based on best practices and security guidelines.",
            "detailed_scores": {
                "problem_clarity": 85,
                "ai_advantage": 90,
                "market_timing": 75,
                "solo_founder_feasibility": 80,
                "distribution_path": 70,
                "monetization_clarity": 85,
                "defensibility": 65,
                "technical_feasibility": 90
            },
            "total_score": 82,
            "verdict": "Strong",
            "strengths": [
                "Clear problem statement - code reviews are tedious",
                "Strong AI advantage over manual reviews",
                "Growing developer market"
            ],
            "risks": [
                "Competition from GitHub Copilot",
                "Need high accuracy to be trusted"
            ],
            "advice": "Focus on specific languages first, then expand",
            "red_flags": [],
            "citations": [
                "code changes",
                "machine learning",
            ],
        }
    ]


@pytest.fixture
def multiple_ideas_response():
    """Return multiple ideas from LLM response."""
    return [
        {
            "idea_title": "AI Meeting Summarizer",
            "idea_summary": "Automatically generates meeting summaries and action items from video calls.",
            "detailed_scores": {
                "problem_clarity": 90,
                "ai_advantage": 85,
                "market_timing": 80,
                "solo_founder_feasibility": 75,
                "distribution_path": 65,
                "monetization_clarity": 70,
                "defensibility": 55,
                "technical_feasibility": 85
            },
            "total_score": 78,
            "verdict": "Strong",
            "strengths": ["High demand", "Clear value proposition"],
            "risks": ["Privacy concerns", "Integration complexity"],
            "advice": "Start with specific platforms like Zoom",
            "red_flags": [],
            "citations": ["video calls", "machine learning"],
        },
        {
            "idea_title": "Personalized Nutrition AI",
            "idea_summary": "AI-powered meal planning based on health goals and dietary restrictions.",
            "detailed_scores": {
                "problem_clarity": 75,
                "ai_advantage": 70,
                "market_timing": 70,
                "solo_founder_feasibility": 60,
                "distribution_path": 55,
                "monetization_clarity": 65,
                "defensibility": 45,
                "technical_feasibility": 75
            },
            "total_score": 65,
            "verdict": "Promising",
            "strengths": ["Large health market", "Recurring revenue potential"],
            "risks": ["Regulatory complexity", "High competition"],
            "advice": "Partner with nutritionists for credibility",
            "red_flags": ["Healthcare regulations"]
        }
    ]


@pytest.fixture
def low_score_idea_response():
    """Return a low-scoring idea to test filtering."""
    return [
        {
            "idea_title": "Generic AI Chatbot",
            "idea_summary": "Yet another AI chatbot for customer service.",
            "detailed_scores": {
                "problem_clarity": 40,
                "ai_advantage": 30,
                "market_timing": 35,
                "solo_founder_feasibility": 50,
                "distribution_path": 30,
                "monetization_clarity": 35,
                "defensibility": 20,
                "technical_feasibility": 60
            },
            "total_score": 38,
            "verdict": "Weak",
            "strengths": ["Simple to build"],
            "risks": [
                "Oversaturated market",
                "No differentiation",
                "Hard to monetize"
            ],
            "advice": "Find a specific niche or unique angle",
            "red_flags": ["Oversaturated market", "No moat"]
        }
    ]


@pytest.fixture
def invalid_idea_response():
    """Return an invalid/malformed LLM response."""
    return {
        "error": "Invalid response format",
        "message": "Expected list of ideas"
    }


@pytest.fixture
def empty_idea_response():
    """Return an empty list response."""
    return []


@pytest.fixture
def extract_partial_candidate():
    """Extract phase for partial_score_idea_response test."""
    return [
        {
            "idea_title": "Incomplete Scoring Test",
            "idea_summary": "Test idea with missing scores.",
            "supporting_quotes": ["test"],
        }
    ]


@pytest.fixture
def partial_score_idea_response():
    """Return an idea with missing scores to test error handling."""
    return [
        {
            "idea_title": "Incomplete Scoring Test",
            "idea_summary": "Test idea with missing scores.",
            "detailed_scores": {
                "problem_clarity": 70,
                # Missing ai_advantage
                "market_timing": 60,
                # Missing solo_founder_feasibility
                "distribution_path": 50,
                # Missing monetization_clarity
                "defensibility": 40,
                "technical_feasibility": 80
            },
            "total_score": 55,
            "verdict": "Marginal",
            "strengths": ["Some good aspects"],
            "risks": ["Incomplete data"],
            "advice": "Get more complete data",
            "red_flags": []
        }
    ]
