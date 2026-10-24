"""Business logic: process a hook, build messages, send the heartbeat."""

import asyncio
import logging
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

from .cert import CertCheck, check_certificate
from .config import Settings
from .schemas import HookPayload
from .telegram import send_text

logger = logging.getLogger("hook_receiver")


def _now(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S")


def build_failed_message(payload: HookPayload, tz: str) -> str:
    return (
        "❌ <b>FAILED</b>\n"
        f"Domain: <code>{escape(payload.domain)}</code>\n"
        f"Time: {_now(tz)} ({tz})"
    )


def build_success_message(payload: HookPayload, check: CertCheck, settings: Settings) -> str:
    tz = settings.timezone
    if check.ok:
        expires = check.not_after.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
        return (
            "✅ <b>SUCCESS — certificate confirmed</b>\n"
            f"Domain: <code>{escape(payload.domain)}</code>\n"
            f"Valid days left: <b>{check.days_left}</b> (min {settings.cert_min_valid_days})\n"
            f"Expires: {expires} ({tz})\n"
            f"Issuer: {escape(check.issuer or 'unknown')}\n"
            f"Time: {_now(tz)} ({tz})"
        )
    return (
        "⚠️ <b>SUCCESS reported, but certificate NOT confirmed</b>\n"
        f"Domain: <code>{escape(payload.domain)}</code>\n"
        f"Reason: {escape(check.error or 'unknown')}\n"
        f"Time: {_now(tz)} ({tz})"
    )


async def verify_certificate(domain: str, settings: Settings) -> CertCheck:
    """Check the cert, retrying a few times (e.g. nginx may not have reloaded yet)."""
    result: CertCheck | None = None
    for attempt in range(1, settings.cert_check_retries + 1):
        result = await asyncio.to_thread(
            check_certificate, domain, settings.cert_min_valid_days, settings.cert_port
        )
        if result.ok:
            break
        logger.warning(
            "cert check %s/%s for %s not ok: %s",
            attempt, settings.cert_check_retries, domain, result.error,
        )
        if attempt < settings.cert_check_retries:
            await asyncio.sleep(settings.cert_check_retry_delay)
    assert result is not None
    return result


async def process_hook(payload: HookPayload, settings: Settings) -> None:
    """Runs in the background after the hook request has been accepted."""
    try:
        if payload.status == "failed":
            text = build_failed_message(payload, settings.timezone)
        else:
            check = await verify_certificate(payload.domain, settings)
            text = build_success_message(payload, check, settings)
        await send_text(text, settings)
    except Exception:
        logger.exception("failed to process hook for %s", payload.domain)


def _uptime(started_at: datetime) -> str:
    total = int((datetime.now(timezone.utc) - started_at).total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}d {hours}h {minutes}m"


async def send_heartbeat(settings: Settings, started_at: datetime) -> None:
    tz = settings.timezone
    text = (
        "🟢 <b>telegram-ops-notifier is running</b>\n"
        f"Uptime: {_uptime(started_at)}\n"
        f"Time: {_now(tz)} ({tz})"
    )
    try:
        await send_text(text, settings)
    except Exception:
        logger.exception("heartbeat failed")
