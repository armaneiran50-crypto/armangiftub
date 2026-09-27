from tests.conftest import GOOD_RFQ
from tests.test_flow import make_provider


def test_lane_stats_counts_providers_and_hides_thin_transit(client, admin):
    a = make_provider(client, admin, "A", verified=True)
    b = make_provider(client, admin, "B", lanes=("*->AE",), modes=("ocean_fcl", "air"))
    make_provider(client, admin, "C", lanes=("TR->SA",))
    s = make_provider(client, admin, "S")
    client.patch(f"/api/providers/{s}", headers=admin, json={"suspended": True})
    r = client.get("/api/lanes/cn/ae").json()
    assert r["providers"] == 2 and r["has_history"] is False
    assert r["modes"]["ocean_fcl"] == {"providers": 2, "verified_providers": 1}
    assert r["modes"]["air"]["providers"] == 1

    for days in (18, 22, 30):
        client.post("/api/rfqs", json=GOOD_RFQ)
        rfq_id = client.get("/api/rfqs", headers=admin).json()[0]["id"]
        client.post(f"/api/rfqs/{rfq_id}/dispatch", headers=admin, json=[a])
        client.post(f"/api/rfqs/{rfq_id}/quotes", headers=admin,
                    json={"provider_id": a, "charges": [{"name": "freight", "amount": 1000}], "transit_days": days})
        if days == 22:
            thin = client.get("/api/lanes/CN/AE").json()["modes"]["ocean_fcl"]
            assert thin["quotes"] == 2 and "median_transit_days" not in thin
    fcl = client.get("/api/lanes/CN/AE").json()["modes"]["ocean_fcl"]
    assert fcl["median_transit_days"] == 22 and "total" not in str(fcl)


def test_lane_stats_validates_codes(client):
    assert client.get("/api/lanes/china/AE").status_code == 422
