"""Performance benchmarks using pytest-benchmark.

This module benchmarks the async implementations of Evaluator, Researcher, and Scraper
agents to measure the performance improvement from parallel processing.

Expected improvement: 50-70% reduction in iteration time through:
1. Parallel LLM calls (Evaluator)
2. Parallel searches (Researcher)
3. Concurrent fetching (Scraper)

Run with: pytest tests/test_performance.py --benchmark-only
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Mock ddgs module before importing researcher
mock_ddgs_module = MagicMock()
mock_ddgs_class = MagicMock()
mock_ddgs_module.DDGS = mock_ddgs_class
sys.modules["ddgs"] = mock_ddgs_module

# Mock trafilatura before importing scraper
mock_trafilatura = MagicMock()
mock_trafilatura.fetch_url = MagicMock()
mock_trafilatura.extract = MagicMock()
mock_trafilatura.use_config = MagicMock()
mock_trafilatura_config = MagicMock()
mock_trafilatura.use_config.return_value = mock_trafilatura_config
sys.modules["trafilatura"] = mock_trafilatura
sys.modules["trafilatura.settings"] = MagicMock()

# Mock requests/beautifulsoup
mock_requests = MagicMock()
sys.modules["requests"] = mock_requests
mock_bs4 = MagicMock()
sys.modules["bs4"] = mock_bs4
sys.modules["bs4"].BeautifulSoup = MagicMock()

from agents.evaluator import EvaluatorAgent
from agents.researcher import ResearcherAgent, DDGS_AVAILABLE
from agents.scraper import ScraperAgent, TRAFILATURA_AVAILABLE, REQUESTS_AVAILABLE

# Get DDGS from the mocked module
DDGS = mock_ddgs_class

from agents.config import (
    EvaluatorInput,
    ResearcherInput,
    ScraperInput,
    PlannerOutput,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_db_path(tmp_path) -> str:
    return str(tmp_path / "test_perf.db")


@pytest.fixture
def mock_criteria() -> dict[str, Any]:
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
        ],
        "failure_patterns": [
            {
                "pattern": "Solution Looking for Problem",
                "red_flag_level": "critical",
                "description": "Building AI without clear use case",
                "warning_signs": ["Tech-first pitch", "No user pain point"],
            },
        ],
    }


@pytest.fixture
def sample_idea_response() -> list[dict[str, Any]]:
    return [
        {
            "idea_title": "AI-Powered Code Review Assistant",
            "idea_summary": "An AI tool that reviews code changes and suggests improvements.",
            "detailed_scores": {
                "problem_clarity": 85,
                "ai_advantage": 90,
                "market_timing": 75,
                "solo_founder_feasibility": 80,
                "distribution_path": 70,
                "monetization_clarity": 85,
                "defensibility": 65,
                "technical_feasibility": 90,
            },
            "total_score": 82,
            "verdict": "Strong",
            "strengths": ["Clear problem", "Strong AI advantage"],
            "risks": ["Competition"],
            "advice": "Focus on specific languages",
            "red_flags": [],
        }
    ]


@pytest.fixture
def ddg_results() -> list[dict[str, Any]]:
    return [
        {"href": f"https://example.com/article{i}"} for i in range(10)
    ]


@pytest.fixture
def html_content() -> str:
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Article</title></head>
    <body>
        <h1>AI Startup Ideas</h1>
        <p>This article discusses innovative AI startup ideas for entrepreneurs.</p>
        <p>The content covers machine learning applications and business opportunities.</p>
    </body>
    </html>
    """


@pytest.fixture
def mock_db_functions():
    with patch("agents.scraper.can_scrape") as mock_can_scrape, \
         patch("agents.scraper.update_scraper_timestamp") as mock_update, \
         patch("agents.scraper.mark_sources_status") as mock_mark:
        yield {
            "can_scrape": mock_can_scrape,
            "update_scraper_timestamp": mock_update,
            "mark_sources_status": mock_mark,
        }


# ==============================================================================
# Evaluator Benchmarks
# ==============================================================================

class TestEvaluatorBenchmarks:
    """Benchmarks for EvaluatorAgent parallel vs sequential LLM calls.

    The EvaluatorAgent uses asyncio.gather() with Semaphore(5) to process
    multiple content items in parallel. This benchmark compares:
    - Sequential: Processing items one at a time
    - Parallel: Processing items concurrently with semaphore

    Expected improvement: 50-70% reduction in total time for multiple items.
    """

    @pytest.fixture
    def content_items(self) -> list[dict[str, Any]]:
        return [
            {
                "url": f"https://example.com/article{i}",
                "content": {
                    "text": (
                        f"Article {i} content about AI startup ideas and machine learning applications. "
                        f"This is a detailed discussion of innovative product concepts for entrepreneurs. "
                        f"The article explores various AI-powered solutions and their market potential. "
                        f"Entrepreneurs can leverage these insights to build successful AI products."
                    )
                }
            }
            for i in range(5)
        ]

    @pytest.fixture
    def evaluator_input(self, content_items: list[dict[str, Any]]) -> EvaluatorInput:
        return EvaluatorInput(
            run_task_id="test-perf-eval",
            iteration_number=1,
            extracted_content=content_items,
        )

    @pytest.mark.benchmark
    def test_evaluator_sequential_llm_calls(
        self,
        benchmark,
        mock_db_path: str,
        evaluator_input: EvaluatorInput,
        mock_criteria: dict[str, Any],
        sample_idea_response: list[dict[str, Any]],
    ) -> None:
        with patch("agents.evaluator.MetaLearningAgent") as mock_meta_class, \
             patch("agents.evaluator.async_llm_complete_json") as mock_llm:
            
            mock_meta_instance = MagicMock()
            mock_meta_instance.research_startup_criteria.return_value = mock_criteria
            mock_meta_class.return_value = mock_meta_instance
            
            async def sequential_llm_call(*args, **kwargs):
                await asyncio.sleep(0.01)
                return sample_idea_response
            
            mock_llm.side_effect = sequential_llm_call

            def run_sequential():
                evaluator = EvaluatorAgent(db_path=mock_db_path, max_concurrent=1)
                return asyncio.run(evaluator.evaluate(evaluator_input))

            result = benchmark(run_sequential)
            assert len(result.ideas) == 5

    @pytest.mark.benchmark
    def test_evaluator_parallel_llm_calls(
        self,
        benchmark,
        mock_db_path: str,
        evaluator_input: EvaluatorInput,
        mock_criteria: dict[str, Any],
        sample_idea_response: list[dict[str, Any]],
    ) -> None:
        with patch("agents.evaluator.MetaLearningAgent") as mock_meta_class, \
             patch("agents.evaluator.async_llm_complete_json") as mock_llm:
            
            mock_meta_instance = MagicMock()
            mock_meta_instance.research_startup_criteria.return_value = mock_criteria
            mock_meta_class.return_value = mock_meta_instance
            
            async def parallel_llm_call(*args, **kwargs):
                await asyncio.sleep(0.01)
                return sample_idea_response
            
            mock_llm.side_effect = parallel_llm_call

            def run_parallel():
                evaluator = EvaluatorAgent(db_path=mock_db_path, max_concurrent=5)
                return asyncio.run(evaluator.evaluate(evaluator_input))

            result = benchmark(run_parallel)
            assert len(result.ideas) == 5

    @pytest.mark.benchmark
    def test_evaluator_parallel_improvement_ratio(
        self,
        mock_db_path: str,
        evaluator_input: EvaluatorInput,
        mock_criteria: dict[str, Any],
        sample_idea_response: list[dict[str, Any]],
    ) -> None:
        with patch("agents.evaluator.MetaLearningAgent") as mock_meta_class, \
             patch("agents.evaluator.async_llm_complete_json") as mock_llm:
            
            mock_meta_instance = MagicMock()
            mock_meta_instance.research_startup_criteria.return_value = mock_criteria
            mock_meta_class.return_value = mock_meta_instance
            
            async def sequential_llm_call(*args, **kwargs):
                await asyncio.sleep(0.02)
                return sample_idea_response
            
            mock_llm.side_effect = sequential_llm_call
            
            evaluator_seq = EvaluatorAgent(db_path=mock_db_path, max_concurrent=1)
            start_seq = time.perf_counter()
            asyncio.run(evaluator_seq.evaluate(evaluator_input))
            time_seq = time.perf_counter() - start_seq
            
            mock_meta_instance.reset_mock()
            
            async def parallel_llm_call(*args, **kwargs):
                await asyncio.sleep(0.02)
                return sample_idea_response
            
            mock_llm.side_effect = parallel_llm_call
            
            evaluator_par = EvaluatorAgent(db_path=mock_db_path, max_concurrent=5)
            start_par = time.perf_counter()
            asyncio.run(evaluator_par.evaluate(evaluator_input))
            time_par = time.perf_counter() - start_par
            
            improvement = (time_seq - time_par) / time_seq
            
            assert improvement >= 0.5, (
                f"Expected at least 50% improvement, got {improvement*100:.1f}% "
                f"(sequential: {time_seq*1000:.1f}ms, parallel: {time_par*1000:.1f}ms)"
            )


# ==============================================================================
# Researcher Benchmarks
# ==============================================================================

class TestResearcherBenchmarks:
    """Benchmarks for ResearcherAgent parallel vs sequential searches.

    The ResearcherAgent uses asyncio.gather() with Semaphore(3) to execute
    multiple DuckDuckGo searches concurrently. This benchmark compares:
    - Sequential: Searches executed one at a time
    - Parallel: Searches executed concurrently with semaphore

    Expected improvement: 50-70% reduction in total search time.
    """

    @pytest.fixture
    def planner_output(self) -> PlannerOutput:
        return PlannerOutput(
            search_queries=[
                "AI startup ideas",
                "machine learning business opportunities",
                "AI entrepreneur trends 2024",
            ],
            target_sources=["techcrunch.com", "venturebeat.com"],
            scraping_depth=2,
            filters={"exclude_domains": ["facebook.com"]},
        )

    @pytest.fixture
    def researcher_input(self, planner_output: PlannerOutput) -> ResearcherInput:
        return ResearcherInput(
            run_task_id="test-perf-research",
            iteration_number=1,
            search_plan=planner_output,
        )

    @pytest.mark.benchmark
    def test_researcher_sequential_searches(
        self,
        benchmark,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_results: list[dict[str, Any]],
    ) -> None:
        with patch("agents.researcher.filter_new_urls") as mock_filter, \
             patch("agents.researcher.mark_sources_status") as mock_mark, \
             patch("agents.researcher.DDGS_AVAILABLE", True):
            
            mock_filter.return_value = {
                "keep_urls": [r["href"] for r in ddg_results[:3]],
                "skipped_urls": [],
            }
            
            mock_ddgs_instance = MagicMock()
            
            def sync_search_sequential(query, max_results=10):
                time.sleep(0.01)
                return ddg_results
            
            mock_ddgs_instance.text = sync_search_sequential
            DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
            DDGS.return_value.__exit__ = MagicMock(return_value=False)

            def run_sequential():
                researcher = ResearcherAgent(db_path=mock_db_path, max_concurrent=1)
                return asyncio.run(researcher.research(researcher_input))

            result = benchmark(run_sequential)
            assert len(result.candidate_urls) == 3

    @pytest.mark.benchmark
    def test_researcher_parallel_searches(
        self,
        benchmark,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_results: list[dict[str, Any]],
    ) -> None:
        with patch("agents.researcher.filter_new_urls") as mock_filter, \
             patch("agents.researcher.mark_sources_status") as mock_mark, \
             patch("agents.researcher.DDGS_AVAILABLE", True):
            
            mock_filter.return_value = {
                "keep_urls": [r["href"] for r in ddg_results[:3]],
                "skipped_urls": [],
            }
            
            mock_ddgs_instance = MagicMock()
            
            def sync_search_parallel(query, max_results=10):
                time.sleep(0.01)
                return ddg_results
            
            mock_ddgs_instance.text = sync_search_parallel
            DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
            DDGS.return_value.__exit__ = MagicMock(return_value=False)

            def run_parallel():
                researcher = ResearcherAgent(db_path=mock_db_path, max_concurrent=3)
                return asyncio.run(researcher.research(researcher_input))

            result = benchmark(run_parallel)
            assert len(result.candidate_urls) == 3

    @pytest.mark.benchmark
    def test_researcher_parallel_improvement_ratio(
        self,
        mock_db_path: str,
        researcher_input: ResearcherInput,
        ddg_results: list[dict[str, Any]],
    ) -> None:
        with patch("agents.researcher.filter_new_urls") as mock_filter, \
             patch("agents.researcher.mark_sources_status") as mock_mark, \
             patch("agents.researcher.DDGS_AVAILABLE", True):
            
            mock_filter.return_value = {
                "keep_urls": [r["href"] for r in ddg_results[:3]],
                "skipped_urls": [],
            }
            
            mock_ddgs_instance_seq = MagicMock()
            
            def sync_search_seq(query, max_results=10):
                time.sleep(0.02)
                return ddg_results
            
            mock_ddgs_instance_seq.text = sync_search_seq
            DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance_seq)
            DDGS.return_value.__exit__ = MagicMock(return_value=False)
            
            researcher_seq = ResearcherAgent(db_path=mock_db_path, max_concurrent=1)
            start_seq = time.perf_counter()
            asyncio.run(researcher_seq.research(researcher_input))
            time_seq = time.perf_counter() - start_seq
            
            mock_ddgs_instance_par = MagicMock()
            
            def sync_search_par(query, max_results=10):
                time.sleep(0.02)
                return ddg_results
            
            mock_ddgs_instance_par.text = sync_search_par
            DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance_par)
            DDGS.return_value.__exit__ = MagicMock(return_value=False)
            
            researcher_par = ResearcherAgent(db_path=mock_db_path, max_concurrent=3)
            start_par = time.perf_counter()
            asyncio.run(researcher_par.research(researcher_input))
            time_par = time.perf_counter() - start_par
            
            improvement = (time_seq - time_par) / time_seq
            
            assert improvement >= 0.5, (
                f"Expected at least 50% improvement, got {improvement*100:.1f}% "
                f"(sequential: {time_seq*1000:.1f}ms, parallel: {time_par*1000:.1f}ms)"
            )


# ==============================================================================
# Scraper Benchmarks
# ==============================================================================

class TestScraperBenchmarks:
    """Benchmarks for ScraperAgent concurrent vs sequential fetching.

    The ScraperAgent uses asyncio.gather() with Semaphore(3) to fetch
    multiple URLs concurrently. This benchmark compares:
    - Sequential: URLs fetched one at a time
    - Concurrent: URLs fetched concurrently with semaphore

    Expected improvement: 50-70% reduction in total fetch time.
    """

    @pytest.fixture
    def scraper_input(self) -> ScraperInput:
        return ScraperInput(
            run_task_id="test-perf-scrape",
            iteration_number=1,
            urls=[
                "https://example.com/article1",
                "https://example.com/article2",
                "https://example.com/article3",
                "https://example.com/article4",
                "https://example.com/article5",
            ],
            throttle_seconds=300,
        )

    @pytest.mark.benchmark
    def test_scraper_sequential_fetching(
        self,
        benchmark,
        mock_db_path: str,
        scraper_input: ScraperInput,
        html_content: str,
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_db_functions["can_scrape"].return_value = (True, 0)
        
        mock_trafilatura.fetch_url.return_value = html_content
        mock_trafilatura.extract.return_value = "Extracted content from the page."
        
        mock_soup = MagicMock()
        mock_soup.title.string = "Test Article"
        mock_bs4.BeautifulSoup.return_value = mock_soup

        def run_sequential():
            scraper = ScraperAgent(db_path=mock_db_path, max_concurrent=1)
            return asyncio.run(scraper.scrape(scraper_input))

        result = benchmark(run_sequential)
        assert len(result.extracted) == 5

    @pytest.mark.benchmark
    def test_scraper_concurrent_fetching(
        self,
        benchmark,
        mock_db_path: str,
        scraper_input: ScraperInput,
        html_content: str,
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_db_functions["can_scrape"].return_value = (True, 0)
        
        mock_trafilatura.fetch_url.return_value = html_content
        mock_trafilatura.extract.return_value = "Extracted content from the page."
        
        mock_soup = MagicMock()
        mock_soup.title.string = "Test Article"
        mock_bs4.BeautifulSoup.return_value = mock_soup

        def run_concurrent():
            scraper = ScraperAgent(db_path=mock_db_path, max_concurrent=3)
            return asyncio.run(scraper.scrape(scraper_input))

        result = benchmark(run_concurrent)
        assert len(result.extracted) == 5

    @pytest.mark.benchmark
    def test_scraper_concurrent_improvement_ratio(
        self,
        mock_db_path: str,
        scraper_input: ScraperInput,
        html_content: str,
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        mock_db_functions["can_scrape"].return_value = (True, 0)
        
        mock_soup = MagicMock()
        mock_soup.title.string = "Test Article"
        mock_bs4.BeautifulSoup.return_value = mock_soup
        
        mock_trafilatura.fetch_url.return_value = html_content
        mock_trafilatura.extract.return_value = "Content."
        
        scraper_seq = ScraperAgent(db_path=mock_db_path, max_concurrent=1)
        start_seq = time.perf_counter()
        asyncio.run(scraper_seq.scrape(scraper_input))
        time_seq = time.perf_counter() - start_seq
        
        scraper_par = ScraperAgent(db_path=mock_db_path, max_concurrent=3)
        start_par = time.perf_counter()
        asyncio.run(scraper_par.scrape(scraper_input))
        time_par = time.perf_counter() - start_par
        
        improvement = (time_seq - time_par) / time_seq
        
        assert improvement >= 0.5, (
            f"Expected at least 50% improvement, got {improvement*100:.1f}% "
            f"(sequential: {time_seq*1000:.1f}ms, concurrent: {time_par*1000:.1f}ms)"
        )


# ==============================================================================
# Baseline Comparison Benchmarks
# ==============================================================================

class TestBaselineComparison:
    """Baseline comparison benchmarks to track performance over time.

    These benchmarks establish baseline performance metrics that can be
    compared across different runs to detect performance regressions.
    """

    @pytest.mark.benchmark
    def test_evaluator_baseline(
        self,
        benchmark,
        mock_db_path: str,
        mock_criteria: dict[str, Any],
        sample_idea_response: list[dict[str, Any]],
    ) -> None:
        content_items = [
            {
                "url": f"https://example.com/article{i}",
                "content": {
                    "text": (
                        f"Article {i} about AI startups and machine learning. "
                        f"This comprehensive discussion covers innovative product concepts. "
                        f"Entrepreneurs can leverage AI technology to build successful businesses. "
                        f"The market potential for AI solutions continues to grow rapidly."
                    )
                }
            }
            for i in range(3)
        ]
        
        evaluator_input = EvaluatorInput(
            run_task_id="test-baseline-eval",
            iteration_number=1,
            extracted_content=content_items,
        )
        
        with patch("agents.evaluator.MetaLearningAgent") as mock_meta_class, \
             patch("agents.evaluator.async_llm_complete_json") as mock_llm:
            
            mock_meta_instance = MagicMock()
            mock_meta_instance.research_startup_criteria.return_value = mock_criteria
            mock_meta_class.return_value = mock_meta_instance
            mock_llm.return_value = sample_idea_response

            def run_baseline():
                evaluator = EvaluatorAgent(db_path=mock_db_path, max_concurrent=5)
                return asyncio.run(evaluator.evaluate(evaluator_input))

            result = benchmark(run_baseline)
            assert len(result.ideas) == 3

    @pytest.mark.benchmark
    def test_researcher_baseline(
        self,
        benchmark,
        mock_db_path: str,
        ddg_results: list[dict[str, Any]],
    ) -> None:
        planner_output = PlannerOutput(
            search_queries=["AI startups", "ML business"],
            target_sources=["techcrunch.com"],
            scraping_depth=2,
            filters={},
        )
        
        researcher_input = ResearcherInput(
            run_task_id="test-baseline-research",
            iteration_number=1,
            search_plan=planner_output,
        )
        
        with patch("agents.researcher.filter_new_urls") as mock_filter, \
             patch("agents.researcher.mark_sources_status") as mock_mark, \
             patch("agents.researcher.DDGS_AVAILABLE", True):
            
            mock_filter.return_value = {
                "keep_urls": [r["href"] for r in ddg_results[:2]],
                "skipped_urls": [],
            }
            
            mock_ddgs_instance = MagicMock()
            mock_ddgs_instance.text.return_value = ddg_results
            DDGS.return_value.__enter__ = MagicMock(return_value=mock_ddgs_instance)
            DDGS.return_value.__exit__ = MagicMock(return_value=False)

            def run_baseline():
                researcher = ResearcherAgent(db_path=mock_db_path, max_concurrent=3)
                return asyncio.run(researcher.research(researcher_input))

            result = benchmark(run_baseline)
            assert len(result.candidate_urls) == 2

    @pytest.mark.benchmark
    def test_scraper_baseline(
        self,
        benchmark,
        mock_db_path: str,
        html_content: str,
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        scraper_input = ScraperInput(
            run_task_id="test-baseline-scrape",
            iteration_number=1,
            urls=[
                "https://example.com/article1",
                "https://example.com/article2",
                "https://example.com/article3",
            ],
            throttle_seconds=300,
        )
        
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura.fetch_url.return_value = html_content
        mock_trafilatura.extract.return_value = "Extracted content."
        
        mock_soup = MagicMock()
        mock_soup.title.string = "Test Article"
        mock_bs4.BeautifulSoup.return_value = mock_soup

        def run_baseline():
            scraper = ScraperAgent(db_path=mock_db_path, max_concurrent=3)
            return asyncio.run(scraper.scrape(scraper_input))

        result = benchmark(run_baseline)
        assert len(result.extracted) == 3