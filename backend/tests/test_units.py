from app.services.calculator import compute
from app.services.quotes import categorize, quote_completeness


def test_air_chargeable_weight_uses_volume_when_bulky():
    r = compute([{"length_cm": 100, "width_cm": 100, "height_cm": 100, "weight_kg": 50, "quantity": 2}], "air")
    assert r["total_cbm"] == 2.0
    assert r["volumetric_weight_kg"] == 334.0
    assert r["chargeable_weight_kg"] == 334.0 and r["basis"] == "volume"


def test_lcl_revenue_tons():
    r = compute([{"length_cm": 120, "width_cm": 100, "height_cm": 100, "weight_kg": 2000}], "ocean_lcl")
    assert r["revenue_tons"] == 2.0 and r["basis"] == "weight"


def test_categorize():
    assert categorize("BAF surcharge", None) == "freight"
    assert categorize("Delivery order fee", None) == "destination"
    assert categorize("Something", "origin") == "origin"
    assert categorize("Misc", None) == "other"


def test_quote_completeness():
    full = [{"category": "freight"}, {"category": "origin"}, {"category": "destination"}]
    assert quote_completeness(full, 20, "2030-01-01", "duties") == 1.0
    assert quote_completeness([{"category": "other"}], None, None, None) == 0.0


def test_calculator_endpoint(client):
    r = client.post("/api/tools/chargeable-weight",
                    json={"mode": "road", "items": [{"length_cm": 100, "width_cm": 100, "height_cm": 100, "weight_kg": 100}]})
    assert r.status_code == 200 and r.json()["chargeable_weight_kg"] == 333.0


def test_intake_disabled_returns_503(client):
    r = client.post("/api/intake/parse", json={"text": "I need to ship 2 containers from Shanghai to Dubai"})
    assert r.status_code == 503
