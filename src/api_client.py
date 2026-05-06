from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx
from loguru import logger


def api_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


class RttfAgentApiClient:
    def __init__(self, base_url: str, token: str, timeout: float) -> None:
        self._base_url = base_url
        self._token = token
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True)

    async def __aenter__(self) -> "RttfAgentApiClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.__aexit__(exc_type, exc, tb)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def get_jobs(self) -> list[str]:
        url = api_url(self._base_url, "/api/v1/rttf-agent/jobs/")
        logger.info("Requesting RTTF jobs from {}", url)
        response = await self._client.get(url, headers=self._headers())
        logger.info("Jobs response received: status={}", response.status_code)
        response.raise_for_status()

        payload = response.json()
        urls = payload.get("urls", [])
        if not isinstance(urls, list) or not all(isinstance(item, str) for item in urls):
            raise RuntimeError("Сервер вернул некорректный список заданий.")

        logger.info("Jobs payload parsed: {} url(s)", len(urls))
        return urls

    async def submit_pages(self, pages: list[dict[str, str]]) -> dict[str, Any]:
        url = api_url(self._base_url, "/api/v1/rttf-agent/results/")
        logger.info("Submitting {} RTTF page(s) to {}", len(pages), url)
        response = await self._client.post(url, headers=self._headers(), json={"pages": pages})
        logger.info("Results response received: status={}", response.status_code)
        response.raise_for_status()
        payload = response.json()
        logger.info(
            "Server summary parsed: profiles={} updated={} failed={} unknown={}",
            payload.get("profiles"),
            payload.get("updated"),
            payload.get("failed"),
            payload.get("unknown"),
        )
        return payload
