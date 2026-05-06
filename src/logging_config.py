from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger


def configure_logging(level_name: str, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"rttf-agent-{started_at}.log"
    latest_log_file = log_dir / "latest.log"

    logger.remove()
    logger.add(
        sys.stderr,
        level=level_name.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
    )
    logger.add(
        log_file,
        level=level_name.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )
    logger.add(
        latest_log_file,
        level=level_name.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        mode="w",
        encoding="utf-8",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return log_file
