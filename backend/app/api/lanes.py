"""Public lane data for SEO lane pages (masterplan §15: unique, useful data on every page).

Only aggregate, non-commercial figures are exposed: how many active providers serve the lane and
the median quoted transit time once enough quotes exist. Prices are never published.
"""
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RFQ, Provider, Quote

router = APIRouter(prefix="/api/lanes", tags=["lanes"])
MIN_QUOTES = 3  # below this, transit statistics are not shown


def _serves(p: Provider, origin: str, dest: str) -> bool:
    lanes = {l.upper() for l in p.lanes or []}
    return bool({f"{origin}->{dest}", f"*->{dest}", f"{origin}->*"} & lanes)


@router.get("/{origin}/{dest}")
def lane_stats(origin: str, dest: str, db: Session = Depends(get_db)):
    origin, dest = origin.upper(), dest.upper()
    if len(origin) != 2 or len(dest) != 2 or not (origin + dest).isalpha():
        raise HTTPException(422, "Use ISO country codes, e.g. /api/lanes/CN/AE")
    providers = [p for p in db.scalars(select(Provider).where(Provider.suspended.is_(False))) if _serves(p, origin, dest)]
    by_mode: dict[str, dict] = {}
    for p in providers:
        for m in p.modes or []:
            by_mode.setdefault(m, {"providers": 0, "verified_providers": 0})
            by_mode[m]["providers"] += 1
            by_mode[m]["verified_providers"] += int(p.verified)
    rows = db.execute(select(RFQ.mode, Quote.transit_days).join(Quote, Quote.rfq_id == RFQ.id)
                      .where(RFQ.origin_country == origin, RFQ.destination_country == dest,
                             Quote.transit_days.is_not(None))).all()
    transit: dict[str, list[int]] = {}
    for mode, days in rows:
        transit.setdefault(mode, []).append(days)
    for mode, days in transit.items():
        entry = by_mode.setdefault(mode, {"providers": 0, "verified_providers": 0})
        entry["quotes"] = len(days)
        if len(days) >= MIN_QUOTES:
            entry["median_transit_days"] = round(median(days))
    rfqs = db.scalar(select(RFQ.id).where(RFQ.origin_country == origin, RFQ.destination_country == dest).limit(1))
    return {"lane": f"{origin}->{dest}", "providers": len(providers), "has_history": rfqs is not None, "modes": by_mode}
