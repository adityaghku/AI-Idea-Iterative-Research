"""Unit tests for TaggerAgent."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from typing import Any

from agents.tagger import TaggerAgent, DEFAULT_TAG_CATEGORIES
from agents.config import TaggerInput, TaggerOutput


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def sample_ideas() -> list[dict[str, Any]]:
    """Return sample ideas for testing."""
    return [
        {
            "idea_title": "AI-Powered Code Review Assistant",
            "idea_summary": "An AI tool that reviews code changes and suggests improvements.",
            "score": 82,
        },
        {
            "idea_title": "Healthcare Diagnosis AI",
            "idea_summary": "AI-powered medical diagnosis for primary care physicians.",
            "score": 75,
        },
        {
            "idea_title": "E-commerce Recommendation Engine",
            "idea_summary": "Personalized product recommendations for online stores.",
            "score": 68,
        },
    ]


@pytest.fixture
def valid_tag_response() -> list[dict[str, Any]]:
    """Return a valid LLM tagging response."""
    return [
        {
            "idea_title": "AI-Powered Code Review Assistant",
            "tags": ["SaaS", "LLM", "Solo-founder friendly"],
            "tag_categories": {
                "SaaS": "business_model",
                "LLM": "technology",
                "Solo-founder friendly": "founder_fit",
            },
        },
        {
            "idea_title": "Healthcare Diagnosis AI",
            "tags": ["Healthcare", "Computer Vision", "Enterprise"],
            "tag_categories": {
                "Healthcare": "industry",
                "Computer Vision": "technology",
                "Enterprise": "business_model",
            },
        },
        {
            "idea_title": "E-commerce Recommendation Engine",
            "tags": ["E-commerce", "Recommendation", "SaaS"],
            "tag_categories": {
                "E-commerce": "industry",
                "Recommendation": "technology",
                "SaaS": "business_model",
            },
        },
    ]


@pytest.fixture
def empty_ideas() -> list[dict[str, Any]]:
    """Return empty ideas list."""
    return []


# ==============================================================================
# Test execute() with Valid Input
# ==============================================================================

class TestTaggerExecute:
    """Tests for execute() method."""

    @patch("agents.tagger.async_llm_complete_json")
    def test_execute_single_batch(
        self,
        mock_llm_json: AsyncMock,
        sample_ideas: list[dict[str, Any]],
        valid_tag_response: list[dict[str, Any]],
    ) -> None:
        """Test execute() processes ideas in a single batch."""
        mock_llm_json.return_value = valid_tag_response

        tagger = TaggerAgent(batch_size=10)
        input_data = TaggerInput(ideas=sample_ideas, categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert len(output.tagged_ideas) == 3
        assert "SaaS" in output.tag_counts
        assert output.tag_counts["SaaS"] == 2
        mock_llm_json.assert_called_once()

    @patch("agents.tagger.async_llm_complete_json")
    def test_execute_multiple_batches(
        self,
        mock_llm_json: AsyncMock,
    ) -> None:
        """Test execute() processes ideas in multiple batches."""
        ideas = [
            {"idea_title": f"Idea {i}", "idea_summary": f"Summary {i}", "score": 70}
            for i in range(25)
        ]

        batch_responses = [
            [
                {
                    "idea_title": f"Idea {i}",
                    "tags": ["SaaS", "LLM"],
                    "tag_categories": {"SaaS": "business_model", "LLM": "technology"},
                }
                for i in range(start, min(start + 10, 25))
            ]
            for start in range(0, 25, 10)
        ]

        mock_llm_json.side_effect = batch_responses

        tagger = TaggerAgent(batch_size=10)
        input_data = TaggerInput(ideas=ideas, categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert len(output.tagged_ideas) == 25
        assert mock_llm_json.call_count == 3

    @patch("agents.tagger.async_llm_complete_json")
    def test_execute_empty_ideas(
        self,
        mock_llm_json: AsyncMock,
        empty_ideas: list[dict[str, Any]],
    ) -> None:
        """Test execute() handles empty ideas list."""
        tagger = TaggerAgent()
        input_data = TaggerInput(ideas=empty_ideas, categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert output.tagged_ideas == []
        assert output.tag_counts == {}
        mock_llm_json.assert_not_called()

    @patch("agents.tagger.async_llm_complete_json")
    def test_execute_custom_categories(
        self,
        mock_llm_json: AsyncMock,
        sample_ideas: list[dict[str, Any]],
    ) -> None:
        """Test execute() uses custom categories when provided."""
        mock_llm_json.return_value = [
            {
                "idea_title": "AI-Powered Code Review Assistant",
                "tags": ["CustomTag"],
                "tag_categories": {"CustomTag": "custom_category"},
            }
        ]

        tagger = TaggerAgent(batch_size=10)
        input_data = TaggerInput(
            ideas=sample_ideas[:1],
            categories=["custom_category", "another_category"],
        )
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert len(output.tagged_ideas) == 1
        call_args = mock_llm_json.call_args
        prompt = call_args[1]["prompt"]
        assert "CUSTOM_CATEGORY" in prompt


# ==============================================================================
# Test Tag Validation and Cleaning
# ==============================================================================

class TestTagValidation:
    """Tests for tag validation and cleaning."""

    @patch("agents.tagger.async_llm_complete_json")
    def test_validate_tags_filters_invalid(
        self,
        mock_llm_json: AsyncMock,
        sample_ideas: list[dict[str, Any]],
    ) -> None:
        """Test _tag_batch validates and filters invalid tags."""
        mock_llm_json.return_value = [
            {
                "idea_title": "AI-Powered Code Review Assistant",
                "tags": ["SaaS", "InvalidTag", "LLM"],
                "tag_categories": {
                    "SaaS": "business_model",
                    "InvalidTag": "unknown_category",
                    "LLM": "technology",
                },
            }
        ]

        tagger = TaggerAgent()
        input_data = TaggerInput(ideas=sample_ideas[:1], categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert len(output.tagged_ideas) == 1
        tags = output.tagged_ideas[0]["tags"]
        assert "InvalidTag" not in tags
        assert "SaaS" in tags
        assert "LLM" in tags

    @patch("agents.tagger.async_llm_complete_json")
    def test_non_list_response(
        self,
        mock_llm_json: AsyncMock,
        sample_ideas: list[dict[str, Any]],
    ) -> None:
        """Test execute() handles non-list LLM response."""
        mock_llm_json.return_value = {"error": "not a list"}

        tagger = TaggerAgent()
        input_data = TaggerInput(ideas=sample_ideas[:1], categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert output.tagged_ideas == []

    @patch("agents.tagger.async_llm_complete_json")
    def test_non_dict_items_in_response(
        self,
        mock_llm_json: AsyncMock,
        sample_ideas: list[dict[str, Any]],
    ) -> None:
        """Test execute() handles non-dict items in response."""
        mock_llm_json.return_value = [
            "not a dict",
            {"idea_title": "Valid Idea", "tags": ["SaaS"], "tag_categories": {"SaaS": "business_model"}},
            None,
        ]

        tagger = TaggerAgent()
        input_data = TaggerInput(ideas=sample_ideas[:1], categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert len(output.tagged_ideas) == 1
        assert output.tagged_ideas[0]["idea_title"] == "Valid Idea"


# ==============================================================================
# Test Helper Methods
# ==============================================================================

class TestHelperMethods:
    """Tests for helper methods."""

    def test_chunk_ideas(self) -> None:
        """Test _chunk_ideas splits ideas correctly."""
        tagger = TaggerAgent()
        ideas = [{"id": i} for i in range(25)]

        chunks = tagger._chunk_ideas(ideas, 10)

        assert len(chunks) == 3
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5

    def test_chunk_ideas_empty(self) -> None:
        """Test _chunk_ideas handles empty list."""
        tagger = TaggerAgent()
        chunks = tagger._chunk_ideas([], 10)
        assert chunks == []

    def test_build_category_descriptions_defaults(self) -> None:
        """Test _build_category_descriptions with default categories."""
        tagger = TaggerAgent()
        result = tagger._build_category_descriptions(list(DEFAULT_TAG_CATEGORIES.keys()))

        assert "INDUSTRY:" in result
        assert "TECHNOLOGY:" in result
        assert "BUSINESS_MODEL:" in result
        assert "FOUNDER_FIT:" in result
        assert "Healthcare" in result
        assert "SaaS" in result

    def test_build_category_descriptions_custom(self) -> None:
        """Test _build_category_descriptions with custom categories."""
        tagger = TaggerAgent()
        result = tagger._build_category_descriptions(["custom_cat"])

        assert "CUSTOM_CAT:" in result

    def test_build_ideas_prompt(self) -> None:
        """Test _build_ideas_prompt formats ideas correctly."""
        tagger = TaggerAgent()
        ideas = [
            {"idea_title": "Test Idea", "idea_summary": "A test idea summary", "score": 80},
            {"idea_title": "Another Idea", "idea_summary": "Short", "score": 65},
        ]

        result = tagger._build_ideas_prompt(ideas)

        assert "1. Title: Test Idea" in result
        assert "2. Title: Another Idea" in result
        assert "Score: 80" in result
        assert "Score: 65" in result

    def test_build_ideas_prompt_truncates_long_summary(self) -> None:
        """Test _build_ideas_prompt truncates long summaries."""
        tagger = TaggerAgent()
        long_summary = "A" * 300
        ideas = [{"idea_title": "Test", "idea_summary": long_summary, "score": 70}]

        result = tagger._build_ideas_prompt(ideas)

        assert len(result) < len(long_summary) + 100


# ==============================================================================
# Test TaggerOutput Structure
# ==============================================================================

class TestTaggerOutput:
    """Tests for TaggerOutput structure."""

    def test_tagger_output_to_dict(self) -> None:
        """Test TaggerOutput.to_dict() returns correct structure."""
        output = TaggerOutput(
            tagged_ideas=[
                {
                    "idea_title": "Test",
                    "tags": ["SaaS", "Healthcare"],
                    "tag_categories": {"SaaS": "business_model", "Healthcare": "industry"},
                }
            ],
            tag_counts={"SaaS": 1, "Healthcare": 1},
        )

        result = output.to_dict()

        assert "tagged_ideas" in result
        assert "tag_counts" in result
        assert len(result["tagged_ideas"]) == 1
        assert result["tag_counts"]["SaaS"] == 1

    def test_tagger_output_empty(self) -> None:
        """Test TaggerOutput handles empty results."""
        output = TaggerOutput(tagged_ideas=[], tag_counts={})

        result = output.to_dict()

        assert result["tagged_ideas"] == []
        assert result["tag_counts"] == {}


# ==============================================================================
# Test Tag Counts Aggregation
# ==============================================================================

class TestTagCountsAggregation:
    """Tests for tag count aggregation."""

    @patch("agents.tagger.async_llm_complete_json")
    def test_tag_counts_across_batches(
        self,
        mock_llm_json: AsyncMock,
    ) -> None:
        """Test tag counts are aggregated across batches."""
        ideas = [
            {"idea_title": f"Idea {i}", "idea_summary": f"Summary {i}", "score": 70}
            for i in range(20)
        ]

        batch_responses = [
            [
                {
                    "idea_title": f"Idea {i}",
                    "tags": ["SaaS", "LLM"],
                    "tag_categories": {"SaaS": "business_model", "LLM": "technology"},
                }
                for i in range(10)
            ],
            [
                {
                    "idea_title": f"Idea {i}",
                    "tags": ["SaaS", "Healthcare"],
                    "tag_categories": {"SaaS": "business_model", "Healthcare": "industry"},
                }
                for i in range(10, 20)
            ],
        ]

        mock_llm_json.side_effect = batch_responses

        tagger = TaggerAgent(batch_size=10)
        input_data = TaggerInput(ideas=ideas, categories=[])
        output = __import__("asyncio").run(tagger.execute(input_data))

        assert output.tag_counts["SaaS"] == 20
        assert output.tag_counts["LLM"] == 10
        assert output.tag_counts["Healthcare"] == 10