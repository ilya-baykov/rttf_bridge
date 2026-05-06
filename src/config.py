from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()
    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]

    return key, value


def load_env_file(path: Path | None = None) -> Path | None:
    env_file = Path(os.getenv("RTTF_AGENT_ENV_FILE", "")).expanduser() if os.getenv("RTTF_AGENT_ENV_FILE") else None
    if env_file is None:
        env_file = path or DEFAULT_ENV_FILE
    else:
        if not env_file.is_absolute():
            env_file = (PROJECT_ROOT / env_file).resolve()

    if not env_file.exists():
        return None

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)

    return env_file


@dataclass(slots=True)
class Settings:
    base_url: str
    token: str
    concurrency: int
    timeout: float
    limit: int
    log_level: str
    log_dir: Path


def load_settings() -> tuple[Settings, Path | None]:
    env_file = load_env_file()
    settings = Settings(
        base_url=os.getenv("RTTF_AGENT_BASE_URL", "http://127.0.0.1").strip(),
        token=os.getenv("RTTF_AGENT_TOKEN", "").strip(),
        concurrency=int(os.getenv("RTTF_AGENT_CONCURRENCY", "1")),
        timeout=float(os.getenv("RTTF_AGENT_TIMEOUT", "30")),
        limit=int(os.getenv("RTTF_AGENT_LIMIT", "0")),
        log_level=os.getenv("RTTF_AGENT_LOG_LEVEL", "INFO").strip().upper(),
        log_dir=Path(os.getenv("RTTF_AGENT_LOG_DIR", str(PROJECT_ROOT / "logs"))).expanduser(),
    )
    return settings, env_file
