"""Scraper agent - extracts content from URLs using Trafilatura."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .config import ScraperInput, ScraperOutput
from .utils import (
    can_scrape,
    update_scraper_timestamp,
    mark_sources_status,
)
from .logger import get_logger, log_structured

# Try to import trafilatura for content extraction
try:
    from trafilatura import fetch_url, extract
    from trafilatura.settings import use_config
    TRAFILATURA_AVAILABLE = True
except ImportError as e:
    TRAFILATURA_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(f"trafilatura not available: {e}. Fallback extraction will be used.")

# Try to import requests as fallback
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError as e:
    REQUESTS_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(f"requests/beautifulsoup4 not available: {e}. Basic extraction only.")


class ScraperAgent:
    """Extracts structured data from URLs using Trafilatura."""

    def __init__(self, db_path: str = "idea_harvester.sqlite", max_concurrent: int = 3):
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.logger = get_logger()
        if not TRAFILATURA_AVAILABLE and not REQUESTS_AVAILABLE:
            raise ImportError(
                "No web scraping library available. "
                "Install with: pip install trafilatura requests beautifulsoup4"
            )

        # Configure trafilatura for faster extraction
        if TRAFILATURA_AVAILABLE:
            self.trafilatura_config = use_config()
            self.trafilatura_config.set("DEFAULT", "MAX_FILE_SIZE", "10000000")  # 10MB max
            self.trafilatura_config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "100")  # Min 100 chars
            self.trafilatura_config.set("DEFAULT", "MAX_RETRIES", "2")

    def _get_url_priority(self, url: str) -> int:
        """Return priority score for URL. Higher = more important."""
        if "reddit.com" in url:
            return 2
        if "x.com" in url or "twitter.com" in url:
            return 2
        return 1

    async def scrape(self, input_data: ScraperInput) -> ScraperOutput:
        """Scrape URLs with cooldown enforcement and concurrent fetching."""
        self.logger.info(f"[iter {input_data.iteration_number}] Scraper starting: {len(input_data.urls)} URLs")

        can_proceed, wait_seconds = can_scrape(
            db_path=self.db_path,
            run_task_id=input_data.run_task_id,
            cooldown_seconds=input_data.throttle_seconds,
        )

        if not can_proceed:
            self.logger.info(f"Scraper throttled, waiting {wait_seconds}s")
            await asyncio.sleep(wait_seconds)

        urls = input_data.urls
        extracted = []
        failures = []

        # Sort by priority (descending) so important URLs are first
        sorted_urls = sorted(urls, key=lambda u: self._get_url_priority(u), reverse=True)
        self.logger.info(f"URL priorities: {[f'{u} ({self._get_url_priority(u)})' for u in sorted_urls[:8]]}")
        urls_to_scrape = sorted_urls[:5]

        # Create semaphore for concurrent fetching
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(url: str) -> dict[str, Any] | None:
            """Fetch a single URL with semaphore-controlled concurrency."""
            async with semaphore:
                try:
                    # Run synchronous extraction in thread pool
                    content = await asyncio.to_thread(self._fetch_and_extract, url)
                    if content and content.get("text"):
                        return {
                            "url": url,
                            "content": content,
                            "timestamp": time.time(),
                        }
                    else:
                        return {"url": url, "error": "No content extracted"}
                except Exception as e:
                    return {"url": url, "error": str(e)}

        # Fetch all URLs concurrently
        tasks = [fetch_with_semaphore(url) for url in urls_to_scrape]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                # This shouldn't happen with return_exceptions=True, but handle it
                failures.append(f"Unknown URL: {str(result)}")
                self.logger.error(f"Exception during scrape: {result}")
            elif result is None:
                failures.append("Unknown URL: No result")
            else:
                # Type narrowing: result is dict[str, Any] here
                result_dict: dict[str, Any] = result  # type: ignore[assignment]
                if "error" in result_dict:
                    failures.append(f"{result_dict['url']}: {result_dict['error']}")
                    self.logger.warning(f"No content from {result_dict['url'][:60]}")
                else:
                    extracted.append(result_dict)
                    text_len = len(result_dict.get('content', {}).get('text', ''))
                    log_structured(
                        "content_scraped",
                        url=result_dict['url'],
                        content_length=text_len,
                        quality_score=text_len / 1000 if text_len > 0 else 0,
                        iteration=input_data.iteration_number,
                    )
                    self.logger.info(f"Extracted {text_len} chars from {result_dict['url'][:60]}")

        if extracted:
            mark_sources_status(
                db_path=self.db_path,
                run_task_id=input_data.run_task_id,
                urls=[e["url"] for e in extracted],
                status="scraped",
            )

        if failures:
            failed_urls = [f.split(":")[0] for f in failures]
            mark_sources_status(
                db_path=self.db_path,
                run_task_id=input_data.run_task_id,
                urls=failed_urls,
                status="failed",
            )

        update_scraper_timestamp(self.db_path, input_data.run_task_id)

        # Calculate quality score
        total = len(urls_to_scrape)
        success = len(extracted)
        quality = success / total if total > 0 else 0.0

        # Adjust quality based on content richness
        total_content_length = sum(len(item.get("content", {}).get("text", "")) for item in extracted)
        avg_content_length = total_content_length / success if success > 0 else 0

        # Bonus for rich content (more than 1000 chars)
        if avg_content_length > 1000:
            quality += 0.1
        quality = min(1.0, quality)

        self.logger.info(f"[iter {input_data.iteration_number}] Scraper complete: {success}/{total} URLs, quality={quality:.2f}")

        return ScraperOutput(
            extracted=extracted,
            scrape_quality=quality,
            scrape_failures=failures,
            dedup_removed_count=len(urls) - len(urls_to_scrape),
        )

    def _fetch_and_extract(self, url: str) -> dict[str, Any]:
        """Fetch URL and extract structured content."""

        if TRAFILATURA_AVAILABLE:
            return self._trafilatura_extract(url)
        elif REQUESTS_AVAILABLE:
            return self._requests_extract(url)
        else:
            raise RuntimeError("No scraping library available")

    def _trafilatura_extract(self, url: str) -> dict[str, Any]:
        """Extract content using Trafilatura."""

        # Fetch and extract in one call
        downloaded = fetch_url(url, config=self.trafilatura_config)

        if downloaded is None:
            raise RuntimeError("Failed to download page")

        # Extract main content
        text = extract(
            downloaded,
            config=self.trafilatura_config,
            include_comments=False,
            include_tables=False,
            deduplicate=True,
        )

        if not text:
            raise RuntimeError("No main content extracted")

        # Extract title
        soup = BeautifulSoup(downloaded, 'html.parser')
        title = soup.title.string if soup.title else ""

        # Extract metadata
        description = ""
        desc_meta = soup.find("meta", attrs={"name": "description"})
        if desc_meta:
            description = desc_meta.get("content", "")

        return {
            "title": title.strip() if title else "",
            "text": text.strip(),
            "description": description,
            "metadata": {
                "source": url,
                "extracted_at": time.time(),
                "method": "trafilatura",
                "content_length": len(text),
            },
        }

    def _requests_extract(self, url: str) -> dict[str, Any]:
        """Fallback extraction using requests + BeautifulSoup."""

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get title
        title = soup.title.string if soup.title else ""

        # Get description
        description = ""
        desc_meta = soup.find("meta", attrs={"name": "description"})
        if desc_meta:
            description = desc_meta.get("content", "")

        # Get text content
        text = soup.get_text(separator=" ", strip=True)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        return {
            "title": title.strip() if title else "",
            "text": text,
            "description": description,
            "metadata": {
                "source": url,
                "extracted_at": time.time(),
                "method": "requests",
                "content_length": len(text),
            },
        }
