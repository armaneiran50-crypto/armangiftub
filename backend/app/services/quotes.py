"""Quote normalization and apples-to-apples comparison (masterplan §8 steps 6–7)."""
from datetime import date

CATEGORIES = ("freight", "origin", "destination", "other")
# Keyword → category, used when a charge line arrives without a category.
_CATEGORY_HINTS = {
    "freight": ["freight", "ocean", "air", "trucking", "haulage", "baf", "caf", "fuel", "fsc", "security", "war risk", "peak"],
    "origin": ["origin", "pickup", "pick-up", "export", "loading", "thc origin", "otHC", "vgm", "documentation fee"],
    "destination": ["destination", "delivery", "import", "dthc", "d/o", "delivery order", "unloading", "customs clearance"],
}
QUOTE_FIELDS = ["charges", "transit_days", "valid_until", "currency"]


def categorize(name: str, category: str | None) -> str:
    if category in CATEGORIES:
        return category
    n = name.lower()
    for cat, hints in _CATEGORY_HINTS.items():
        if any(h.lower() in n for h in hints):
            return cat
    return "other"


def normalize_charges(lines: list[dict]) -> list[dict]:
    out = []
    for line in lines:
        amount = float(line.get("amount", 0) or 0)
        out.append({"category": categorize(line.get("name", ""), line.get("category")),
                    "name": line.get("name", "").strip() or "charge", "amount": round(amount, 2)})
    return out


def totals_by_category(charges: list[dict]) -> dict:
    t = {c: 0.0 for c in CATEGORIES}
    for c in charges:
        t[c["category"]] = round(t[c["category"]] + c["amount"], 2)
    return t


def quote_completeness(charges: list[dict], transit_days, valid_until, exclusions) -> float:
    cats = {c["category"] for c in charges}
    score = 0.4 if "freight" in cats else 0.0
    score += 0.1 if "origin" in cats else 0.0
    score += 0.1 if "destination" in cats else 0.0
    score += 0.15 if transit_days else 0.0
    score += 0.15 if valid_until else 0.0
    score += 0.1 if exclusions else 0.0
    return round(score, 2)


def is_expired(valid_until: str | None, today: date | None = None) -> bool:
    if not valid_until:
        return False
    try:
        return date.fromisoformat(valid_until) < (today or date.today())
    except ValueError:
        return False


def compare(quotes: list) -> dict:
    """Return quotes sorted by total with per-category breakdown and simple trade-off labels."""
    valid = [q for q in quotes if q.status != "rejected"]
    currencies = {q.currency for q in valid}
    rows = []
    for q in valid:
        rows.append({
            "quote_id": q.id,
            "provider_id": q.provider_id,
            "company": q.provider.company.legal_name if q.provider and q.provider.company else None,
            "currency": q.currency,
            "total": q.total,
            "by_category": totals_by_category(q.charges),
            "transit_days": q.transit_days,
            "valid_until": q.valid_until,
            "expired": is_expired(q.valid_until),
            "completeness": q.completeness,
            "exclusions": q.exclusions,
            "labels": [],
        })
    live = [r for r in rows if not r["expired"]]
    if live and len(currencies) == 1:
        min(live, key=lambda r: r["total"])["labels"].append("cheapest")
        timed = [r for r in live if r["transit_days"]]
        if timed:
            min(timed, key=lambda r: r["transit_days"])["labels"].append("fastest")
        best = max(live, key=lambda r: r["completeness"])
        if best["completeness"] >= 0.8:
            best["labels"].append("most_complete")
    rows.sort(key=lambda r: (r["expired"], r["total"]))
    return {
        "comparable": len(currencies) <= 1,
        "currencies": sorted(currencies),
        "note": None if len(currencies) <= 1 else "Quotes are in different currencies; convert before comparing totals.",
        "quotes": rows,
    }
