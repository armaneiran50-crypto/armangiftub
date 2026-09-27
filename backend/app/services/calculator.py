"""CBM and chargeable-weight calculator (masterplan §15 tool page)."""
from ..models import Mode

# Volumetric divisors (kg per cbm equivalents)
AIR_KG_PER_CBM = 167.0     # IATA 1:6000
ROAD_KG_PER_CBM = 333.0    # common 1:3000
OCEAN_KG_PER_CBM = 1000.0  # LCL W/M: 1 cbm = 1 revenue ton


def compute(items: list[dict], mode: str) -> dict:
    total_cbm = 0.0
    total_kg = 0.0
    for it in items:
        qty = int(it.get("quantity", 1))
        cbm = it["length_cm"] * it["width_cm"] * it["height_cm"] / 1_000_000
        total_cbm += cbm * qty
        total_kg += float(it["weight_kg"]) * qty
    total_cbm = round(total_cbm, 3)
    factor = {Mode.air: AIR_KG_PER_CBM, Mode.road: ROAD_KG_PER_CBM}.get(mode, OCEAN_KG_PER_CBM)
    volumetric = round(total_cbm * factor, 2)
    chargeable = max(total_kg, volumetric)
    result = {
        "mode": mode,
        "total_cbm": total_cbm,
        "gross_weight_kg": round(total_kg, 2),
        "volumetric_weight_kg": volumetric,
        "chargeable_weight_kg": round(chargeable, 2),
        "basis": "volume" if volumetric > total_kg else "weight",
    }
    if mode in (Mode.ocean_lcl, Mode.ocean_fcl):
        result["revenue_tons"] = round(max(total_cbm, total_kg / 1000), 3)
    return result
