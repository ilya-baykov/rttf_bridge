from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from .api_client import RttfAgentApiClient, RttfAgentFlow
from .config import Settings, load_settings
from .logging_config import configure_logging
from .models import FetchResult
from .rttf_client import RttfPageFetcher


FLOW_ALIASES = {
    "profiles": [RttfAgentFlow.PROFILES],
    "tournament-lists": [RttfAgentFlow.TOURNAMENT_LISTS],
    "tournament-pages": [RttfAgentFlow.TOURNAMENT_PAGES],
    "all": [
        RttfAgentFlow.PROFILES,
        RttfAgentFlow.TOURNAMENT_LISTS,
        RttfAgentFlow.TOURNAMENT_PAGES,
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Локально скачивает RTTF-страницы и отправляет HTML на сервер.",
    )

    parser.add_argument(
        "--flow",
        choices=sorted(FLOW_ALIASES),
        default="all",
        help=(
            "Что синхронизировать: profiles, tournament-lists, "
            "tournament-pages или all. По умолчанию all."
        ),
    )

    parser.add_argument("--base-url", help="URL Django-сайта, например http://127.0.0.1")
    parser.add_argument("--token", help="API-токен RTTF-агента.")
    parser.add_argument("--concurrency", type=int, help="Количество одновременных запросов к RTTF.")
    parser.add_argument("--timeout", type=float, help="HTTP-таймаут в секундах.")
    parser.add_argument("--limit", type=int, help="Обработать только первые N URL. 0 означает все.")
    parser.add_argument(
        "--submit-max-bytes",
        type=int,
        help="Максимальный размер JSON-запроса с результатами в байтах.",
    )
    parser.add_argument("--log-level", help="Уровень логирования, например INFO или DEBUG.")
    parser.add_argument("--log-dir", help="Папка для файлов логов.")

    return parser


def _apply_cli_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    return Settings(
        base_url=(args.base_url or settings.base_url).strip(),
        token=(args.token or settings.token).strip(),
        concurrency=args.concurrency if args.concurrency is not None else settings.concurrency,
        timeout=args.timeout if args.timeout is not None else settings.timeout,
        limit=args.limit if args.limit is not None else settings.limit,
        submit_max_bytes=(
            args.submit_max_bytes if args.submit_max_bytes is not None else settings.submit_max_bytes
        ),
        log_level=(args.log_level or settings.log_level).strip().upper(),
        log_dir=Path(args.log_dir).expanduser() if args.log_dir else settings.log_dir,
    )


def _progress_logger(completed: int, total: int, result: FetchResult) -> None:
    remaining = total - completed

    if result.ok:
        logger.info("Progress: {}/{} downloaded, {} left", completed, total, remaining)
        return

    logger.info(
        "Progress: {}/{} processed, {} left, last_failed={} {}",
        completed,
        total,
        remaining,
        result.url,
        result.error_type,
    )


def _pages_payload_size(pages: list[dict[str, str]]) -> int:
    return len(
        json.dumps(
            {"pages": pages},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _split_pages_by_payload_size(
    pages: list[dict[str, str]],
    max_bytes: int,
) -> list[list[dict[str, str]]]:
    batches: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []

    for page in pages:
        candidate = [*current, page]

        if current and _pages_payload_size(candidate) > max_bytes:
            batches.append(current)
            current = [page]
        else:
            current = candidate

        if len(current) == 1:
            page_size = _pages_payload_size(current)

            if page_size > max_bytes:
                logger.warning(
                    "Single RTTF page payload exceeds submit limit: url={} payload_bytes={} max_bytes={}",
                    page.get("url"),
                    page_size,
                    max_bytes,
                )

    if current:
        batches.append(current)

    return batches


def _merge_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Объединяет summary от разных батчей.

    Summary у profiles и tournaments отличается по ключам,
    поэтому суммируем все int-поля универсально.
    """

    for key, value in source.items():
        if isinstance(value, int):
            target[key] = target.get(key, 0) + value

    errors = source.get("errors", [])
    if isinstance(errors, list):
        target.setdefault("errors", []).extend(errors)


async def _submit_pages_in_batches(
    api_client: RttfAgentApiClient,
    flow: RttfAgentFlow,
    pages: list[dict[str, str]],
    max_bytes: int,
) -> dict[str, Any]:
    batches = _split_pages_by_payload_size(pages, max_bytes)

    logger.info(
        "Submitting results in {} batch(es): flow={} max_payload_bytes={}",
        len(batches),
        flow,
        max_bytes,
    )

    summary: dict[str, Any] = {"errors": []}

    for index, batch in enumerate(batches, start=1):
        payload_size = _pages_payload_size(batch)

        logger.info(
            "Submitting batch {}/{}: flow={} pages={} payload_bytes={}",
            index,
            len(batches),
            flow,
            len(batch),
            payload_size,
        )

        batch_summary = await api_client.submit_pages(flow, batch)
        _merge_summary(summary, batch_summary)

    return summary


def _build_failures_payload(failed: list[FetchResult]) -> list[dict[str, str]]:
    return [
        {
            "url": item.url,
            "error_type": item.error_type or "UNKNOWN_ERROR",
            "message": item.error_message or "",
        }
        for item in failed
    ]


def _print_summary(flow: RttfAgentFlow, summary: dict[str, Any]) -> None:
    """Печатает универсальный summary, не привязанный только к profiles."""

    print(f"Серверная синхронизация завершена: flow={flow}")

    for key, value in summary.items():
        if key == "errors":
            continue

        print(f"{key}={value}")

    errors = summary.get("errors", [])
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict):
                print(
                    f"- ошибка парсинга {error.get('url')}: "
                    f"{error.get('error_type')} - {error.get('message')}"
                )


async def run_flow(
    *,
    settings: Settings,
    api_client: RttfAgentApiClient,
    flow: RttfAgentFlow,
) -> int:
    """Выполняет один sync-flow.

    Например:
    - profiles;
    - tournament-lists;
    - tournament-pages.
    """

    logger.info("Starting RTTF flow: {}", flow)

    urls = await api_client.get_jobs(flow)

    if settings.limit > 0:
        logger.info("Applying limit: {}", settings.limit)
        urls = urls[: settings.limit]
    else:
        logger.info("Limit disabled; processing all RTTF URLs")

    if not urls:
        logger.info("No RTTF URLs returned by Django: flow={}", flow)
        print(f"Нет RTTF-страниц для синхронизации: flow={flow}")
        return 0

    logger.info("Fetching {} RTTF page(s): flow={}", len(urls), flow)

    fetcher = RttfPageFetcher(
        concurrency=settings.concurrency,
        timeout=settings.timeout,
    )

    results = await fetcher.fetch_pages(
        urls,
        progress_callback=_progress_logger,
    )

    pages = [{"url": item.url, "html": item.html} for item in results if item.ok]
    failed = [item for item in results if not item.ok]

    logger.info(
        "Fetch finished: flow={} success={} failed={}",
        flow,
        len(pages),
        len(failed),
    )

    failures = _build_failures_payload(failed)

    if failures:
        failures_summary = await api_client.submit_failures(flow, failures)
        print(f"Ошибки загрузки отправлены: flow={flow} summary={failures_summary}")

    if not pages:
        print(f"Не удалось успешно скачать ни одной страницы: flow={flow}")
        return 1

    summary = await _submit_pages_in_batches(
        api_client,
        flow,
        pages,
        settings.submit_max_bytes,
    )

    _print_summary(flow, summary)

    return 0


async def run(settings: Settings, flow_name: str) -> int:
    logger.info("Starting RTTF agent")
    logger.info(
        "Runtime settings: base_url={} concurrency={} timeout={} limit={} submit_max_bytes={} token_set={} flow={}",
        settings.base_url,
        settings.concurrency,
        settings.timeout,
        settings.limit,
        settings.submit_max_bytes,
        bool(settings.token),
        flow_name,
    )

    if not settings.token:
        print("Нужен токен RTTF-агента. Задайте RTTF_AGENT_TOKEN в .env.", file=sys.stderr)
        return 2

    if settings.concurrency < 1:
        print("RTTF_AGENT_CONCURRENCY должен быть >= 1.", file=sys.stderr)
        return 2

    if settings.submit_max_bytes < 1:
        print("RTTF_AGENT_SUBMIT_MAX_BYTES должен быть >= 1.", file=sys.stderr)
        return 2

    flows = FLOW_ALIASES[flow_name]

    async with RttfAgentApiClient(
        settings.base_url,
        settings.token,
        settings.timeout,
    ) as api_client:
        exit_code = 0

        for flow in flows:
            flow_exit_code = await run_flow(
                settings=settings,
                api_client=api_client,
                flow=flow,
            )

            if flow_exit_code != 0:
                exit_code = flow_exit_code

        return exit_code


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings, env_file = load_settings()
    final_settings = _apply_cli_overrides(settings, args)

    log_file = configure_logging(final_settings.log_level, final_settings.log_dir)

    if env_file is not None:
        logger.info("Loaded env from {}", env_file)

    logger.info("Writing logs to {}", log_file)

    try:
        return asyncio.run(run(final_settings, args.flow))
    except httpx.HTTPStatusError as exc:
        print(f"HTTP {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"HTTP-ошибка: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("Unexpected RTTF agent error")
        print(f"Неожиданная ошибка: {exc}", file=sys.stderr)
        return 1