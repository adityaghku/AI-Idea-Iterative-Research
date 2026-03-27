"""Mock DuckDuckGo search results for researcher agent testing."""
import pytest


@pytest.fixture
def ddg_search_results():
    """Return DuckDuckGo search results with href keys for URL extraction.

    Matches the format returned by ddgs.text() and used by ResearcherAgent._search().
    """
    return [
        {"href": "https://techcrunch.com/2024/01/15/ai-startup-raises-funding"},
        {"href": "https://www.theverge.com/2024/01/14/new-ai-framework-released"},
        {"href": "https://arstechnica.com/ai-research-breakthrough-2024"},
        {"href": "https://venturebeat.com/ai-transforming-healthcare"},
        {"href": "https://hackernews.com/show?fn=ai-startup-idea"},
    ]


@pytest.fixture
def ddg_search_results_with_titles():
    """Return full DuckDuckGo search results with titles and snippets.

    Includes all fields that ddgs.text() returns: href, title, body.
    Useful for testing scraper targeting logic or result parsing beyond URLs.
    """
    return [
        {
            "href": "https://techcrunch.com/2024/01/15/ai-startup-raises-funding",
            "title": "AI Startup Raises $50M to Build Autonomous Agents",
            "body": "The company plans to use the funding to expand its AI agent platform..."
        },
        {
            "href": "https://www.theverge.com/2024/01/14/new-ai-framework-released",
            "title": "New Open Source AI Framework Aims to Simplify Agent Development",
            "body": "Developers can now build AI agents with fewer lines of code..."
        },
        {
            "href": "https://arstechnica.com/ai-research-breakthrough-2024",
            "title": "Researchers Achieve Breakthrough in Multimodal AI Reasoning",
            "body": "The new approach combines vision and language for better understanding..."
        },
        {
            "href": "https://venturebeat.com/ai-transforming-healthcare",
            "title": "How AI is Transforming Healthcare Diagnostics",
            "body": "Machine learning models are helping doctors detect diseases earlier..."
        },
        {
            "href": "https://hackernews.com/show?fn=ai-startup-idea",
            "title": "Ask HN: AI Startup Ideas for 2024",
            "body": "Looking for feedback on my AI startup idea in the productivity space..."
        },
        {
            "href": "https://medium.com/ai-insights/best-ai-business-ideas",
            "title": "10 Profitable AI Business Ideas for Entrepreneurs",
            "body": "A comprehensive guide to building successful AI-powered businesses..."
        },
    ]


@pytest.fixture
def empty_ddg_results():
    """Return empty list to simulate no search results.

    Useful for edge case testing: handling queries with no matches,
    network errors, or rate limiting scenarios.
    """
    return []
