"""Quote submission shared by the Ops desk and the provider portal."""
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from ..models import RFQ, Provider, Quote, RFQStatus
from . import audit
from .quotes import normalize_charges, quote_completeness


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def submit_quote(db: Session, rfq: RFQ, provider_id: int, *, currency: str, charges: list[dict],
                 transit_days: int | None, valid_until: str | None, exclusions: str | None,
                 actor: str, via: str, background: BackgroundTasks | None = None) -> Quote:
    if rfq.status not in (RFQStatus.dispatched, RFQStatus.quoted):
        raise HTTPException(409, f"RFQ is {rfq.status}; quotes are accepted only while it is open for quotes")
    dispatch = next((d for d in rfq.dispatches if d.provider_id == provider_id), None)
    if not dispatch:
        raise HTTPException(422, "This provider was not dispatched for this RFQ")
    if any(q.provider_id == provider_id and q.status == "submitted" for q in rfq.quotes):
        raise HTTPException(409, "Provider already has an active quote; it must be rejected before requoting")
    lines = normalize_charges(charges)
    completeness = quote_completeness(lines, transit_days, valid_until, exclusions)
    quote = Quote(rfq_id=rfq.id, provider_id=provider_id, currency=currency.upper(), charges=lines,
                  total=round(sum(c["amount"] for c in lines), 2), transit_days=transit_days,
                  valid_until=valid_until, exclusions=exclusions, completeness=completeness, submitted_via=via)
    db.add(quote)
    provider = db.get(Provider, provider_id)
    now = datetime.now(timezone.utc)
    if dispatch.responded_at is None:
        dispatch.responded_at = now
        dispatch.declined_at = None
        provider.total_response_hours += (now - _utc(dispatch.sent_at)).total_seconds() / 3600
        provider.quotes_submitted += 1
        provider.completeness_sum += completeness
    first_quote = rfq.status == RFQStatus.dispatched
    rfq.status = RFQStatus.quoted
    db.flush()
    if first_quote and background is not None:
        from ..api.whatsapp import _deliver
        from .whatsapp import notify_rfq_customer

        queued = notify_rfq_customer(db, rfq, "quotes_ready")
        if queued:
            background.add_task(_deliver, db.get_bind(), *queued)
    audit.log(db, actor, "quote.create", "quote", quote.id, {"rfq_id": rfq.id, "total": quote.total, "via": via},
              source=via)
    return quote
