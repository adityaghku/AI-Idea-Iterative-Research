"""Fixtures package for Idea Harvester tests."""
from tests.fixtures.llm_fixtures import (
    valid_idea_response,
    invalid_idea_response,
    multiple_ideas_response,
    low_score_idea_response,
)
from tests.fixtures.ddg_fixtures import (
    ddg_search_results,
    ddg_search_results_with_titles,
    empty_ddg_results,
)
from tests.fixtures.http_fixtures import (
    simple_html_content,
    complex_html_content,
    malformed_html_content,
    minimal_html_content,
    rich_article_html,
)

__all__ = [
    # LLM fixtures
    "valid_idea_response",
    "invalid_idea_response",
    "multiple_ideas_response",
    "low_score_idea_response",
    # DDG fixtures
    "ddg_search_results",
    "ddg_search_results_with_titles",
    "empty_ddg_results",
    # HTTP fixtures
    "simple_html_content",
    "complex_html_content",
    "malformed_html_content",
    "minimal_html_content",
    "rich_article_html",
]
