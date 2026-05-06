from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger


def configure_logging(level_name: str, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "rttf-agent.log"

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
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return log_file
