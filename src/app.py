from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx
from loguru import logger

from .api_client import RttfAgentApiClient
from .config import Settings, load_settings
from .logging_config import configure_logging
from .models import FetchResult
from .rttf_client import RttfPageFetcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Локально скачивает RTTF-страницы и отправляет HTML на сервер.",
    )
    parser.add_argument("--base-url", help="URL Django-сайта, например http://127.0.0.1")
    parser.add_argument("--token", help="API-токен RTTF-агента.")
    parser.add_argument("--concurrency", type=int, help="Количество одновременных запросов к RTTF.")
    parser.add_argument("--timeout", type=float, help="HTTP-таймаут в секундах.")
    parser.add_argument("--limit", type=int, help="Обработать только первые N URL. 0 означает все.")
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


async def run(settings: Settings) -> int:
    logger.info("Starting RTTF agent")
    logger.info(
        "Runtime settings: base_url={} concurrency={} timeout={} limit={} token_set={}",
        settings.base_url,
        settings.concurrency,
        settings.timeout,
        settings.limit,
        bool(settings.token),
    )

    if not settings.token:
        print("Нужен токен RTTF-агента. Задайте RTTF_AGENT_TOKEN в .env.", file=sys.stderr)
        return 2

    if settings.concurrency < 1:
        print("RTTF_AGENT_CONCURRENCY должен быть >= 1.", file=sys.stderr)
        return 2

    async with RttfAgentApiClient(settings.base_url, settings.token, settings.timeout) as api_client:
        urls = await api_client.get_jobs()

        if settings.limit > 0:
            logger.info("Applying limit: {}", settings.limit)
            urls = urls[: settings.limit]
        else:
            logger.info("Limit disabled; processing all RTTF URLs")

        if not urls:
            logger.info("No RTTF URLs returned by Django")
            print("Нет RTTF-профилей для синхронизации.")
            return 0

        logger.info("Fetching {} RTTF page(s)", len(urls))
        fetcher = RttfPageFetcher(concurrency=settings.concurrency, timeout=settings.timeout)
        results = await fetcher.fetch_pages(urls, progress_callback=_progress_logger)

        pages = [{"url": item.url, "html": item.html} for item in results if item.ok]
        failed = [item for item in results if not item.ok]

        logger.info("Fetch finished: success={} failed={}", len(pages), len(failed))
        for item in failed:
            logger.warning(
                "Failed page: url={} error={} message={}",
                item.url,
                item.error_type,
                item.error_message,
            )

        if not pages:
            print("Не удалось успешно скачать ни одной страницы.")
            return 1

        summary = await api_client.submit_pages(pages)
        print(
            "Серверная синхронизация завершена: "
            f"profiles={summary.get('profiles')}, "
            f"updated={summary.get('updated')}, "
            f"failed={summary.get('failed')}, "
            f"unknown={summary.get('unknown')}"
        )

        errors = summary.get("errors", [])
        if isinstance(errors, list):
            for error in errors:
                if isinstance(error, dict):
                    print(
                        f"- ошибка парсинга {error.get('url')}: "
                        f"{error.get('error_type')} - {error.get('message')}"
                    )

    return 0


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
        return asyncio.run(run(final_settings))
    except httpx.HTTPStatusError as exc:
        print(f"HTTP {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"HTTP-ошибка: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Неожиданная ошибка: {exc}", file=sys.stderr)
        return 1
