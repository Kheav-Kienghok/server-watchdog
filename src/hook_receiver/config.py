import os
from dataclasses import dataclass
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


@lru_cache
def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
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
    )
