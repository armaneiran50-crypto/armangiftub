"""Provider score and RFQ→provider matching (masterplan §13, §8 step 4).

Score weights (initial, to be recalibrated with real data):
25% response time + 20% quote completeness + 20% price competitiveness
+ 15% booking success + 10% exception performance + 10% compliance/documentation.
"""
from ..models import RFQ, Provider, ProviderTier

WEIGHTS = {
    "response_time": 0.25,
    "quote_completeness": 0.20,
    "price": 0.20,
    "booking_success": 0.15,
    "exceptions": 0.10,
    "compliance": 0.10,
}
NEUTRAL = 0.6  # prior for providers with no history yet
TARGET_RESPONSE_HOURS = 24.0


def provider_score(p: Provider) -> dict:
    parts: dict[str, float] = {}
    if p.quotes_submitted:
        avg_h = p.total_response_hours / p.quotes_submitted
        parts["response_time"] = max(0.0, min(1.0, 1 - (avg_h - 2) / (TARGET_RESPONSE_HOURS * 2)))
        parts["quote_completeness"] = p.completeness_sum / p.quotes_submitted
    else:
        parts["response_time"] = parts["quote_completeness"] = NEUTRAL
    # price_rank_sum stores normalized ranks within each RFQ (1.0 = cheapest)
    parts["price"] = p.price_rank_sum / p.quotes_ranked if p.quotes_ranked else NEUTRAL
    if p.rfqs_dispatched and p.quotes_submitted:
        # response rate modulates the response-time component
        parts["response_time"] *= min(1.0, p.quotes_submitted / p.rfqs_dispatched)
    parts["booking_success"] = p.bookings_completed / p.bookings_won if p.bookings_won else NEUTRAL
    done = max(p.bookings_completed, 1)
    parts["exceptions"] = max(0.0, 1 - p.exceptions / done) if p.bookings_completed else NEUTRAL
    parts["compliance"] = max(0.0, 1 - 0.25 * p.compliance_issues) if p.verified else 0.4
    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return {"score": round(100 * total, 1), "components": {k: round(v, 3) for k, v in parts.items()}}


def rank_prices(quotes: list) -> None:
    """Credit each provider with a normalized price rank once an RFQ's quote round closes."""
    by_ccy: dict[str, list] = {}
    for q in quotes:
        if q.status != "rejected":
            by_ccy.setdefault(q.currency, []).append(q)
    for group in by_ccy.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda q: q.total)
        n = len(group) - 1
        for i, q in enumerate(group):
            q.provider.price_rank_sum += 1 - i / n
            q.provider.quotes_ranked += 1


def lane_of(rfq: RFQ) -> str:
    return f"{(rfq.origin_country or '').upper()}->{(rfq.destination_country or '').upper()}"


def match(rfq: RFQ, providers: list[Provider]) -> list[dict]:
    """Rank eligible providers. Hard filters: mode, lane, not suspended, DG capability when flagged."""
    lane = lane_of(rfq)
    wildcard_origin = f"*->{(rfq.destination_country or '').upper()}"
    wildcard_dest = f"{(rfq.origin_country or '').upper()}->*"
    needs_dg = "dangerous_goods" in (rfq.flags or [])
    ranked = []
    for p in providers:
        if p.suspended or (rfq.mode and rfq.mode not in (p.modes or [])):
            continue
        lanes = {l.upper() for l in (p.lanes or [])}
        if lane in lanes:
            lane_fit = 1.0
        elif wildcard_origin in lanes or wildcard_dest in lanes:
            lane_fit = 0.7
        else:
            continue
        if needs_dg and "dg" not in (p.cargo_classes or []):
            continue
        s = provider_score(p)
        tier_bonus = {ProviderTier.preferred: 5, ProviderTier.standard: 0, ProviderTier.probation: -10}.get(p.tier, 0)
        match_score = round(0.7 * s["score"] + 30 * lane_fit + tier_bonus, 1)
        ranked.append({
            "provider_id": p.id,
            "company": p.company.legal_name if p.company else None,
            "tier": p.tier,
            "verified": p.verified,
            "lane_fit": lane_fit,
            "provider_score": s["score"],
            "match_score": match_score,
        })
    ranked.sort(key=lambda r: r["match_score"], reverse=True)
    return ranked
