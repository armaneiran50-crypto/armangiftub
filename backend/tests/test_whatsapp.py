import hashlib
import hmac
import itertools
import json

import pytest

from app.config import get_settings
from app.services import whatsapp as wa
from tests.test_flow import make_provider

_ids = itertools.count()


@pytest.fixture()
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(wa, "send_text", lambda to, body: out.append((to, body)) or "ok")
    return out


def inbound(client, text, wa_id="971501234567", name="Ali", msg_type="text", headers=None):
    msg = {"from": wa_id, "id": f"wamid.{next(_ids)}", "type": msg_type}
    if msg_type == "text":
        msg["text"] = {"body": text}
    payload = {"entry": [{"changes": [{"value": {"contacts": [{"wa_id": wa_id, "profile": {"name": name}}],
                                                 "messages": [msg]}}]}]}
    r = client.post("/api/whatsapp/webhook", content=json.dumps(payload), headers=headers or {})
    return r, msg["id"], payload


def last(sent):
    return sent[-1][1]


def test_webhook_verification(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_verify_token", "tok123")
    ok = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "tok123", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_signature_required_when_secret_set(client, monkeypatch, sent):
    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "s3cret")
    r, _, _ = inbound(client, "سلام")
    assert r.status_code == 401
    payload = {"entry": [{"changes": [{"value": {"messages": [{"from": "1", "id": "x1", "type": "text", "text": {"body": "hi"}}]}}]}]}
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert client.post("/api/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": sig}).status_code == 200


def test_guided_persian_flow_creates_rfq(client, admin, sent):
    inbound(client, "سلام")
    assert "خوش آمدید" in sent[0][1] and "کدام کشور" in last(sent)
    inbound(client, "شانگهای")
    assert "مقصد" in last(sent)
    inbound(client, "دبی")
    assert "نوع حمل" in last(sent)
    inbound(client, "۱")
    assert "نوع کالا" in last(sent)
    inbound(client, "مبلمان")
    assert "وزن" in last(sent)
    inbound(client, "بیست")  # not a number → retry
    assert last(sent).startswith("متوجه نشدم")
    inbound(client, "۱۸ تن")
    assert "کانتینر" in last(sent)
    inbound(client, "2x40HC")
    assert "تاریخ" in last(sent)
    inbound(client, "۱۴۰۵/۰۹/۰۱")
    assert "تأیید می‌کنید" in last(sent) and "Shanghai → Dubai" in last(sent)
    inbound(client, "بله")
    assert "ثبت شد" in last(sent)
    rfq = client.get("/api/rfqs", headers=admin).json()[0]
    assert rfq["source"] == "whatsapp" and rfq["contact_phone"] == "+971501234567"
    assert rfq["status"] == "qualified" and rfq["weight_kg"] == 18000 and rfq["containers"] == "2x40HC"
    assert rfq["ready_date"] == "2026-11-22" and rfq["contact_name"] == "Ali"

    inbound(client, "وضعیت")
    assert rfq["reference"] in last(sent)


def test_free_text_english_fills_many_fields(client, admin, sent):
    inbound(client, "Hi, I need to ship 2x40HC furniture from Shanghai to Dubai, 20 tons, ready 2026-11-20", wa_id="4479")
    assert "What is the commodity" in last(sent)
    inbound(client, "Furniture", wa_id="4479")
    assert "Confirm?" in last(sent)
    inbound(client, "no", wa_id="4479")
    assert "start over" in last(sent)


def test_duplicate_webhook_delivery_ignored(client, sent):
    r, mid, payload = inbound(client, "سلام")
    n = len(sent)
    client.post("/api/whatsapp/webhook", content=json.dumps(payload))
    assert len(sent) == n


def test_handoff_and_ops_reply(client, admin, sent):
    inbound(client, "سلام")
    inbound(client, "کارشناس")
    assert "همکاران" in last(sent)
    convs = client.get("/api/whatsapp/conversations?needs_human=true", headers=admin).json()
    assert len(convs) == 1 and convs[0]["window_open"]
    cid = convs[0]["id"]
    r = client.post(f"/api/whatsapp/conversations/{cid}/reply", headers=admin, json={"text": "سلام، در خدمتم"})
    assert r.status_code == 200 and sent[-1] == ("971501234567", "سلام، در خدمتم")
    detail = client.get(f"/api/whatsapp/conversations/{cid}", headers=admin).json()
    assert detail["needs_human"] is False
    assert [m["sender"] for m in detail["messages"]][-1] == "admin@logirad.local"
    assert detail["messages"][-1]["delivery"] == "ok"
    # pause the bot: further customer messages get no automatic reply
    client.patch(f"/api/whatsapp/conversations/{cid}", headers=admin, json={"bot_paused": True})
    n = len(sent)
    inbound(client, "ممنون")
    assert len(sent) == n


def test_media_message_goes_to_human(client, admin, sent):
    inbound(client, "", msg_type="image")
    assert client.get("/api/whatsapp/conversations?needs_human=true", headers=admin).json()


def test_reply_blocked_outside_24h_window(client, admin, sent):
    from datetime import datetime, timedelta, timezone

    from app.models import WAConversation
    inbound(client, "سلام")
    cid = client.get("/api/whatsapp/conversations", headers=admin).json()[0]["id"]
    db = next(client.app.dependency_overrides[__import__("app.db", fromlist=["get_db"]).get_db]())
    conv = db.get(WAConversation, cid)
    conv.last_inbound_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db.commit()
    r = client.post(f"/api/whatsapp/conversations/{cid}/reply", headers=admin, json={"text": "hello"})
    assert r.status_code == 409


def test_whatsapp_customer_told_when_quotes_arrive(client, admin, sent):
    pid = make_provider(client, admin, "Alpha")
    for text in ["2x40HC furniture from Shanghai to Dubai, 20 tons, ready 2026-11-20", "Furniture", "yes"]:
        inbound(client, text, wa_id="4479")
    rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]
    client.post(f"/api/rfqs/{rfq_id}/dispatch", headers=admin)
    client.post(f"/api/rfqs/{rfq_id}/quotes", headers=admin, json={"provider_id": pid, "charges": [{"name": "freight", "amount": 100}]})
    assert sent[-1][0] == "4479" and "Quotes have arrived" in sent[-1][1]


def test_public_config(client):
    assert client.get("/api/config").json() == {"whatsapp_number": None, "ai_intake": False}
