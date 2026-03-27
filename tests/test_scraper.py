"""Unit tests for ScraperAgent."""
from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import MagicMock, patch, call
from typing import Any

import pytest

# Mock trafilatura before importing scraper
mock_trafilatura = MagicMock()
mock_trafilatura.fetch_url = MagicMock()
mock_trafilatura.extract = MagicMock()
mock_trafilatura.use_config = MagicMock()
mock_trafilatura_config = MagicMock()
mock_trafilatura.use_config.return_value = mock_trafilatura_config
sys.modules["trafilatura"] = mock_trafilatura
sys.modules["trafilatura.settings"] = MagicMock()

# Mock requests/beautifulsoup as fallback
mock_requests = MagicMock()
mock_requests.get = MagicMock()
sys.modules["requests"] = mock_requests

# Mock BeautifulSoup (used by both trafilatura and requests paths)
mock_bs4 = MagicMock()
mock_beautifulsoup = MagicMock()
sys.modules["bs4"] = mock_bs4
sys.modules["bs4"].BeautifulSoup = mock_beautifulsoup

from agents.scraper import ScraperAgent, TRAFILATURA_AVAILABLE, REQUESTS_AVAILABLE
from agents.config import ScraperInput, ScraperOutput


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_db_path(tmp_path) -> str:
    """Provide a temporary database path for testing."""
    return str(tmp_path / "test_scraper.db")


@pytest.fixture
def scraper_input(sample_urls: list[str]) -> ScraperInput:
    """Return a sample ScraperInput for testing."""
    return ScraperInput(
        run_task_id="test-run-123",
        iteration_number=1,
        urls=sample_urls,
        throttle_seconds=300,
    )


@pytest.fixture
def mock_db_functions():
    """Mock database utility functions."""
    with patch("agents.scraper.can_scrape") as mock_can_scrape, \
         patch("agents.scraper.update_scraper_timestamp") as mock_update, \
         patch("agents.scraper.mark_sources_status") as mock_mark:
        yield {
            "can_scrape": mock_can_scrape,
            "update_scraper_timestamp": mock_update,
            "mark_sources_status": mock_mark,
        }


@pytest.fixture
def mock_trafilatura_module():
    """Mock trafilatura module for testing."""
    with patch("agents.scraper.TRAFILATURA_AVAILABLE", True), \
         patch("agents.scraper.fetch_url") as mock_fetch, \
         patch("agents.scraper.extract") as mock_extract, \
         patch("agents.scraper.use_config") as mock_use_config:
        mock_config = MagicMock()
        mock_use_config.return_value = mock_config
        yield {
            "fetch_url": mock_fetch,
            "extract": mock_extract,
            "use_config": mock_use_config,
            "config": mock_config,
        }


@pytest.fixture
def mock_requests_module():
    """Mock requests module for fallback testing."""
    with patch("agents.scraper.REQUESTS_AVAILABLE", True), \
         patch("agents.scraper.requests") as mock_requests:
        yield mock_requests


# ==============================================================================
# Test scrape() Method - Normal Cases
# ==============================================================================

class TestScrapeNormalCases:
    """Tests for scrape() method with normal operation."""

    def test_scrape_with_valid_urls(
        self,
        mock_db_path: str,
        scraper_input: ScraperInput,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() extracts content from valid URLs."""
        # Setup mocks
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "This is a paragraph with some content. Another paragraph with more text."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert isinstance(output, ScraperOutput)
        assert len(output.extracted) == 3  # 3 URLs in sample_urls
        assert output.scrape_quality > 0
        assert output.scrape_failures == []
        assert output.dedup_removed_count == 0

        # Verify database calls
        mock_db_functions["can_scrape"].assert_called_once()
        mock_db_functions["update_scraper_timestamp"].assert_called_once()
        mock_db_functions["mark_sources_status"].assert_called()

    def test_scrape_limits_to_5_urls(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() limits processing to 5 URLs per batch."""
        # Setup - provide 10 URLs
        urls = [f"https://example.com/article{i}" for i in range(10)]
        scraper_input = ScraperInput(
            run_task_id="test-run-123",
            iteration_number=1,
            urls=urls,
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content extracted from page."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - only 5 URLs processed
        assert len(output.extracted) == 5
        assert output.dedup_removed_count == 5  # 10 - 5 = 5 removed

    def test_scrape_quality_score_calculation(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        rich_article_html: str,
    ) -> None:
        """Test scrape_quality calculation with content richness bonus."""
        # Setup - rich content (>1000 chars) should get bonus
        scraper_input = ScraperInput(
            run_task_id="test-run-quality",
            iteration_number=1,
            urls=["https://example.com/article1"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = rich_article_html
        
        # Rich content > 1000 chars
        rich_content = "A" * 1500
        mock_trafilatura_module["extract"].return_value = rich_content

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - quality should be 1.0 (success rate) + 0.1 (bonus) = 1.1, capped at 1.0
        assert output.scrape_quality == 1.0

    def test_scrape_quality_score_no_bonus_for_short_content(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape_quality without bonus for short content."""
        # Setup - short content (<1000 chars avg)
        scraper_input = ScraperInput(
            run_task_id="test-run-short",
            iteration_number=1,
            urls=["https://example.com/article1", "https://example.com/article2"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        # Short content
        mock_trafilatura_module["extract"].return_value = "Short content here."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - quality should be 1.0 (success rate), no bonus
        assert output.scrape_quality == 1.0

    def test_scrape_partial_success(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() with some URLs succeeding and some failing."""
        # Setup
        urls = ["https://example.com/success", "https://example.com/fail"]
        scraper_input = ScraperInput(
            run_task_id="test-run-partial",
            iteration_number=1,
            urls=urls,
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        
        # First URL succeeds, second fails
        call_count = [0]
        def side_effect_fetch(url, config=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return simple_html_content
            return None  # Simulate failure

        mock_trafilatura_module["fetch_url"].side_effect = side_effect_fetch
        mock_trafilatura_module["extract"].return_value = "Content extracted."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 1
        assert len(output.scrape_failures) == 1
        assert "fail" in output.scrape_failures[0]
        # Quality: 1 success / 2 total = 0.5
        assert output.scrape_quality == 0.5


# ==============================================================================
# Test Rate Limiting / can_scrape()
# ==============================================================================

class TestRateLimiting:
    """Tests for rate limiting via can_scrape()."""

    def test_scrape_waits_when_throttled(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() waits when can_scrape returns False."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-throttled",
            iteration_number=1,
            urls=["https://example.com/article1"],
            throttle_seconds=300,
        )
        # First call returns False (throttled), second call would return True
        mock_db_functions["can_scrape"].return_value = (False, 5)  # Wait 5 seconds
        
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content."

        # Execute with mocked asyncio.sleep
        with patch("agents.scraper.asyncio.sleep") as mock_sleep:
            scraper = ScraperAgent(db_path=mock_db_path)
            output = asyncio.run(scraper.scrape(scraper_input))

            # Assert - sleep was called with wait time
            mock_sleep.assert_called_once_with(5)

        assert len(output.extracted) == 1

    def test_scrape_proceeds_immediately_when_not_throttled(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() proceeds immediately when can_scrape returns True."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-not-throttled",
            iteration_number=1,
            urls=["https://example.com/article1"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content."

        # Execute with mocked asyncio.sleep
        with patch("agents.scraper.asyncio.sleep") as mock_sleep:
            scraper = ScraperAgent(db_path=mock_db_path)
            output = asyncio.run(scraper.scrape(scraper_input))

            # Assert - sleep should NOT be called
            mock_sleep.assert_not_called()

        assert len(output.extracted) == 1

    def test_can_scrape_returns_true_when_no_previous_scrape(
        self,
        mock_db_path: str,
    ) -> None:
        """Test can_scrape utility returns True when no previous scrape."""
        with patch("agents.utils.call_db") as mock_call_db:
            mock_call_db.return_value = None  # No previous timestamp
            
            from agents.utils import can_scrape
            result, wait_time = can_scrape(mock_db_path, "test-run", 300)
            
            assert result is True
            assert wait_time == 0

    def test_can_scrape_returns_false_when_within_cooldown(
        self,
        mock_db_path: str,
    ) -> None:
        """Test can_scrape utility returns False when within cooldown period."""
        with patch("agents.utils.call_db") as mock_call_db, \
             patch("agents.utils.get_current_epoch") as mock_epoch:
            # Last scrape was 100 seconds ago, cooldown is 300
            mock_call_db.return_value = {"epoch": 1000}
            mock_epoch.return_value = 1100  # 100 seconds later
            
            from agents.utils import can_scrape
            result, wait_time = can_scrape(mock_db_path, "test-run", 300)
            
            assert result is False
            assert wait_time == 200  # 300 - 100 = 200 remaining


# ==============================================================================
# Test Content Extraction
# ==============================================================================

class TestContentExtraction:
    """Tests for content extraction methods."""

    def test_trafilatura_extract_success(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        rich_article_html: str,
    ) -> None:
        """Test _trafilatura_extract extracts content correctly."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-extract",
            iteration_number=1,
            urls=["https://example.com/article"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = rich_article_html
        
        extracted_text = "This is the main article content extracted by trafilatura."
        mock_trafilatura_module["extract"].return_value = extracted_text

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 1
        assert output.extracted[0]["content"]["text"] == extracted_text
        assert output.extracted[0]["content"]["metadata"]["method"] == "trafilatura"

    def test_trafilatura_extract_extracts_title(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test _trafilatura_extract extracts title from HTML."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-title",
            iteration_number=1,
            urls=["https://example.com/article"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content text."

        # Mock BeautifulSoup for title extraction
        with patch("agents.scraper.BeautifulSoup") as mock_bs:
            mock_soup = MagicMock()
            mock_soup.title.string = "Simple Test Page"
            mock_bs.return_value = mock_soup

            # Execute
            scraper = ScraperAgent(db_path=mock_db_path)
            output = asyncio.run(scraper.scrape(scraper_input))

            # Assert
            assert output.extracted[0]["content"]["title"] == "Simple Test Page"

    def test_requests_fallback_when_trafilatura_unavailable(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test fallback to requests+BeautifulSoup when trafilatura unavailable."""
        # Setup - simulate trafilatura not available
        with patch("agents.scraper.TRAFILATURA_AVAILABLE", False), \
             patch("agents.scraper.REQUESTS_AVAILABLE", True), \
             patch("agents.scraper.requests") as mock_requests, \
             patch("agents.scraper.BeautifulSoup") as mock_bs:
            
            scraper_input = ScraperInput(
                run_task_id="test-run-fallback",
                iteration_number=1,
                urls=["https://example.com/article"],
                throttle_seconds=300,
            )
            mock_db_functions["can_scrape"].return_value = (True, 0)
            
            # Mock requests response
            mock_response = MagicMock()
            mock_response.text = simple_html_content
            mock_response.raise_for_status = MagicMock()
            mock_requests.get.return_value = mock_response

            # Mock BeautifulSoup for content extraction
            mock_soup = MagicMock()
            mock_soup.title.string = "Test Title"
            mock_soup.get_text.return_value = "Extracted content from requests fallback."
            mock_bs.return_value = mock_soup

            # Execute
            scraper = ScraperAgent(db_path=mock_db_path)
            output = asyncio.run(scraper.scrape(scraper_input))

            # Assert
            assert len(output.extracted) == 1
            assert output.extracted[0]["content"]["metadata"]["method"] == "requests"
            mock_requests.get.assert_called_once()


# ==============================================================================
# Test Edge Cases
# ==============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_scrape_no_content_extracted(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() handles URLs where no content is extracted."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-no-content",
            iteration_number=1,
            urls=["https://example.com/empty"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = None  # No content extracted

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 0
        assert len(output.scrape_failures) == 1
        assert "No main content extracted" in output.scrape_failures[0]
        assert output.scrape_quality == 0.0

    def test_scrape_empty_text_in_content(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() handles content with empty text field."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-empty-text",
            iteration_number=1,
            urls=["https://example.com/empty-text"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = ""  # Empty string

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 0
        assert len(output.scrape_failures) == 1

    def test_scrape_malformed_html(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        malformed_html_content: str,
    ) -> None:
        """Test scrape() handles malformed HTML gracefully."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-malformed",
            iteration_number=1,
            urls=["https://example.com/malformed"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = malformed_html_content
        # BeautifulSoup should still parse malformed HTML
        mock_trafilatura_module["extract"].return_value = "Unclosed tag test Missing closing paragraph"

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - should still extract something from malformed HTML
        assert len(output.extracted) == 1
        assert "Unclosed" in output.extracted[0]["content"]["text"]

    def test_scrape_fetch_failure(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
    ) -> None:
        """Test scrape() handles fetch failures (e.g., network error)."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-fetch-fail",
            iteration_number=1,
            urls=["https://example.com/fail"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = None  # Fetch failed

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 0
        assert len(output.scrape_failures) == 1
        assert "Failed to download page" in output.scrape_failures[0]

    def test_scrape_timeout(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
    ) -> None:
        """Test scrape() handles timeout errors."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-timeout",
            iteration_number=1,
            urls=["https://example.com/timeout"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].side_effect = TimeoutError("Request timed out")

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 0
        assert len(output.scrape_failures) == 1
        assert "timeout" in output.scrape_failures[0].lower()

    def test_scrape_empty_urls_list(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
    ) -> None:
        """Test scrape() handles empty URL list."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-empty-urls",
            iteration_number=1,
            urls=[],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 0
        assert len(output.scrape_failures) == 0
        assert output.scrape_quality == 0.0
        assert output.dedup_removed_count == 0

    def test_scrape_all_urls_fail(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
    ) -> None:
        """Test scrape() when all URLs fail."""
        # Setup
        urls = ["https://example.com/fail1", "https://example.com/fail2"]
        scraper_input = ScraperInput(
            run_task_id="test-run-all-fail",
            iteration_number=1,
            urls=urls,
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = None  # All fail

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert
        assert len(output.extracted) == 0
        assert len(output.scrape_failures) == 2
        assert output.scrape_quality == 0.0


# ==============================================================================
# Test Database Integration
# ==============================================================================

class TestDatabaseIntegration:
    """Tests for database function calls."""

    def test_scrape_marks_successful_urls_as_scraped(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() marks successful URLs as 'scraped' in database."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-mark-scraped",
            iteration_number=1,
            urls=["https://example.com/success"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        asyncio.run(scraper.scrape(scraper_input))

        # Assert - mark_sources_status called with 'scraped'
        mark_calls = mock_db_functions["mark_sources_status"].call_args_list
        assert len(mark_calls) >= 1
        
        # Find the call with status='scraped'
        scraped_call = None
        for call_obj in mark_calls:
            if call_obj.kwargs.get("status") == "scraped":
                scraped_call = call_obj
                break
        
        assert scraped_call is not None
        assert "https://example.com/success" in scraped_call.kwargs["urls"]

    def test_scrape_marks_failed_urls(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
    ) -> None:
        """Test scrape() marks failed URLs as 'failed' in database."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-mark-failed",
            iteration_number=1,
            urls=["https://example.com/fail"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = None  # Fail

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        asyncio.run(scraper.scrape(scraper_input))

        # Assert - mark_sources_status called with 'failed'
        mark_calls = mock_db_functions["mark_sources_status"].call_args_list
        
        # Find the call with status='failed'
        failed_call = None
        for call_obj in mark_calls:
            if call_obj.kwargs.get("status") == "failed":
                failed_call = call_obj
                break
        
        assert failed_call is not None
        assert len(failed_call.kwargs["urls"]) >= 1

    def test_scrape_updates_timestamp(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test scrape() updates scraper timestamp after completion."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-timestamp",
            iteration_number=1,
            urls=["https://example.com/article"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        asyncio.run(scraper.scrape(scraper_input))

        # Assert
        mock_db_functions["update_scraper_timestamp"].assert_called_once_with(
            mock_db_path, "test-run-timestamp"
        )


# ==============================================================================
# Test ScraperOutput Structure
# ==============================================================================

class TestScraperOutputStructure:
    """Tests for ScraperOutput structure and methods."""

    def test_scraper_output_to_dict(self) -> None:
        """Test ScraperOutput.to_dict() returns correct structure."""
        output = ScraperOutput(
            extracted=[
                {
                    "url": "https://example.com/article",
                    "content": {
                        "title": "Test Article",
                        "text": "Article content here.",
                        "description": "A test article",
                        "metadata": {"method": "trafilatura"},
                    },
                    "timestamp": 1234567890.0,
                }
            ],
            scrape_quality=0.85,
            scrape_failures=["https://example.com/fail: Timeout"],
            dedup_removed_count=2,
        )

        result = output.to_dict()

        assert "extracted" in result
        assert "scrape_quality" in result
        assert "scrape_failures" in result
        assert "dedup_removed_count" in result
        assert result["scrape_quality"] == 0.85
        assert len(result["extracted"]) == 1
        assert result["extracted"][0]["url"] == "https://example.com/article"

    def test_scraper_output_empty_extracted(self) -> None:
        """Test ScraperOutput with empty extracted list."""
        output = ScraperOutput(
            extracted=[],
            scrape_quality=0.0,
            scrape_failures=["https://example.com/fail: Error"],
            dedup_removed_count=0,
        )

        assert output.extracted == []
        assert output.scrape_quality == 0.0
        assert len(output.scrape_failures) == 1


# ==============================================================================
# Test Import Error Handling
# ==============================================================================

class TestImportErrorHandling:
    """Tests for handling missing scraping libraries."""

    def test_init_raises_when_no_library_available(self, mock_db_path: str) -> None:
        """Test ScraperAgent raises ImportError when no scraping library available."""
        with patch("agents.scraper.TRAFILATURA_AVAILABLE", False), \
             patch("agents.scraper.REQUESTS_AVAILABLE", False):
            with pytest.raises(ImportError, match="No web scraping library available"):
                ScraperAgent(db_path=mock_db_path)

    def test_init_succeeds_with_trafilatura_only(self, mock_db_path: str) -> None:
        """Test ScraperAgent initializes when only trafilatura is available."""
        with patch("agents.scraper.TRAFILATURA_AVAILABLE", True), \
             patch("agents.scraper.REQUESTS_AVAILABLE", False), \
             patch("agents.scraper.fetch_url"), \
             patch("agents.scraper.extract"), \
             patch("agents.scraper.use_config"):
            # Should not raise
            scraper = ScraperAgent(db_path=mock_db_path)
            assert scraper is not None

    def test_init_succeeds_with_requests_only(self, mock_db_path: str) -> None:
        """Test ScraperAgent initializes when only requests is available."""
        with patch("agents.scraper.TRAFILATURA_AVAILABLE", False), \
             patch("agents.scraper.REQUESTS_AVAILABLE", True), \
             patch("agents.scraper.requests"):
            # Should not raise
            scraper = ScraperAgent(db_path=mock_db_path)
            assert scraper is not None


# ==============================================================================
# Test Content Quality Scoring
# ==============================================================================

class TestContentQualityScoring:
    """Tests for content quality score calculation."""

    def test_quality_score_all_success(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test quality score is 1.0 when all URLs succeed."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-all-success",
            iteration_number=1,
            urls=["https://example.com/1", "https://example.com/2"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = simple_html_content
        mock_trafilatura_module["extract"].return_value = "Content."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - 2/2 success = 1.0
        assert output.scrape_quality == 1.0

    def test_quality_score_half_success(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
    ) -> None:
        """Test quality score is 0.5 when half URLs succeed."""
        # Setup
        scraper_input = ScraperInput(
            run_task_id="test-run-half",
            iteration_number=1,
            urls=["https://example.com/success", "https://example.com/fail"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        
        call_count = [0]
        def side_effect_fetch(url, config=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return simple_html_content
            return None

        mock_trafilatura_module["fetch_url"].side_effect = side_effect_fetch
        mock_trafilatura_module["extract"].return_value = "Content."

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - 1/2 success = 0.5
        assert output.scrape_quality == 0.5

    def test_quality_score_with_rich_content_bonus(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        rich_article_html: str,
    ) -> None:
        """Test quality score gets bonus for rich content (>1000 chars avg)."""
        # Setup - 2 URLs, both with rich content
        scraper_input = ScraperInput(
            run_task_id="test-run-rich",
            iteration_number=1,
            urls=["https://example.com/rich1", "https://example.com/rich2"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        mock_trafilatura_module["fetch_url"].return_value = rich_article_html
        
        # Rich content > 1000 chars each
        rich_content = "X" * 2000
        mock_trafilatura_module["extract"].return_value = rich_content

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - base 1.0 + 0.1 bonus = 1.1, capped at 1.0
        assert output.scrape_quality == 1.0

    def test_quality_score_mixed_content_lengths(
        self,
        mock_db_path: str,
        mock_db_functions: dict[str, MagicMock],
        mock_trafilatura_module: dict[str, MagicMock],
        simple_html_content: str,
        rich_article_html: str,
    ) -> None:
        """Test quality score with mixed content lengths."""
        # Setup - 2 URLs: one short, one rich
        scraper_input = ScraperInput(
            run_task_id="test-run-mixed",
            iteration_number=1,
            urls=["https://example.com/short", "https://example.com/rich"],
            throttle_seconds=300,
        )
        mock_db_functions["can_scrape"].return_value = (True, 0)
        
        call_count = [0]
        def side_effect_fetch(url, config=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return simple_html_content
            return rich_article_html

        def side_effect_extract(content, config=None, **kwargs):
            if "Simple" in content:
                return "Short content."
            return "X" * 2000  # Rich content

        mock_trafilatura_module["fetch_url"].side_effect = side_effect_fetch
        mock_trafilatura_module["extract"].side_effect = side_effect_extract

        # Execute
        scraper = ScraperAgent(db_path=mock_db_path)
        output = asyncio.run(scraper.scrape(scraper_input))

        # Assert - avg length = (short + rich) / 2
        # If avg > 1000, bonus applies
        # Short ~15 chars, rich ~2000 chars, avg ~1007 chars -> bonus
        # But we need to check actual calculation
        # Quality = success_rate + (0.1 if avg_length > 1000 else 0)
        # With 2 successes: 1.0 + bonus if applicable
        assert output.scrape_quality >= 1.0  # Capped at 1.0