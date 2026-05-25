from __future__ import annotations

from enum import StrEnum
from typing import Any
from urllib.parse import urljoin

import httpx
from loguru import logger


class RttfAgentFlow(StrEnum):
    """Тип синхронизации, которую должен выполнить агент."""

    PROFILES = "profiles"
    TOURNAMENT_LISTS = "tournament-lists"
    TOURNAMENT_PAGES = "tournament-pages"


FLOW_ENDPOINTS = {
    RttfAgentFlow.PROFILES: {
        "jobs": "/api/v1/rttf-agent/jobs/",
        "results": "/api/v1/rttf-agent/results/",
        "failures": "/api/v1/rttf-agent/failures/",
    },
    RttfAgentFlow.TOURNAMENT_LISTS: {
        "jobs": "/api/v1/rttf-agent/tournament-list-jobs/",
        "results": "/api/v1/rttf-agent/tournament-list-results/",
        "failures": "/api/v1/rttf-agent/failures/",
    },
    RttfAgentFlow.TOURNAMENT_PAGES: {
        "jobs": "/api/v1/rttf-agent/tournament-page-jobs/",
        "results": "/api/v1/rttf-agent/tournament-page-results/",
        "failures": "/api/v1/rttf-agent/failures/",
    },
}


def api_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


class RttfAgentApiClient:
    """HTTP-клиент для общения локального агента с Django API."""

    def __init__(self, base_url: str, token: str, timeout: float) -> None:
        self._base_url = base_url
        self._token = token
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def __aenter__(self) -> "RttfAgentApiClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.__aexit__(exc_type, exc, tb)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _endpoint(self, flow: RttfAgentFlow, name: str) -> str:
        return FLOW_ENDPOINTS[flow][name]

    async def get_jobs(self, flow: RttfAgentFlow) -> list[str]:
        """Получает список RTTF URL, которые нужно скачать."""

        url = api_url(self._base_url, self._endpoint(flow, "jobs"))

        logger.info("Requesting RTTF jobs: flow={} url={}", flow, url)

        response = await self._client.get(url, headers=self._headers())
        logger.info("Jobs response received: flow={} status={}", flow, response.status_code)
        response.raise_for_status()

        payload = response.json()
        urls = payload.get("urls", [])

        if not isinstance(urls, list) or not all(isinstance(item, str) for item in urls):
            raise RuntimeError("Сервер вернул некорректный список заданий.")

        logger.info("Jobs payload parsed: flow={} urls={}", flow, len(urls))
        return urls

    async def submit_pages(
        self,
        flow: RttfAgentFlow,
        pages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Отправляет скачанные HTML-страницы в нужный Django endpoint."""

        url = api_url(self._base_url, self._endpoint(flow, "results"))

        logger.info("Submitting RTTF pages: flow={} pages={} url={}", flow, len(pages), url)

        response = await self._client.post(
            url,
            headers=self._headers(),
            json={"pages": pages},
        )

        logger.info("Results response received: flow={} status={}", flow, response.status_code)
        response.raise_for_status()

        payload = response.json()
        logger.info("Server summary parsed: flow={} summary={}", flow, payload)

        return payload

    async def submit_failures(
        self,
        flow: RttfAgentFlow,
        failures: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Отправляет ошибки скачивания страниц.

        Пока failures endpoint общий/старый.
        Позже можно сделать отдельные failures для турниров.
        """

        url = api_url(self._base_url, self._endpoint(flow, "failures"))

        logger.info("Submitting RTTF failures: flow={} failures={} url={}", flow, len(failures), url)

        response = await self._client.post(
            url,
            headers=self._headers(),
            json={"failures": failures},
        )

        logger.info("Failures response received: flow={} status={}", flow, response.status_code)
        response.raise_for_status()

        payload = response.json()
        logger.info("Failures summary parsed: flow={} summary={}", flow, payload)

        return payload