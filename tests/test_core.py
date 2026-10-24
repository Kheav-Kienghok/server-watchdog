import asyncio
import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hook_receiver import service  # noqa: E402
from hook_receiver.app import app  # noqa: E402
from hook_receiver.cert import CertCheck, evaluate_cert  # noqa: E402
from hook_receiver.config import get_settings, parse_times  # noqa: E402
from hook_receiver.schemas import HookPayload  # noqa: E402

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("CERT_CHECK_RETRY_DELAY", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_parse_times():
    assert parse_times("09:00, 14:30") == ((9, 0), (14, 30))
    with pytest.raises(ValueError):
        parse_times("25:00")


def test_schema_normalises_and_rejects():
    assert HookPayload(status="success", domain=" Example.COM ").domain == "example.com"
    with pytest.raises(ValueError):
        HookPayload(status="maybe", domain="example.com")
    with pytest.raises(ValueError):
        HookPayload(status="success", domain="not a domain")


def test_evaluate_cert_fresh_and_stale():
    fresh = evaluate_cert("a.com", {"notAfter": "Jan 22 03:14:00 2027 GMT"}, 85, NOW)
    assert fresh.ok and fresh.days_left == 90
    stale = evaluate_cert("a.com", {"notAfter": "Dec  1 00:00:00 2026 GMT"}, 85, NOW)
    assert not stale.ok and "need at least 85" in stale.error


def _post(client, status):
    return client.post("/hook", json={"status": status, "domain": "example.com"})


def test_success_hook_confirmed(monkeypatch):
    sent = []

    async def fake_send(text, settings):
        sent.append(text)

    monkeypatch.setattr(service, "send_text", fake_send)
    monkeypatch.setattr(
        service, "check_certificate",
        lambda d, m, p: CertCheck(d, True, 89, datetime(2027, 1, 22, tzinfo=timezone.utc), "Let's Encrypt"),
    )
    r = _post(TestClient(app), "success")
    assert r.status_code == 202
    assert "certificate confirmed" in sent[0] and "89" in sent[0]


def test_success_hook_not_confirmed(monkeypatch):
    sent = []

    async def fake_send(text, settings):
        sent.append(text)

    monkeypatch.setattr(service, "send_text", fake_send)
    monkeypatch.setattr(
        service, "check_certificate",
        lambda d, m, p: CertCheck(d, False, 12, None, None, "only 12 valid days left (need at least 85)"),
    )
    _post(TestClient(app), "success")
    assert "NOT confirmed" in sent[0]


def test_failed_hook_skips_cert_check(monkeypatch):
    sent = []

    async def fake_send(text, settings):
        sent.append(text)

    def boom(*a):
        raise AssertionError("cert check must not run on failed")

    monkeypatch.setattr(service, "send_text", fake_send)
    monkeypatch.setattr(service, "check_certificate", boom)
    _post(TestClient(app), "failed")
    assert "FAILED" in sent[0]


def test_heartbeat(monkeypatch):
    sent = []

    async def fake_send(text, settings):
        sent.append(text)

    monkeypatch.setattr(service, "send_text", fake_send)
    asyncio.run(service.send_heartbeat(get_settings(), datetime.now(timezone.utc)))
    assert "is running" in sent[0]
