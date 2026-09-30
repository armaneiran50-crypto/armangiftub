"""AI agents with a fake Anthropic client (no network)."""
from types import SimpleNamespace

import pytest

from app.ai import quote_parser
from app.ai.intake import RFQDraft
from app.ai.quote_parser import ParsedCharge, QuoteDraft
from app.config import get_settings
from tests.conftest import GOOD_RFQ
from tests.portal_helpers import provider_login
from tests.test_flow import make_provider


class FakeClient:
    def __init__(self, output, stop_reason="end_turn"):
        self.calls = []
        self.output, self.stop_reason = output, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason, model=kwargs["model"],
                               parsed_output=None if self.stop_reason == "refusal" else self.output,
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50))


@pytest.fixture()
def ai_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_enabled", True)


def fake(monkeypatch, output, **kw):
    client = FakeClient(output, **kw)
    monkeypatch.setattr("app.ai.quote_parser.get_client", lambda: client)
    monkeypatch.setattr("app.ai.intake.get_client", lambda: client)
    return client


def dispatched_rfq(client, admin):
    pid = make_provider(client, admin, "Alpha")
    client.post("/api/rfqs", json=GOOD_RFQ)
    rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]
    client.post(f"/api/rfqs/{rfq_id}/dispatch", headers=admin)
    return pid, rfq_id


DRAFT = QuoteDraft(currency="usd", transit_days=22, valid_until="2026-12-31", stated_total=2500,
                   exclusions="Duties; contact sales@alpha.example",
                   charges=[ParsedCharge(name="Ocean freight 1 x 2100/40HC", amount=2100, category="freight"),
                            ParsedCharge(name="THC", amount=150, category="origin"),
                            ParsedCharge(name="DTHC", amount=250, category="destination")])


def test_quote_parse_text_returns_draft_without_saving(client, admin, ai_on, monkeypatch):
    fc = fake(monkeypatch, DRAFT.model_copy(deep=True))
    _, rfq_id = dispatched_rfq(client, admin)
    r = client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin, data={"text": "O/F USD 2100 per 40HC ..."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["currency"] == "USD" and len(body["charges"]) == 3 and body["warnings"] == []
    assert client.get(f"/api/rfqs/{rfq_id}/compare", headers=admin).json()["quotes"] == []  # nothing saved
    call = fc.calls[0]
    assert call["model"] == "claude-opus-5" and call["fallbacks"] == "default"
    assert "Containers: 1x40HC" in call["messages"][0]["content"][-1]["text"]


def test_quote_parse_flags_total_mismatch(client, admin, ai_on, monkeypatch):
    d = DRAFT.model_copy(deep=True)
    d.stated_total = 2900
    fake(monkeypatch, d)
    _, rfq_id = dispatched_rfq(client, admin)
    body = client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin, data={"text": "..."}).json()
    assert any("یکی نیست" in w for w in body["warnings"])


def test_quote_parse_pdf_is_sent_as_document(client, admin, ai_on, monkeypatch):
    fc = fake(monkeypatch, DRAFT.model_copy(deep=True))
    _, rfq_id = dispatched_rfq(client, admin)
    r = client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin,
                    files={"file": ("quote.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    first = fc.calls[0]["messages"][0]["content"][0]
    assert first["type"] == "document" and first["source"]["media_type"] == "application/pdf"
    bad = client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin,
                      files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 415


def test_quote_parse_requires_input_and_ai(client, admin, monkeypatch):
    _, rfq_id = dispatched_rfq(client, admin)
    assert client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin, data={"text": "x"}).status_code == 503
    monkeypatch.setattr(get_settings(), "ai_enabled", True)
    assert client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin, data={}).status_code == 422


def test_quote_parse_refusal_is_503(client, admin, ai_on, monkeypatch):
    fake(monkeypatch, None, stop_reason="refusal")
    _, rfq_id = dispatched_rfq(client, admin)
    assert client.post(f"/api/rfqs/{rfq_id}/quotes/parse", headers=admin, data={"text": "..."}).status_code == 503


def test_provider_can_parse_own_quote_and_contact_is_redacted(client, admin, ai_on, monkeypatch):
    fake(monkeypatch, DRAFT.model_copy(deep=True))
    pid, rfq_id = dispatched_rfq(client, admin)
    hp = provider_login(client, admin, pid, "p@alpha.example")
    r = client.post(f"/api/portal/rfqs/{rfq_id}/quote/parse", headers=hp, data={"text": "..."})
    assert r.status_code == 200 and "[email hidden]" in r.json()["exclusions"]
    other = make_provider(client, admin, "Other", lanes=("TR->SA",))
    ho = provider_login(client, admin, other, "p@other.example")
    assert client.post(f"/api/portal/rfqs/{rfq_id}/quote/parse", headers=ho, data={"text": "..."}).status_code == 404


def test_intake_parse_with_fake_client(client, ai_on, monkeypatch):
    fake(monkeypatch, RFQDraft(origin_country="CN", destination_country="AE", mode="ocean_fcl", containers="2x40HC",
                               contact_phone="+1 555", questions=["تاریخ آمادگی بار؟"]))
    r = client.post("/api/intake/parse", json={"text": "two 40HC from Shanghai to Dubai"})
    assert r.status_code == 200
    assert r.json()["draft"]["containers"] == "2x40HC" and r.json()["questions"] == ["تاریخ آمادگی بار؟"]
