"""Shared pytest fixtures for Idea Harvester tests."""
import sys
from unittest.mock import MagicMock

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

import logging
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Import fixtures from llm_fixtures.py
from tests.fixtures.llm_fixtures import (  # noqa: F401
    valid_idea_response,
    multiple_ideas_response,
    low_score_idea_response,
    invalid_idea_response,
    empty_idea_response,
    partial_score_idea_response,
)
from agents.cache import ResponseCache

# Import fixtures from ddg_fixtures.py
from tests.fixtures.ddg_fixtures import (  # noqa: F401
    ddg_search_results,
    ddg_search_results_with_titles,
    empty_ddg_results,
)

# Import fixtures from http_fixtures.py
from tests.fixtures.http_fixtures import (  # noqa: F401
    simple_html_content,
    complex_html_content,
    malformed_html_content,
    minimal_html_content,
    rich_article_html,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_db_path(temp_dir: Path) -> Path:
    """Provide a temporary database path for testing."""
    return temp_dir / "test_idea_harvester.db"


@pytest.fixture
def sample_ideas() -> list[dict]:
    """Sample ideas data for testing."""
    return [
        {
            "idea_title": "Test Idea 1",
            "idea_summary": "A test idea for unit testing",
            "source_urls": ["https://example.com/1"],
            "score": 75,
            "score_breakdown": {
                "novelty": 80,
                "feasibility": 70,
                "market_potential": 75,
            },
            "evaluator_explain": "Test evaluation",
            "idea_payload": {},
        },
        {
            "idea_title": "Test Idea 2",
            "idea_summary": "Another test idea",
            "source_urls": ["https://example.com/2"],
            "score": 60,
            "score_breakdown": {
                "novelty": 50,
                "feasibility": 70,
                "market_potential": 60,
            },
            "evaluator_explain": "Another test",
            "idea_payload": {},
        },
    ]


@pytest.fixture
def sample_urls() -> list[str]:
    """Sample URLs for testing scraper functionality."""
    return [
        "https://example.com/article1",
        "https://example.com/article2",
        "https://example.com/article3",
    ]


@pytest.fixture(autouse=True)
def setup_logging(caplog: pytest.LogCaptureFixture) -> Generator[None, None, None]:
    """Configure logging for all tests."""
    caplog.set_level(logging.INFO)
    yield


@pytest.fixture(autouse=True)
def reset_response_cache() -> Generator[None, None, None]:
    """Reset ResponseCache singleton before each test."""
    ResponseCache.reset()
    yield
    ResponseCache.reset()


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent
