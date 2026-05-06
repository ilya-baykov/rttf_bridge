from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
from loguru import logger

from .models import FetchResult


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://rttf.ru/",
}


class RttfPageFetcher:
    def __init__(self, *, concurrency: int, timeout: float) -> None:
        self._concurrency = concurrency
        self._timeout = timeout

    async def _fetch_one(self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, url: str) -> FetchResult:
        async with semaphore:
            logger.info("Downloading RTTF page: {}", url)
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                error_type = type(exc).__name__
                error_message = str(exc) or repr(exc)
                logger.warning("RTTF download failed: {} error={} message={}", url, error_type, error_message)
                return FetchResult(url=url, error_type=error_type, error_message=error_message)

            html = response.text
            final_url = str(response.url)
            html_bytes = len(html.encode("utf-8"))
            logger.info(
                "RTTF page downloaded: {} status={} final_url={} bytes={}",
                url,
                response.status_code,
                final_url,
                html_bytes,
            )
            return FetchResult(url=url, html=html, status_code=response.status_code, final_url=final_url)

    async def fetch_pages(
        self,
        urls: list[str],
        *,
        progress_callback: Callable[[int, int, FetchResult], None] | None = None,
    ) -> list[FetchResult]:
        if not urls:
            return []

        semaphore = asyncio.Semaphore(self._concurrency)
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        ) as client:
            tasks = [asyncio.create_task(self._fetch_one(client, semaphore, url)) for url in urls]
            results: list[FetchResult] = []
            completed = 0
            total = len(tasks)

            for task in asyncio.as_completed(tasks):
                result = await task
                results.append(result)
                completed += 1
                if progress_callback is not None:
                    progress_callback(completed, total, result)

            return results
