"""RFQ qualification: completeness, compliance flags and lead score (masterplan §8 step 3, §16, §17).

Flags never auto-reject: anything that needs a judgment call moves the RFQ to
``compliance_hold`` so a human reviews it before dispatch (human-in-the-loop).
"""
from dataclasses import dataclass, field

from ..models import RFQ, Mode, RFQStatus

REQUIRED_FIELDS = ["origin_country", "destination_country", "mode", "commodity", "weight_kg", "ready_date", "contact_email"]
MODE_FIELDS = {
    Mode.ocean_fcl: ["containers"],
    Mode.ocean_lcl: ["volume_cbm"],
    Mode.air: ["volume_cbm"],
    Mode.road: [],
}
OPTIONAL_FIELDS = ["incoterm", "packages", "hs_code", "origin_city", "destination_city"]

# Jurisdictions that always require specialist review before any dispatch (§17).
# This is a routing rule for human review, not a legal determination.
REVIEW_COUNTRIES = {"IR", "KP", "SY", "CU", "RU", "BY"}

# Cargo that needs specialist handling / DG-certified providers.
DG_KEYWORDS = ["battery", "batteries", "lithium", "flammable", "chemical", "explosive", "gas cylinder",
               "aerosol", "paint", "corrosive", "radioactive", "باتری", "شیمیایی", "اشتعال"]
# Potentially controlled / dual-use goods — export-control questions required.
CONTROLLED_KEYWORDS = ["weapon", "ammunition", "military", "drone", "uav", "night vision", "encryption",
                       "centrifuge", "nuclear", "سلاح", "مهمات", "نظامی", "پهپاد"]


@dataclass
class Qualification:
    completeness: float
    missing_fields: list[str]
    flags: list[str] = field(default_factory=list)
    lead_score: float = 0.0
    status: RFQStatus = RFQStatus.started


def _text(rfq: RFQ) -> str:
    return " ".join(filter(None, [rfq.commodity, rfq.notes, rfq.cargo_class])).lower()


def qualify(rfq: RFQ) -> Qualification:
    required = REQUIRED_FIELDS + MODE_FIELDS.get(rfq.mode, []) if rfq.mode else REQUIRED_FIELDS
    missing = [f for f in required if getattr(rfq, f) in (None, "")]
    optional_present = sum(1 for f in OPTIONAL_FIELDS if getattr(rfq, f) not in (None, ""))
    completeness = round(0.85 * (1 - len(missing) / len(required)) + 0.15 * optional_present / len(OPTIONAL_FIELDS), 3)

    flags: list[str] = []
    for side, country in (("origin", rfq.origin_country), ("destination", rfq.destination_country)):
        if country and country.upper() in REVIEW_COUNTRIES:
            flags.append(f"restricted_jurisdiction:{side}:{country.upper()}")
    text = _text(rfq)
    if rfq.cargo_class == "dg" or any(k in text for k in DG_KEYWORDS):
        flags.append("dangerous_goods")
    if any(k in text for k in CONTROLLED_KEYWORDS):
        flags.append("controlled_goods")

    hold = any(f.startswith("restricted_jurisdiction") or f == "controlled_goods" for f in flags)
    if hold:
        status = RFQStatus.compliance_hold
    elif not missing:
        status = RFQStatus.qualified
    else:
        status = RFQStatus.started

    return Qualification(completeness, missing, flags, lead_score(rfq, completeness, flags), status)


def lead_score(rfq: RFQ, completeness: float, flags: list[str]) -> float:
    """0–100. Shipment value proxy + urgency + completeness − compliance risk (§16)."""
    score = 40 * completeness
    size = 0.0
    if rfq.containers:
        try:
            size = min(1.0, sum(int(p.split("x")[0]) for p in rfq.containers.split(",") if "x" in p) / 5)
        except ValueError:
            size = 0.3
    elif rfq.weight_kg:
        size = min(1.0, rfq.weight_kg / 20000)
    score += 30 * size
    if rfq.mode == Mode.air:
        score += 10  # air RFQs are usually time-sensitive
    if rfq.company_name:
        score += 10
    if rfq.contact_phone:
        score += 10
    if any(f.startswith("restricted_jurisdiction") or f == "controlled_goods" for f in flags):
        score -= 30
    return round(max(0.0, min(100.0, score)), 1)


def apply(rfq: RFQ) -> Qualification:
    q = qualify(rfq)
    rfq.completeness = q.completeness
    rfq.missing_fields = q.missing_fields
    rfq.flags = q.flags
    rfq.lead_score = q.lead_score
    if rfq.status in (None, RFQStatus.started, RFQStatus.qualified, RFQStatus.compliance_hold):
        rfq.status = q.status
    return q
