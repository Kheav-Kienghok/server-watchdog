"""Outside-view certificate check via the Cloudflare Worker (/check endpoint)."""

from datetime import datetime

import httpx

from .cert import CertCheck
from .config import Settings


async def check_via_worker(
    domain: str, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> CertCheck:
    headers = {"X-Auth-Token": settings.cert_worker_token} if settings.cert_worker_token else {}
    url = settings.cert_worker_url.rstrip("/") + "/check"
    try:
        async with httpx.AsyncClient(timeout=settings.cert_worker_timeout, transport=transport) as client:
            resp = await client.get(url, params={"domain": domain}, headers=headers)
            resp.raise_for_status()
            body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        return CertCheck(domain, False, error=f"worker request failed: {exc}", source="cloudflare")

    ct = body.get("ct") or {}
    not_after = None
    if ct.get("notAfter"):
        not_after = datetime.fromisoformat(ct["notAfter"].replace("Z", "+00:00"))
    ok = bool(body.get("confirmed"))
    return CertCheck(
        domain=domain,
        ok=ok,
        days_left=ct.get("daysLeft"),
        not_after=not_after,
        issuer=ct.get("issuer"),
        error=None if ok else body.get("summary", "not confirmed"),
        source="cloudflare",
    )
