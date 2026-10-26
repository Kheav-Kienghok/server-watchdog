import os
from dataclasses import dataclass, field
from functools import lru_cache


def parse_times(raw: str) -> tuple[tuple[int, int], ...]:
    """Parse "09:00,11:00,14:00" into ((9, 0), (11, 0), (14, 0))."""
    times: list[tuple[int, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        hh, _, mm = part.partition(":")
        h, m = int(hh), int(mm or 0)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"invalid time in HEALTHCHECK_TIMES: {part!r}")
        times.append((h, m))
    if not times:
        raise ValueError("HEALTHCHECK_TIMES must contain at least one time")
    return tuple(times)


def parse_overrides(raw: str) -> dict[str, str]:
    """Parse "a.com=10.0.0.5,b.com=10.0.0.6" into {"a.com": "10.0.0.5", ...}."""
    out: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        domain, sep, host = part.partition("=")
        if not sep or not domain.strip() or not host.strip():
            raise ValueError(f"invalid CERT_CONNECT_OVERRIDES entry: {part!r}")
        out[domain.strip().lower()] = host.strip()
    return out


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    timezone: str = "Asia/Phnom_Penh"
    telegram_timeout: float = 10.0
    healthcheck_times: tuple[tuple[int, int], ...] = ((9, 0), (11, 0), (14, 0), (16, 0), (21, 0))
    healthcheck_days: str = "mon,tue,wed,thu,fri,sun"
    cert_min_valid_days: int = 85
    cert_check_retries: int = 3
    cert_check_retry_delay: float = 20.0
    cert_port: int = 443
    cert_connect_host: str = ""
    cert_connect_overrides: dict[str, str] = field(default_factory=dict)
    cert_check_mode: str = "local"  # local | worker | both
    cert_worker_url: str = ""
    cert_worker_token: str = ""
    cert_worker_timeout: float = 30.0


@lru_cache
def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
    mode = os.getenv("CERT_CHECK_MODE", "local").strip().lower()
    if mode not in ("local", "worker", "both"):
        raise RuntimeError("CERT_CHECK_MODE must be local, worker or both")
    worker_url = os.getenv("CERT_WORKER_URL", "").strip()
    if mode in ("worker", "both") and not worker_url:
        raise RuntimeError("CERT_WORKER_URL must be set when CERT_CHECK_MODE is worker or both")
    return Settings(
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        timezone=os.getenv("TIMEZONE", "Asia/Phnom_Penh"),
        healthcheck_times=parse_times(
            os.getenv("HEALTHCHECK_TIMES", "09:00,11:00,14:00,16:00,21:00")
        ),
        healthcheck_days=os.getenv("HEALTHCHECK_DAYS", "mon,tue,wed,thu,fri,sun"),
        cert_min_valid_days=int(os.getenv("CERT_MIN_VALID_DAYS", "85")),
        cert_check_retries=int(os.getenv("CERT_CHECK_RETRIES", "3")),
        cert_check_retry_delay=float(os.getenv("CERT_CHECK_RETRY_DELAY", "20")),
        cert_port=int(os.getenv("CERT_PORT", "443")),
        cert_connect_host=os.getenv("CERT_CONNECT_HOST", "").strip(),
        cert_connect_overrides=parse_overrides(os.getenv("CERT_CONNECT_OVERRIDES", "")),
        cert_check_mode=mode,
        cert_worker_url=worker_url,
        cert_worker_token=os.getenv("CERT_WORKER_TOKEN", "").strip(),
        cert_worker_timeout=float(os.getenv("CERT_WORKER_TIMEOUT", "30")),
    )
