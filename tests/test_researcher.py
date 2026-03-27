"""Unit tests for ResearcherAgent."""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch
from typing import Any

import pytest

# Mock ddgs module before importing researcher
mock_ddgs_module = MagicMock()
mock_ddgs_class = MagicMock()
mock_ddgs_module.DDGS = mock_ddgs_class
sys.modules["ddgs"] = mock_ddgs_module

# Now import after mocking
from agents.config import (
    ResearcherInput,
    ResearcherOutput,
    PlannerOutput,
)
from agents.researcher import ResearcherAgent, DDGS_AVAILABLE, DDGS


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_db_path(tmp_path) -> str:
    return str(tmp_path / "test_researcher.db")


@pytest.fixture
def planner_output() -> PlannerOutput:
    return PlannerOutput(
        search_queries=["AI startup ideas", "machine learning business opportunities"],
        target_sources=["techcrunch.com", "venturebeat.com"],
        scraping_depth=2,
        filters={"exclude_domains": ["facebook.com", "twitter.com"]},
    )


@pytest.fixture
def researcher_input(planner_output: PlannerOutput) -> ResearcherInput:
    return ResearcherInput(
        run_task_id="test-run-123",
        iteration_number=1,
        search_plan=planner_output,
    )


@pytest.fixture
def researcher_input_dict(planner_output: PlannerOutput) -> dict[str, Any]:
    return {
        "run_task_id": "test-run-456",
        "iteration_number": 2,
        "search_plan": planner_output.to_dict(),
    }


@pytest.fixture
def mock_db_functions():
    with patch("agents.researcher.filter_new_urls") as mock_filter, \
         patch("agents.researcher.mark_sources_status") as mock_mark:
        yield {"filter_new_urls": mock_filter, "mark_sources_status": mock_mark}


# ==============================================================================
# Test _search() Method
# ==============================================================================

class TestSearchMethod:
    """Tests for the _search() internal method."""

    def test_search_returns_urls_from_results(
        self,
        mock_db_path: str,
        ddg_search_results: list[dict[str, Any]],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        researcher = ResearcherAgent(db_path=mock_db_path)
        urls = asyncio.run(researcher._search("AI startup ideas", max_results=10))

        assert len(urls) == 5
        assert urls[0] == "https://techcrunch.com/2024/01/15/ai-startup-raises-funding"
        assert urls[4] == "https://hackernews.com/show?fn=ai-startup-idea"
        mock_ddgs_instance.text.assert_called_once_with("AI startup ideas", max_results=10)

    def test_search_filters_out_missing_href(
        self,
        mock_db_path: str,
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {"href": "https://example.com/1"},
            {"title": "No href here"},
            {"href": "https://example.com/2"},
            {"body": "Also no href"},
        ]
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        researcher = ResearcherAgent(db_path=mock_db_path)
        urls = asyncio.run(researcher._search("test query", max_results=10))

        assert len(urls) == 2
        assert urls == ["https://example.com/1", "https://example.com/2"]

    def test_search_empty_results(
        self,
        mock_db_path: str,
        empty_ddg_results: list[dict[str, Any]],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = empty_ddg_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        researcher = ResearcherAgent(db_path=mock_db_path)
        urls = asyncio.run(researcher._search("nonexistent query xyz", max_results=10))

        assert urls == []


# ==============================================================================
# Test research() Method - Normal Cases
# ==============================================================================

class TestResearchMethod:
    """Tests for the research() main method."""

    def test_research_with_valid_search_plan(
        self,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [
                "https://techcrunch.com/2024/01/15/ai-startup-raises-funding",
                "https://www.theverge.com/2024/01/14/new-ai-framework-released",
            ],
            "skipped_urls": [],
        }

        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert isinstance(output, ResearcherOutput)
        assert len(output.candidate_urls) == 2
        assert "Query 'AI startup ideas': found 5 URLs" in output.coverage_notes
        assert "Query 'machine learning business opportunities': found 5 URLs" in output.coverage_notes
        # URLs are deduplicated across queries, so total unique is 5 (not 10)
        assert "Total unique: 5" in output.coverage_notes
        assert "New: 2" in output.coverage_notes

        mock_db_functions["filter_new_urls"].assert_called_once()
        call_args = mock_db_functions["filter_new_urls"].call_args
        assert call_args.kwargs["db_path"] == mock_db_path
        assert call_args.kwargs["run_task_id"] == "test-run-123"
        assert call_args.kwargs["retry_limit"] == 2

        mock_db_functions["mark_sources_status"].assert_called_once()
        mark_call_args = mock_db_functions["mark_sources_status"].call_args
        assert mark_call_args.kwargs["db_path"] == mock_db_path
        assert mark_call_args.kwargs["run_task_id"] == "test-run-123"
        assert mark_call_args.kwargs["status"] == "queued"

    def test_research_accepts_dict_search_plan(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": ["https://example.com/1"],
            "skipped_urls": [],
        }

        # ResearcherInput accepts dict for search_plan field
        researcher_input_with_dict = ResearcherInput(
            run_task_id="test-run-456",
            iteration_number=2,
            search_plan=planner_output.to_dict(),  # type: ignore
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input_with_dict))

        assert isinstance(output, ResearcherOutput)
        assert len(output.candidate_urls) == 1

    def test_research_deduplicates_urls(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [r["href"] for r in ddg_search_results[:3]],
            "skipped_urls": [],
        }

        researcher_input = ResearcherInput(
            run_task_id="test-run-789",
            iteration_number=1,
            search_plan=planner_output,
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        asyncio.run(researcher.research(researcher_input))

        call_args = mock_db_functions["filter_new_urls"].call_args
        urls_passed = call_args.kwargs["urls"]
        assert len(urls_passed) == 5


# ==============================================================================
# Test URL Deduplication
# ==============================================================================

class TestURLDeduplication:
    """Tests for URL deduplication via filter_new_urls."""

    def test_filter_new_urls_keeps_new_urls(
        self,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [r["href"] for r in ddg_search_results],
            "skipped_urls": [],
        }

        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert len(output.candidate_urls) == 5
        assert len(output.candidate_urls) == len(ddg_search_results)

    def test_filter_new_urls_skips_seen_urls(
        self,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [ddg_search_results[0]["href"]],
            "skipped_urls": [r["href"] for r in ddg_search_results[1:]],
        }

        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert len(output.candidate_urls) == 1
        assert "Skipped: 4" in output.coverage_notes

    def test_filter_new_urls_all_skipped(
        self,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [],
            "skipped_urls": [r["href"] for r in ddg_search_results],
        }

        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert len(output.candidate_urls) == 0
        assert "New: 0" in output.coverage_notes
        assert not mock_db_functions["mark_sources_status"].called


# ==============================================================================
# Test Empty Results Handling
# ==============================================================================

class TestEmptyResultsHandling:
    """Tests for handling empty search results."""

    def test_research_empty_search_results(
        self,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        empty_ddg_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = empty_ddg_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [],
            "skipped_urls": [],
        }

        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert isinstance(output, ResearcherOutput)
        assert output.candidate_urls == []
        assert "Query 'AI startup ideas': found 0 URLs" in output.coverage_notes
        assert "Total unique: 0" in output.coverage_notes
        assert "New: 0" in output.coverage_notes

    def test_research_mixed_empty_and_results(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        ddg_search_results: list[dict[str, Any]],
        empty_ddg_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = [ddg_search_results, empty_ddg_results]
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [ddg_search_results[0]["href"]],
            "skipped_urls": [],
        }

        researcher_input = ResearcherInput(
            run_task_id="test-run-mixed",
            iteration_number=1,
            search_plan=planner_output,
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert len(output.candidate_urls) == 1
        assert "Query 'AI startup ideas': found 5 URLs" in output.coverage_notes
        assert "Query 'machine learning business opportunities': found 0 URLs" in output.coverage_notes


# ==============================================================================
# Test Timeout and Error Handling
# ==============================================================================

class TestTimeoutAndErrorHandling:
    """Tests for timeout and error handling."""

    def test_research_handles_search_timeout(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = [
            TimeoutError("Search timed out"),
            ddg_search_results,
        ]
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [ddg_search_results[0]["href"]],
            "skipped_urls": [],
        }

        researcher_input = ResearcherInput(
            run_task_id="test-run-timeout",
            iteration_number=1,
            search_plan=planner_output,
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert len(output.candidate_urls) == 1
        assert "Query 'AI startup ideas': failed - Search timed out" in output.coverage_notes
        assert "Query 'machine learning business opportunities': found 5 URLs" in output.coverage_notes

    def test_research_handles_all_queries_fail(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = [
            ConnectionError("Network error"),
            TimeoutError("Request timeout"),
        ]
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [],
            "skipped_urls": [],
        }

        researcher_input = ResearcherInput(
            run_task_id="test-run-all-fail",
            iteration_number=1,
            search_plan=planner_output,
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert output.candidate_urls == []
        assert "Query 'AI startup ideas': failed - Network error" in output.coverage_notes
        assert "Query 'machine learning business opportunities': failed - Request timeout" in output.coverage_notes
        assert "Total unique: 0" in output.coverage_notes

    def test_search_handles_ddg_exception(
        self,
        mock_db_path: str,
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = RuntimeError("DDG API error")
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        researcher = ResearcherAgent(db_path=mock_db_path)
        with pytest.raises(RuntimeError, match="DDG API error"):
            asyncio.run(researcher._search("test query", max_results=10))


# ==============================================================================
# Test DDGS Import Error
# ==============================================================================

class TestDDGSImportError:
    """Tests for handling missing DDGS library."""

    def test_init_raises_when_ddgs_not_available(self, mock_db_path: str) -> None:
        with patch("agents.researcher.DDGS_AVAILABLE", False):
            with pytest.raises(ImportError, match="DuckDuckGo search not available"):
                ResearcherAgent(db_path=mock_db_path)


# ==============================================================================
# Test ResearcherOutput Structure
# ==============================================================================

class TestResearcherOutputStructure:
    """Tests for ResearcherOutput structure and methods."""

    def test_researcher_output_to_dict(self) -> None:
        output = ResearcherOutput(
            candidate_urls=["https://example.com/1", "https://example.com/2"],
            coverage_notes="Query 'test': found 2 URLs",
        )

        result = output.to_dict()

        assert result["candidate_urls"] == ["https://example.com/1", "https://example.com/2"]
        assert result["coverage_notes"] == "Query 'test': found 2 URLs"

    def test_researcher_output_empty_urls(self) -> None:
        output = ResearcherOutput(
            candidate_urls=[],
            coverage_notes="No URLs found",
        )

        assert output.candidate_urls == []
        assert output.to_dict()["candidate_urls"] == []


# ==============================================================================
# Test Coverage Notes
# ==============================================================================

class TestCoverageNotes:
    """Tests for coverage_notes generation."""

    def test_coverage_notes_includes_query_results(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = ddg_search_results
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [r["href"] for r in ddg_search_results],
            "skipped_urls": [],
        }

        researcher_input = ResearcherInput(
            run_task_id="test-coverage",
            iteration_number=1,
            search_plan=planner_output,
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert "Query 'AI startup ideas': found 5 URLs" in output.coverage_notes
        assert "Query 'machine learning business opportunities': found 5 URLs" in output.coverage_notes
        # URLs are deduplicated across queries, so total unique is 5 (not 10)
        assert "Total unique: 5" in output.coverage_notes
        assert "New: 5" in output.coverage_notes
        assert "Skipped: 0" in output.coverage_notes

    def test_coverage_notes_with_failures(
        self,
        mock_db_path: str,
        planner_output: PlannerOutput,
        ddg_search_results: list[dict[str, Any]],
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.side_effect = [
            Exception("Rate limited"),
            ddg_search_results,
        ]
        DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        DDGS.return_value.__exit__ = MagicMock(return_value=False)

        mock_db_functions["filter_new_urls"].return_value = {
            "keep_urls": [ddg_search_results[0]["href"]],
            "skipped_urls": [],
        }

        researcher_input = ResearcherInput(
            run_task_id="test-coverage-fail",
            iteration_number=1,
            search_plan=planner_output,
        )
        researcher = ResearcherAgent(db_path=mock_db_path)
        output = asyncio.run(researcher.research(researcher_input))

        assert "Query 'AI startup ideas': failed - Rate limited" in output.coverage_notes
        assert "Query 'machine learning business opportunities': found 5 URLs" in output.coverage_notes