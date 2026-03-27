"""Unit tests for EvaluatorAgent."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Any

from agents.evaluator import EvaluatorAgent
from agents.config import (
    EvaluatorInput,
    EvaluatorOutput,
    Idea,
    IdeaScore,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_criteria() -> dict[str, Any]:
    """Return mock evaluation criteria for testing."""
    return {
        "version": 1,
        "success_factors": [
            {
                "factor": "Problem Clarity",
                "importance": "critical",
                "weight": 0.15,
                "description": "Clear articulation of problem being solved",
                "indicators": ["Problem is well-defined", "Users have pain point"],
            },
            {
                "factor": "AI Advantage",
                "importance": "critical",
                "weight": 0.15,
                "description": "Problem genuinely requires AI to solve",
                "indicators": ["Needs pattern recognition", "Scale requires automation"],
            },
        ],
        "failure_patterns": [
            {
                "pattern": "Solution Looking for Problem",
                "red_flag_level": "critical",
                "description": "Building AI without clear use case",
                "warning_signs": ["Tech-first pitch", "No user pain point"],
            },
        ],
        "market_insights": {
            "hot_sectors_2024": ["AI developer tools", "Vertical AI agents"],
            "saturated_markets": ["Generic chatbots"],
        },
    }


@pytest.fixture
def sample_content_item() -> dict[str, Any]:
    """Return a sample content item for testing."""
    return {
        "url": "https://example.com/ai-ideas",
        "content": {
            "text": "AI-Powered Code Review Assistant: An innovative AI tool that reviews code changes and suggests improvements based on best practices and security guidelines. This startup idea addresses the pain point of tedious manual code reviews for software development teams. The product uses machine learning to analyze code patterns and provide actionable feedback for developers.",
        },
    }


@pytest.fixture
def short_content_item() -> dict[str, Any]:
    """Return a content item with text too short to process."""
    return {
        "url": "https://example.com/short",
        "content": {
            "text": "Too short",
        },
    }


@pytest.fixture
def empty_content_item() -> dict[str, Any]:
    """Return a content item with no text."""
    return {
        "url": "https://example.com/empty",
        "content": {},
    }


@pytest.fixture
def evaluator_input(sample_content_item: dict[str, Any]) -> EvaluatorInput:
    """Return a sample EvaluatorInput for testing."""
    return EvaluatorInput(
        run_task_id="test-run-123",
        iteration_number=1,
        extracted_content=[sample_content_item],
    )


# ==============================================================================
# Test _extract_ideas() with Valid Content
# ==============================================================================

class TestExtractIdeasValid:
    """Tests for _extract_ideas() with valid content and mocked LLM responses."""

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_single_idea(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
        valid_idea_response: list[dict[str, Any]],
    ) -> None:
        """Test _extract_ideas returns a single idea from valid LLM response."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = valid_idea_response

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=sample_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert
        assert len(ideas) == 1
        assert ideas[0].idea_title == "AI-Powered Code Review Assistant"
        assert ideas[0].score == 82
        assert ideas[0].source_urls == ["https://example.com/ai-ideas"]
        assert ideas[0].score_breakdown.novelty == 90
        assert ideas[0].score_breakdown.feasibility == 80
        assert ideas[0].score_breakdown.market_potential == 85

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_multiple_ideas(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
        multiple_ideas_response: list[dict[str, Any]],
    ) -> None:
        """Test _extract_ideas returns multiple ideas from valid LLM response."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = multiple_ideas_response

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=sample_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert
        assert len(ideas) == 2
        assert ideas[0].idea_title == "AI Meeting Summarizer"
        assert ideas[0].score == 78
        assert ideas[1].idea_title == "Personalized Nutrition AI"
        assert ideas[1].score == 65

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_preserves_source_url(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        valid_idea_response: list[dict[str, Any]],
    ) -> None:
        """Test _extract_ideas correctly assigns source URL to ideas."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = valid_idea_response

        # Execute with custom URL
        content_item = {
            "url": "https://custom-source.com/article",
            "content": {"text": "This is a detailed article about AI-powered code review assistants and their applications in modern software development practices. The startup idea focuses on building an innovative product that helps developers improve code quality through machine learning algorithms and intelligent automation."},
        }
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert
        assert len(ideas) == 1
        assert ideas[0].source_urls == ["https://custom-source.com/article"]


# ==============================================================================
# Test Score Calculation and Ranking
# ==============================================================================

class TestScoreCalculationAndRanking:
    """Tests for score calculation and ranking logic."""

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_ranks_ideas_by_score(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        multiple_ideas_response: list[dict[str, Any]],
    ) -> None:
        """Test evaluate() returns ideas in score order (highest first)."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = multiple_ideas_response

        # Execute
        content_item = {
            "url": "https://example.com/ideas",
            "content": {"text": "This article discusses innovative AI startup ideas including meeting summarizers and personalized nutrition platforms for health-conscious consumers. The product concepts leverage machine learning technology to solve real business problems and create value for users in various market segments."},
        }
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=[content_item],
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        output = asyncio.run(evaluator.evaluate(input_data))

        # Assert - ideas should be ordered by score (highest first)
        assert len(output.ideas) == 2
        assert output.ideas[0].score >= output.ideas[1].score

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_filters_high_and_low_scoring(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        valid_idea_response: list[dict[str, Any]],
        low_score_idea_response: list[dict[str, Any]],
    ) -> None:
        """Test evaluate() correctly identifies high and low scoring ideas."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        # Return high score idea first, then low score
        mock_llm_json.side_effect = [valid_idea_response, low_score_idea_response]

        # Execute
        content_items = [
            {"url": "https://example.com/high", "content": {"text": "This article discusses high-scoring AI startup ideas with strong market potential and clear value propositions for enterprise customers. The innovative product solutions address real business needs and leverage artificial intelligence technology effectively."}},
            {"url": "https://example.com/low", "content": {"text": "This article covers low-scoring AI ideas that lack differentiation and face significant market challenges in crowded spaces. The startup concepts need more innovation and product-market fit analysis to succeed in competitive environments."}},
        ]
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=content_items,
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        output = asyncio.run(evaluator.evaluate(input_data))

        # Assert - meta_learning.update_criteria_from_results should be called
        # with high scoring (>=75) and low scoring (<60) ideas
        assert mock_meta_instance.update_criteria_from_results.called
        call_args = mock_meta_instance.update_criteria_from_results.call_args
        high_scoring = call_args[0][1]  # Second argument is high_scoring list
        low_scoring = call_args[0][2]  # Third argument is low_scoring list
        
        # High score idea (82) should be in high_scoring
        assert len(high_scoring) == 1
        assert high_scoring[0]["score"] == 82
        
        # Low score idea (38) should be in low_scoring
        assert len(low_scoring) == 1
        assert low_scoring[0]["score"] == 38

    def test_idea_score_total_calculation(self) -> None:
        """Test IdeaScore.total() calculates weighted average correctly."""
        # Weighted: 30% novelty, 40% feasibility, 30% market_potential
        score = IdeaScore(novelty=100, feasibility=100, market_potential=100)
        assert score.total() == 100

        score = IdeaScore(novelty=80, feasibility=70, market_potential=90)
        # 0.3 * 80 + 0.4 * 70 + 0.3 * 90 = 24 + 28 + 27 = 79
        assert score.total() == 79

        score = IdeaScore(novelty=50, feasibility=50, market_potential=50)
        assert score.total() == 50

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_limits_to_15_ideas(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
    ) -> None:
        """Test evaluate() limits output to max 15 ideas."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        
        # Create 20 ideas
        many_ideas = [
            {
                "idea_title": f"Idea {i}",
                "idea_summary": f"Summary {i}",
                "detailed_scores": {
                    "problem_clarity": 70,
                    "ai_advantage": 70,
                    "market_timing": 70,
                    "solo_founder_feasibility": 70,
                    "distribution_path": 70,
                    "monetization_clarity": 70,
                    "defensibility": 70,
                    "technical_feasibility": 70,
                },
                "total_score": 70,
                "verdict": "Promising",
                "strengths": ["Good"],
                "risks": ["Some risk"],
                "advice": "Test",
                "red_flags": [],
            }
            for i in range(20)
        ]
        mock_llm_json.return_value = many_ideas

        # Execute
        content_item = {
            "url": "https://example.com/many-ideas",
            "content": {"text": "This comprehensive article presents twenty innovative AI startup ideas covering various sectors including healthcare, finance, education, and enterprise software solutions. Each product concept leverages machine learning and artificial intelligence to solve real problems and create business value for customers across different markets."},
        }
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=[content_item],
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        output = asyncio.run(evaluator.evaluate(input_data))

        # Assert - should be limited to 15
        assert len(output.ideas) == 15


# ==============================================================================
# Test Empty Content Handling
# ==============================================================================

class TestEmptyContentHandling:
    """Tests for handling empty or insufficient content."""

    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_empty_content(
        self,
        mock_meta_class: MagicMock,
        mock_criteria: dict[str, Any],
        empty_content_item: dict[str, Any],
    ) -> None:
        """Test _extract_ideas returns empty list for content with no text."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=empty_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert
        assert ideas == []

    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_short_content(
        self,
        mock_meta_class: MagicMock,
        mock_criteria: dict[str, Any],
        short_content_item: dict[str, Any],
    ) -> None:
        """Test _extract_ideas returns empty list for content < 50 chars."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=short_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert
        assert ideas == []

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_empty_extracted_content_list(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
    ) -> None:
        """Test evaluate() handles empty extracted_content list."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance

        # Execute
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=[],  # Empty list
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        output = asyncio.run(evaluator.evaluate(input_data))

        # Assert
        assert output.ideas == []
        assert "0 sources" in output.iteration_summary
        # LLM should not be called for empty content
        assert not mock_llm_json.called


# ==============================================================================
# Test Malformed LLM Response Handling
# ==============================================================================

class TestMalformedResponseHandling:
    """Tests for handling malformed or invalid LLM responses."""

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_non_list_response(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
        invalid_idea_response: dict[str, Any],
    ) -> None:
        """Test _extract_ideas handles non-list LLM response."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = invalid_idea_response  # Returns dict, not list

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=sample_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert - should return empty list for non-list response
        assert ideas == []

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_empty_list_response(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
        empty_idea_response: list[dict[str, Any]],
    ) -> None:
        """Test _extract_ideas handles empty list response."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = empty_idea_response

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=sample_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert
        assert ideas == []

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_missing_required_fields(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
        partial_score_idea_response: list[dict[str, Any]],
    ) -> None:
        """Test _extract_ideas handles ideas with missing score fields."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = partial_score_idea_response

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=sample_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert - should still create idea with default scores (0) for missing fields
        assert len(ideas) == 1
        assert ideas[0].idea_title == "Incomplete Scoring Test"
        # Missing ai_advantage, solo_founder_feasibility, monetization_clarity should default to 0
        assert ideas[0].score_breakdown.novelty == 0  # ai_advantage missing
        assert ideas[0].score_breakdown.feasibility == 0  # solo_founder_feasibility missing
        assert ideas[0].score_breakdown.market_potential == 0  # monetization_clarity missing

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_missing_title_field(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
    ) -> None:
        """Test _extract_ideas handles ideas with missing title field."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        
        # Idea missing title
        mock_llm_json.return_value = [
            {
                "idea_summary": "An idea without a title",
                "detailed_scores": {
                    "ai_advantage": 70,
                    "solo_founder_feasibility": 70,
                    "monetization_clarity": 70,
                },
                "total_score": 70,
                "verdict": "Promising",
                "strengths": [],
                "risks": [],
                "advice": "Test",
            }
        ]

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        ideas = asyncio.run(evaluator._extract_ideas(
            content_item=sample_content_item,
            run_task_id="test-run-123",
            evaluation_criteria=mock_criteria,
        ))

        # Assert - should use default title "Untitled"
        assert len(ideas) == 1
        assert ideas[0].idea_title == "Untitled"

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_propagates_extraction_error(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        valid_idea_response: list[dict[str, Any]],
    ) -> None:
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        
        mock_llm_json.side_effect = [
            Exception("LLM error"),
            valid_idea_response,
        ]

        content_items = [
            {"url": "https://example.com/fail", "content": {"text": "This content will fail during processing due to simulated LLM error conditions in the test environment. The AI startup idea discusses innovative product solutions for enterprise customers and business applications."}},
            {"url": "https://example.com/success", "content": {"text": "This content will succeed and produce valid AI startup ideas for evaluation and scoring purposes. The innovative product concept leverages machine learning to solve real business problems effectively for customers."}},
        ]
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=content_items,
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        
        with pytest.raises(Exception):
            asyncio.run(evaluator.evaluate(input_data))


# ==============================================================================
# Test Timeout and Error Handling
# ==============================================================================

class TestTimeoutAndErrorHandling:
    """Tests for timeout and error handling."""

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_extract_ideas_llm_timeout(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        sample_content_item: dict[str, Any],
    ) -> None:
        """Test _extract_ideas handles LLM timeout gracefully."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.side_effect = TimeoutError("LLM request timed out")

        # Execute
        evaluator = EvaluatorAgent(db_path=":memory:")
        
        # Should raise the timeout error
        with pytest.raises(TimeoutError):
            asyncio.run(evaluator._extract_ideas(
                content_item=sample_content_item,
                run_task_id="test-run-123",
                evaluation_criteria=mock_criteria,
            ))

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_propagates_exception_in_extract_ideas(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        valid_idea_response: list[dict[str, Any]],
    ) -> None:
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        
        call_count = [0]
        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("LLM connection failed")
            return valid_idea_response
        
        mock_llm_json.side_effect = side_effect

        content_items = [
            {"url": "https://example.com/1", "content": {"text": "First content item about AI startup ideas that will encounter processing errors during the evaluation phase. The innovative product concept discusses machine learning applications for business solutions and enterprise customers."}},
            {"url": "https://example.com/2", "content": {"text": "Second content item discussing innovative AI applications that will successfully complete the evaluation process. The startup idea focuses on creating value through intelligent automation technology for modern businesses."}},
        ]
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=content_items,
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        
        with pytest.raises(RuntimeError):
            asyncio.run(evaluator.evaluate(input_data))

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluate_all_content_items_fail(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
    ) -> None:
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.side_effect = RuntimeError("LLM error")

        content_items = [
            {"url": "https://example.com/1", "content": {"text": "This is a detailed AI startup idea description that discusses innovative machine learning applications for business automation. The concept leverages natural language processing to solve real problems for enterprise customers and developers."}},
            {"url": "https://example.com/2", "content": {"text": "Another comprehensive AI product description focusing on computer vision and automation tools for modern businesses. This startup idea targets underserved markets with innovative technology solutions and clear monetization strategies for sustainable growth."}},
        ]
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=content_items,
        )
        evaluator = EvaluatorAgent(db_path=":memory:")

        with pytest.raises(RuntimeError):
            asyncio.run(evaluator.evaluate(input_data))


# ==============================================================================
# Test EvaluatorOutput Structure
# ==============================================================================

class TestEvaluatorOutput:
    """Tests for EvaluatorOutput structure and methods."""

    @patch("agents.evaluator.async_llm_complete_json")
    @patch("agents.evaluator.MetaLearningAgent")
    def test_evaluator_output_structure(
        self,
        mock_meta_class: MagicMock,
        mock_llm_json: AsyncMock,
        mock_criteria: dict[str, Any],
        valid_idea_response: list[dict[str, Any]],
    ) -> None:
        """Test EvaluatorOutput has correct structure."""
        # Setup mocks
        mock_meta_instance = MagicMock()
        mock_meta_instance.research_startup_criteria.return_value = mock_criteria
        mock_meta_class.return_value = mock_meta_instance
        mock_llm_json.return_value = valid_idea_response

        # Execute
        content_item = {
            "url": "https://example.com/test",
            "content": {"text": "This test content provides detailed information about AI-powered code review assistants and their benefits for software development teams. The innovative startup idea leverages machine learning technology to improve code quality and developer productivity."},
        }
        input_data = EvaluatorInput(
            run_task_id="test-run-123",
            iteration_number=1,
            extracted_content=[content_item],
        )
        evaluator = EvaluatorAgent(db_path=":memory:")
        output = asyncio.run(evaluator.evaluate(input_data))

        # Assert structure
        assert isinstance(output, EvaluatorOutput)
        assert isinstance(output.ideas, list)
        assert isinstance(output.iteration_summary, str)
        assert len(output.ideas) == 1

    def test_idea_to_dict(self) -> None:
        """Test Idea.to_dict() returns correct structure."""
        idea = Idea(
            idea_title="Test Idea",
            idea_summary="A test idea",
            source_urls=["https://example.com"],
            score=75,
            score_breakdown=IdeaScore(novelty=80, feasibility=70, market_potential=75),
            evaluator_explain="Test explanation",
            idea_payload={"custom": "data"},
        )
        
        result = idea.to_dict()
        
        assert result["idea_title"] == "Test Idea"
        assert result["idea_summary"] == "A test idea"
        assert result["source_urls"] == ["https://example.com"]
        assert result["score"] == 75
        assert result["score_breakdown"]["novelty"] == 80
        assert result["score_breakdown"]["feasibility"] == 70
        assert result["score_breakdown"]["market_potential"] == 75
        assert result["evaluator_explain"] == "Test explanation"
        assert result["idea_payload"]["custom"] == "data"

    def test_evaluator_output_to_dict(self) -> None:
        """Test EvaluatorOutput.to_dict() returns correct structure."""
        idea = Idea(
            idea_title="Test",
            idea_summary="Summary",
            source_urls=["https://example.com"],
            score=80,
            score_breakdown=IdeaScore(novelty=80, feasibility=80, market_potential=80),
            evaluator_explain="Good",
            idea_payload={},
        )
        output = EvaluatorOutput(
            ideas=[idea],
            iteration_summary="Test summary",
        )
        
        result = output.to_dict()
        
        assert "ideas" in result
        assert "iteration_summary" in result
        assert result["iteration_summary"] == "Test summary"
        assert len(result["ideas"]) == 1
        assert result["ideas"][0]["idea_title"] == "Test"


# ==============================================================================
# Test Criteria Prompt Building
# ==============================================================================

class TestBuildCriteriaPrompt:
    """Tests for _build_criteria_prompt method."""

    def test_build_criteria_prompt_includes_success_factors(self) -> None:
        """Test _build_criteria_prompt includes success factors."""
        evaluator = EvaluatorAgent(db_path=":memory:")
        criteria = {
            "success_factors": [
                {
                    "factor": "Problem Clarity",
                    "importance": "critical",
                    "weight": 0.15,
                    "description": "Clear problem",
                    "indicators": ["Well-defined", "User pain"],
                },
            ],
            "failure_patterns": [],
        }
        
        prompt = evaluator._build_criteria_prompt(criteria)
        
        assert "LEARNED STARTUP SUCCESS CRITERIA" in prompt
        assert "Problem Clarity" in prompt
        assert "Importance: critical" in prompt
        assert "Weight: 15%" in prompt

    def test_build_criteria_prompt_includes_failure_patterns(self) -> None:
        """Test _build_criteria_prompt includes failure patterns."""
        evaluator = EvaluatorAgent(db_path=":memory:")
        criteria = {
            "success_factors": [],
            "failure_patterns": [
                {
                    "pattern": "Solution Looking for Problem",
                    "red_flag_level": "critical",
                    "description": "No clear use case",
                    "warning_signs": ["Tech-first", "No pain point"],
                },
            ],
        }
        
        prompt = evaluator._build_criteria_prompt(criteria)
        
        assert "FAILURE PATTERNS TO AVOID" in prompt
        assert "Solution Looking for Problem" in prompt
        assert "Severity: critical" in prompt

    def test_build_criteria_prompt_limits_output(self) -> None:
        """Test _build_criteria_prompt limits factors and patterns for brevity."""
        evaluator = EvaluatorAgent(db_path=":memory:")
        criteria = {
            "success_factors": [
                {
                    "factor": f"TestFactor{i}",
                    "importance": "medium",
                    "weight": 0.10,
                    "description": f"Description {i}",
                    "indicators": ["Indicator 1", "Indicator 2", "Indicator 3"],
                }
                for i in range(10)
            ],
            "failure_patterns": [
                {
                    "pattern": f"TestPattern{i}",
                    "red_flag_level": "high",
                    "description": f"Description {i}",
                    "warning_signs": ["Sign 1", "Sign 2", "Sign 3"],
                }
                for i in range(10)
            ],
        }
        
        prompt = evaluator._build_criteria_prompt(criteria)
        
        # Should limit to 6 success factors
        assert prompt.count("TestFactor") <= 6
        # Should limit to 4 failure patterns
        assert prompt.count("TestPattern") <= 4