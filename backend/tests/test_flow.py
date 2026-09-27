from datetime import date, timedelta

from tests.conftest import GOOD_RFQ

FUTURE = (date.today() + timedelta(days=30)).isoformat()


def make_provider(client, admin, name, lanes=("CN->AE",), modes=("ocean_fcl",), **kw):
    r = client.post("/api/providers", headers=admin,
                    json={"legal_name": name, "country": "AE", "lanes": list(lanes), "modes": list(modes), **kw})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_public_rfq_requires_no_auth_and_is_qualified(client):
    r = client.post("/api/rfqs", json=GOOD_RFQ)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "qualified"
    assert body["missing_fields"] == []
    assert body["reference"].startswith("LR-")
    assert client.get(f"/api/rfqs/track/{body['reference']}").json()["status"] == "qualified"


def test_incomplete_rfq_lists_missing_fields(client):
    r = client.post("/api/rfqs", json={"origin_country": "CN", "mode": "air", "commodity": "shoes"})
    body = r.json()
    assert body["status"] == "started"
    assert {"destination_country", "weight_kg", "volume_cbm", "contact_email"} <= set(body["missing_fields"])


def test_restricted_jurisdiction_goes_to_compliance_hold_and_blocks_dispatch(client, admin):
    make_provider(client, admin, "Any", lanes=("*->AE",))
    ref = client.post("/api/rfqs", json={**GOOD_RFQ, "origin_country": "IR"}).json()
    assert ref["status"] == "compliance_hold"
    rfq = client.get("/api/rfqs", headers=admin).json()[0]
    assert "restricted_jurisdiction:origin:IR" in rfq["flags"]
    r = client.post(f"/api/rfqs/{rfq['id']}/dispatch", headers=admin)
    assert r.status_code == 409
    r = client.post(f"/api/rfqs/{rfq['id']}/compliance", headers=admin,
                    json={"decision": "reject", "reason": "Out of policy scope"})
    assert r.json()["status"] == "rejected"


def test_dangerous_goods_only_match_dg_providers(client, admin):
    plain = make_provider(client, admin, "Plain")
    dg = make_provider(client, admin, "DG Pro", cargo_classes=["general", "dg"])
    client.post("/api/rfqs", json={**GOOD_RFQ, "commodity": "Lithium batteries"})
    rfq = client.get("/api/rfqs", headers=admin).json()[0]
    assert "dangerous_goods" in rfq["flags"]
    ids = [m["provider_id"] for m in client.get(f"/api/rfqs/{rfq['id']}/matches", headers=admin).json()]
    assert ids == [dg] and plain not in ids


def test_matching_filters_mode_lane_and_suspension(client, admin):
    exact = make_provider(client, admin, "Exact", verified=True)
    wildcard = make_provider(client, admin, "Wild", lanes=("*->AE",))
    make_provider(client, admin, "WrongMode", modes=("air",))
    make_provider(client, admin, "WrongLane", lanes=("TR->SA",))
    susp = make_provider(client, admin, "Suspended")
    client.patch(f"/api/providers/{susp}", headers=admin, json={"suspended": True})
    client.post("/api/rfqs", json=GOOD_RFQ)
    rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]
    ids = [m["provider_id"] for m in client.get(f"/api/rfqs/{rfq_id}/matches", headers=admin).json()]
    assert ids == [exact, wildcard]


def test_full_flow_quote_compare_book_deliver(client, admin):
    a = make_provider(client, admin, "Alpha", verified=True)
    b = make_provider(client, admin, "Beta")
    client.post("/api/rfqs", json=GOOD_RFQ)
    rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]

    r = client.post(f"/api/rfqs/{rfq_id}/dispatch", headers=admin)
    assert r.status_code == 200 and set(r.json()["dispatched_to"]) == {a, b}

    qa = client.post(f"/api/rfqs/{rfq_id}/quotes", headers=admin, json={
        "provider_id": a, "charges": [{"name": "Ocean freight", "amount": 2100}, {"name": "THC origin", "amount": 150},
                                      {"name": "DTHC", "amount": 250}],
        "transit_days": 18, "valid_until": FUTURE, "exclusions": "Duties and taxes"})
    assert qa.status_code == 201, qa.text
    assert qa.json()["total"] == 2500
    cats = {c["name"]: c["category"] for c in qa.json()["charges"]}
    assert cats == {"Ocean freight": "freight", "THC origin": "origin", "DTHC": "destination"}

    qb = client.post(f"/api/rfqs/{rfq_id}/quotes", headers=admin, json={
        "provider_id": b, "charges": [{"name": "All-in freight", "amount": 2300}], "transit_days": 25})
    assert qb.status_code == 201

    # duplicate active quote is rejected
    assert client.post(f"/api/rfqs/{rfq_id}/quotes", headers=admin, json={
        "provider_id": b, "charges": [{"name": "x", "amount": 1}]}).status_code == 409

    cmp_ = client.get(f"/api/rfqs/{rfq_id}/compare", headers=admin).json()
    assert cmp_["comparable"] is True
    assert [q["provider_id"] for q in cmp_["quotes"]] == [b, a]
    labels = {q["provider_id"]: q["labels"] for q in cmp_["quotes"]}
    assert "cheapest" in labels[b] and "fastest" in labels[a] and "most_complete" in labels[a]

    bk = client.post(f"/api/rfqs/{rfq_id}/book", headers=admin, json={"quote_id": qa.json()["id"], "platform_fee": 75})
    assert bk.status_code == 201, bk.text
    booking_id = bk.json()["id"]
    assert client.get(f"/api/rfqs/{rfq_id}", headers=admin).json()["status"] == "booked"

    r = client.post(f"/api/bookings/{booking_id}/milestones", headers=admin,
                    json={"event": "Vessel departed", "status": "in_transit"})
    assert r.json()["status"] == "in_transit"
    r = client.post(f"/api/bookings/{booking_id}/milestones", headers=admin,
                    json={"event": "POD received", "status": "delivered"})
    assert r.json()["status"] == "delivered"
    assert client.get(f"/api/rfqs/{rfq_id}", headers=admin).json()["status"] == "closed"

    providers = {p["id"]: p for p in client.get("/api/providers", headers=admin).json()}
    assert providers[a]["score_components"]["booking_success"] == 1.0
    assert providers[b]["score_components"]["price"] == 1.0  # b was cheapest
    assert providers[a]["score_components"]["price"] == 0.0

    k = client.get("/api/kpis", headers=admin).json()
    assert k["bookings"] == 1 and k["gross_revenue"] == 75
    assert k["quote_coverage"] == 1.0 and k["provider_response_rate"] == 1.0

    actions = [e["action"] for e in client.get("/api/audit", headers=admin).json()]
    for needed in ("rfq.create", "rfq.dispatch", "quote.create", "booking.create", "booking.milestone"):
        assert needed in actions


def test_quote_from_non_dispatched_provider_rejected(client, admin):
    a = make_provider(client, admin, "Alpha")
    other = make_provider(client, admin, "Other", lanes=("TR->SA",))
    client.post("/api/rfqs", json=GOOD_RFQ)
    rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]
    client.post(f"/api/rfqs/{rfq_id}/dispatch", headers=admin, json=[a])
    r = client.post(f"/api/rfqs/{rfq_id}/quotes", headers=admin,
                    json={"provider_id": other, "charges": [{"name": "freight", "amount": 1}]})
    assert r.status_code == 422


def test_ops_endpoints_require_auth(client):
    assert client.get("/api/rfqs").status_code == 401
    assert client.get("/api/providers").status_code == 401
    assert client.get("/api/kpis").status_code == 401


def test_ops_user_cannot_suspend_provider(client, admin):
    client.post("/api/auth/users", headers=admin, json={"email": "ops@x.com", "password": "ops-password", "role": "ops"})
    tok = client.post("/api/auth/login", data={"username": "ops@x.com", "password": "ops-password"}).json()["access_token"]
    ops = {"Authorization": f"Bearer {tok}"}
    pid = make_provider(client, ops, "P")
    assert client.patch(f"/api/providers/{pid}", headers=ops, json={"suspended": True}).status_code == 403
    assert client.patch(f"/api/providers/{pid}", headers=ops, json={"tier": "preferred"}).status_code == 200


def test_invalid_lane_rejected(client, admin):
    r = client.post("/api/providers", headers=admin, json={"legal_name": "X", "country": "AE", "lanes": ["China-UAE"]})
    assert r.status_code == 422
