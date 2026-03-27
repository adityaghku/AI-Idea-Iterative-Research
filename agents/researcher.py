"""Researcher agent - finds candidate URLs using DuckDuckGo web search."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .config import ResearcherInput, ResearcherOutput, PlannerOutput
from .utils import (
    filter_new_urls,
    mark_sources_status,
    get_current_epoch,
)
from .logger import get_logger, log_structured

# Try to import DuckDuckGo search
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError as e:
    DDGS_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(f"ddgs not available: {e}. Web search functionality will be limited.")


class ResearcherAgent:
    """Discovers candidate URLs from web search queries using DuckDuckGo."""

    def __init__(self, db_path: str = "idea_harvester.sqlite", max_concurrent: int = 3):
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore | None = None
        self.logger = get_logger()
        if not DDGS_AVAILABLE:
            raise ImportError(
                "DuckDuckGo search not available. "
                "Install with: pip install duckduckgo-search"
            )

    async def research(self, input_data: ResearcherInput) -> ResearcherOutput:
        """Find candidate URLs based on search plan using DuckDuckGo search."""
        self.logger.info(f"[iter {input_data.iteration_number}] Researcher starting")

        search_plan = input_data.search_plan
        if isinstance(search_plan, dict):
            search_plan = PlannerOutput(**search_plan)

        # Initialize semaphore for rate limiting
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        semaphore = self._semaphore

        async def search_with_semaphore(query: str) -> tuple[str, list[str] | Exception]:
            """Execute search with semaphore for rate limiting."""
            async with semaphore:
                try:
                    urls = await self._search(query, max_results=10)
                    return (query, urls)
                except Exception as e:
                    return (query, e)

        # Execute all searches in parallel with semaphore
        tasks = [search_with_semaphore(query) for query in search_plan.search_queries]
        results = await asyncio.gather(*tasks)

        all_urls = []
        coverage_notes = []

        for query, result in results:
            if isinstance(result, Exception):
                coverage_notes.append(f"Query '{query}': failed - {str(result)}")
                self.logger.error(f"[iter {input_data.iteration_number}] Query failed: {result}")
            else:
                all_urls.extend(result)
                coverage_notes.append(f"Query '{query}': found {len(result)} URLs")
                self.logger.info(f"[iter {input_data.iteration_number}] Query returned {len(result)} URLs")
                for url in result:
                    log_structured("url_discovered", url=url, source_query=query, iteration=input_data.iteration_number)

        unique_urls = list(dict.fromkeys(all_urls))

        filter_result = filter_new_urls(
            db_path=self.db_path,
            run_task_id=input_data.run_task_id,
            urls=unique_urls,
            retry_limit=2,
        )

        keep_urls = filter_result.get("keep_urls", [])
        skipped_urls = filter_result.get("skipped_urls", [])

        if keep_urls:
            mark_sources_status(
                db_path=self.db_path,
                run_task_id=input_data.run_task_id,
                urls=keep_urls,
                status="queued",
            )

        coverage_notes.append(
            f"Total unique: {len(unique_urls)}, "
            f"New: {len(keep_urls)}, "
            f"Skipped: {len(skipped_urls)}"
        )

        self.logger.info(f"[iter {input_data.iteration_number}] Researcher complete: {len(keep_urls)} new URLs")

        return ResearcherOutput(
            candidate_urls=keep_urls,
            coverage_notes="; ".join(coverage_notes),
        )

    async def _search(self, query: str, max_results: int = 10) -> list[str]:
        """Execute DuckDuckGo search and extract URLs."""
        start_time = time.time()
        urls = []

        def sync_search() -> list[str]:
            result_urls = []
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=max_results)
                for result in results:
                    url = result.get("href")
                    if url:
                        result_urls.append(url)
            return result_urls

        urls = await asyncio.to_thread(sync_search)

        duration_ms = (time.time() - start_time) * 1000
        self.logger.info(f"  Search '{query[:50]}...' found {len(urls)} URLs in {duration_ms:.0f}ms")

        return urls
