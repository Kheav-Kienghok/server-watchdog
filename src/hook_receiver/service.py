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
from .worker_client import check_via_worker

logger = logging.getLogger("hook_receiver")


def _now(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S")


def build_failed_message(payload: HookPayload, tz: str) -> str:
    return (
        "❌ <b>FAILED</b>\n"
        f"Domain: <code>{escape(payload.domain)}</code>\n"
        f"Time: {_now(tz)} ({tz})"
    )


LABELS = {"local": "Local check", "cloudflare": "Cloudflare (outside)"}


def build_success_message(payload: HookPayload, checks: list[CertCheck], settings: Settings) -> str:
    tz = settings.timezone
    all_ok = all(c.ok for c in checks)
    lines = [
        "✅ <b>SUCCESS — certificate confirmed</b>"
        if all_ok
        else "⚠️ <b>SUCCESS reported, but certificate NOT confirmed</b>",
        f"Domain: <code>{escape(payload.domain)}</code>",
    ]
    for c in checks:
        label = LABELS.get(c.source, c.source)
        if c.ok:
            expires = c.not_after.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"• {label}: <b>{c.days_left}</b> days left (min {settings.cert_min_valid_days}), "
                f"expires {expires}, issuer {escape(c.issuer or 'unknown')}"
            )
        else:
            lines.append(f"• {label}: {escape(c.error or 'unknown')}")
    lines.append(f"Time: {_now(tz)} ({tz})")
    return "\n".join(lines)


async def _check_once(domain: str, settings: Settings, kind: str) -> CertCheck:
    if kind == "worker":
        return await check_via_worker(domain, settings)
    connect_host = settings.cert_connect_overrides.get(domain) or settings.cert_connect_host or None
    return await asyncio.to_thread(
        check_certificate,
        domain,
        settings.cert_min_valid_days,
        settings.cert_port,
        connect_host=connect_host,
    )


async def verify_certificate(domain: str, settings: Settings, kind: str = "local") -> CertCheck:
    """Check the cert, retrying a few times (web server reload / CT lag)."""
    result: CertCheck | None = None
    for attempt in range(1, settings.cert_check_retries + 1):
        result = await _check_once(domain, settings, kind)
        if result.ok:
            break
        logger.warning(
            "%s cert check %s/%s for %s not ok: %s",
            kind, attempt, settings.cert_check_retries, domain, result.error,
        )
        if attempt < settings.cert_check_retries:
            await asyncio.sleep(settings.cert_check_retry_delay)
    assert result is not None
    return result


KINDS = {"local": ["local"], "worker": ["worker"], "both": ["local", "worker"]}


async def process_hook(payload: HookPayload, settings: Settings) -> None:
    """Runs in the background after the hook request has been accepted."""
    try:
        if payload.status == "failed":
            text = build_failed_message(payload, settings.timezone)
        else:
            kinds = KINDS[settings.cert_check_mode]
            checks = await asyncio.gather(
                *(verify_certificate(payload.domain, settings, k) for k in kinds)
            )
            text = build_success_message(payload, list(checks), settings)
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
