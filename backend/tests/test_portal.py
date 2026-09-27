from app.services import notify
from tests.conftest import GOOD_RFQ
from tests.test_flow import make_provider


def provider_login(client, admin, provider_id, email):
    r = client.post(f"/api/providers/{provider_id}/users", headers=admin, json={"email": email, "password": "portal-pass-1"})
    assert r.status_code == 201, r.text
    tok = client.post("/api/auth/login", data={"username": email, "password": "portal-pass-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def setup(client, admin, notes="Call me at +971 50 123 4567 or ali@example.com"):
    a = make_provider(client, admin, "Alpha", contact_email="ops@alpha.example")
    b = make_provider(client, admin, "Beta")
    client.post("/api/rfqs", json={**GOOD_RFQ, "notes": notes})
    rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]
    client.post(f"/api/rfqs/{rfq_id}/dispatch", headers=admin)
    return a, b, rfq_id


def test_provider_sees_only_masked_dispatched_rfqs(client, admin):
    a, b, rfq_id = setup(client, admin)
    ha = provider_login(client, admin, a, "p@alpha.example")
    rows = client.get("/api/portal/rfqs", headers=ha).json()
    assert len(rows) == 1 and rows[0]["state"] == "pending" and rows[0]["lane"] == "CN->AE"
    detail = client.get(f"/api/portal/rfqs/{rfq_id}", headers=ha).json()
    blob = str(detail)
    for secret in ("ali@example.com", "Ali Trading", "123 4567", "contact_email", "contact_phone"):
        assert secret not in blob
    assert "[phone hidden]" in detail["notes"] and "[email hidden]" in detail["notes"]


def test_provider_cannot_see_other_rfqs_or_ops_endpoints(client, admin):
    a, b, rfq_id = setup(client, admin)
    other = make_provider(client, admin, "Other", lanes=("TR->SA",))
    ho = provider_login(client, admin, other, "p@other.example")
    assert client.get("/api/portal/rfqs", headers=ho).json() == []
    assert client.get(f"/api/portal/rfqs/{rfq_id}", headers=ho).status_code == 404
    assert client.post(f"/api/portal/rfqs/{rfq_id}/quote", headers=ho,
                       json={"charges": [{"name": "freight", "amount": 1}]}).status_code == 404
    assert client.get("/api/rfqs", headers=ho).status_code == 403
    assert client.get("/api/providers", headers=ho).status_code == 403


def test_portal_quote_decline_and_win(client, admin):
    a, b, rfq_id = setup(client, admin)
    ha = provider_login(client, admin, a, "p@alpha.example")
    hb = provider_login(client, admin, b, "p@beta.example")

    r = client.post(f"/api/portal/rfqs/{rfq_id}/quote", headers=ha, json={
        "charges": [{"name": "Ocean freight", "amount": 2000}, {"name": "DTHC", "amount": 200}],
        "transit_days": 20, "exclusions": "Duties. Contact sales@alpha.example"})
    assert r.status_code == 201, r.text
    assert "[email hidden]" in r.json()["exclusions"]
    assert client.post(f"/api/portal/rfqs/{rfq_id}/quote", headers=ha,
                       json={"charges": [{"name": "x", "amount": 1}]}).status_code == 409
    assert client.post(f"/api/portal/rfqs/{rfq_id}/decline", headers=ha, json={"reason": "no"}).status_code == 409

    assert client.post(f"/api/portal/rfqs/{rfq_id}/decline", headers=hb, json={"reason": "No capacity"}).json()["state"] == "declined"
    disp = {d["provider_id"]: d for d in client.get(f"/api/rfqs/{rfq_id}/dispatches", headers=admin).json()}
    assert disp[b]["decline_reason"] == "No capacity" and disp[a]["responded_at"]

    cmp_ = client.get(f"/api/rfqs/{rfq_id}/compare", headers=admin).json()
    assert len(cmp_["quotes"]) == 1
    client.post(f"/api/rfqs/{rfq_id}/book", headers=admin, json={"quote_id": cmp_["quotes"][0]["quote_id"]})
    assert client.get("/api/portal/rfqs", headers=ha).json()[0]["state"] == "won"
    assert client.get("/api/portal/rfqs", headers=hb).json()[0]["state"] == "declined"
    me = client.get("/api/portal/me", headers=ha).json()
    assert me["stats"]["bookings_won"] == 1 and me["company"] == "Alpha"


def test_suspended_provider_locked_out(client, admin):
    a, b, rfq_id = setup(client, admin)
    ha = provider_login(client, admin, a, "p@alpha.example")
    client.patch(f"/api/providers/{a}", headers=admin, json={"suspended": True})
    assert client.get("/api/portal/rfqs", headers=ha).status_code == 403


def test_notifications_queued(client, admin):
    notify.outbox.clear()
    setup(client, admin)
    subjects = [(m["to"], m["subject"]) for m in notify.outbox]
    assert any(to == "ali@example.com" and "LR-" in s for to, s in subjects)
    assert any(to == "ops@alpha.example" and s.startswith("New freight RFQ") for to, s in subjects)


def test_change_password(client, admin):
    assert client.post("/api/auth/password", headers=admin,
                       json={"current_password": "wrong", "new_password": "new-pass-123"}).status_code == 400
    assert client.post("/api/auth/password", headers=admin,
                       json={"current_password": "test-admin-pw", "new_password": "new-pass-123"}).status_code == 200
    assert client.post("/api/auth/login", data={"username": "admin@logirad.local", "password": "new-pass-123"}).status_code == 200
