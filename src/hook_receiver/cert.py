"""Certificate check: connect to the domain over TLS and read the served cert."""

import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class CertCheck:
    domain: str
    ok: bool
    days_left: int | None = None
    not_after: datetime | None = None
    issuer: str | None = None
    error: str | None = None


def _issuer_name(cert: dict) -> str | None:
    rdns = cert.get("issuer", ())
    for wanted in ("organizationName", "commonName"):
        for rdn in rdns:
            for key, value in rdn:
                if key == wanted:
                    return value
    return None


def evaluate_cert(
    domain: str, cert: dict, min_days: int, now: datetime | None = None
) -> CertCheck:
    """Pure function: turn a getpeercert() dict into a CertCheck."""
    now = now or datetime.now(timezone.utc)
    not_after = datetime.fromtimestamp(
        ssl.cert_time_to_seconds(cert["notAfter"]), tz=timezone.utc
    )
    days_left = (not_after - now).days
    ok = days_left >= min_days
    return CertCheck(
        domain=domain,
        ok=ok,
        days_left=days_left,
        not_after=not_after,
        issuer=_issuer_name(cert),
        error=None if ok else f"only {days_left} valid days left (need at least {min_days})",
    )


def check_certificate(
    domain: str, min_days: int, port: int = 443, timeout: float = 10.0
) -> CertCheck:
    """Connect to domain:port with full verification (chain + hostname)."""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                cert = tls.getpeercert()
    except ssl.SSLCertVerificationError as exc:
        return CertCheck(domain, False, error=f"certificate verification failed: {exc.verify_message}")
    except (OSError, ssl.SSLError) as exc:
        return CertCheck(domain, False, error=f"connection failed: {exc}")
    return evaluate_cert(domain, cert, min_days)
