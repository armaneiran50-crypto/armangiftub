import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..models import RFQ, Booking, Dispatch, Provider, Quote, RFQStatus, User
from ..schemas import (BookingIn, BookingOut, ComplianceDecision, MilestoneIn, QuoteIn, QuoteOut, RFQIn, RFQOut,
                       RFQPublicOut, RFQUpdate)
from ..security import admin_only, staff
from ..services import audit, qualification
from ..services.quotes import compare, is_expired, normalize_charges, quote_completeness
from ..services.scoring import match, rank_prices

router = APIRouter(prefix="/api/rfqs", tags=["rfqs"])
bookings_router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def new_reference() -> str:
    return "LR-" + secrets.token_hex(5).upper()


def get_rfq(db: Session, rfq_id: int) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    return rfq


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- Public intake ----------

@router.post("", response_model=RFQPublicOut, status_code=201)
def create_rfq(body: RFQIn, db: Session = Depends(get_db)):
    """Public endpoint: anyone can submit an RFQ (free for cargo owners, §6)."""
    rfq = RFQ(reference=new_reference(), **body.model_dump())
    qualification.apply(rfq)
    db.add(rfq)
    db.flush()
    audit.log(db, body.contact_email or "anonymous", "rfq.create", "rfq", rfq.id,
              {"status": rfq.status, "flags": rfq.flags}, source=body.source)
    db.commit()
    return RFQPublicOut(reference=rfq.reference, status=rfq.status, completeness=rfq.completeness,
                        missing_fields=rfq.missing_fields)


@router.get("/track/{reference}", response_model=RFQPublicOut)
def track_rfq(reference: str, db: Session = Depends(get_db)):
    rfq = db.scalar(select(RFQ).where(RFQ.reference == reference.upper()))
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    return RFQPublicOut(reference=rfq.reference, status=rfq.status, completeness=rfq.completeness,
                        missing_fields=rfq.missing_fields)


# ---------- Ops desk ----------

@router.get("", response_model=list[RFQOut])
def list_rfqs(status: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
              db: Session = Depends(get_db), _: User = Depends(staff)):
    q = select(RFQ).order_by(RFQ.created_at.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(RFQ.status == status)
    return db.scalars(q).all()


@router.get("/{rfq_id}", response_model=RFQOut)
def read_rfq(rfq_id: int, db: Session = Depends(get_db), _: User = Depends(staff)):
    return get_rfq(db, rfq_id)


@router.patch("/{rfq_id}", response_model=RFQOut)
def update_rfq(rfq_id: int, body: RFQUpdate, db: Session = Depends(get_db), user: User = Depends(staff)):
    rfq = get_rfq(db, rfq_id)
    if rfq.status not in (RFQStatus.started, RFQStatus.qualified, RFQStatus.compliance_hold):
        raise HTTPException(409, f"RFQ is {rfq.status}; it can no longer be edited")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(rfq, k, v)
    qualification.apply(rfq)
    audit.log(db, user.email, "rfq.update", "rfq", rfq.id, {"fields": sorted(changes), "status": rfq.status})
    db.commit()
    return rfq


@router.post("/{rfq_id}/compliance", response_model=RFQOut)
def compliance_decision(rfq_id: int, body: ComplianceDecision, db: Session = Depends(get_db),
                        user: User = Depends(admin_only)):
    """Human gate for flagged RFQs (§17, RACI: authorized officer)."""
    rfq = get_rfq(db, rfq_id)
    if rfq.status != RFQStatus.compliance_hold:
        raise HTTPException(409, "RFQ is not on compliance hold")
    if body.decision == "reject":
        rfq.status = RFQStatus.rejected
    else:
        rfq.status = RFQStatus.qualified if not rfq.missing_fields else RFQStatus.started
        rfq.flags = [*rfq.flags, "compliance_released"]
    audit.log(db, user.email, f"compliance.{body.decision}", "rfq", rfq.id, {"reason": body.reason})
    db.commit()
    return rfq


@router.get("/{rfq_id}/matches")
def rfq_matches(rfq_id: int, db: Session = Depends(get_db), _: User = Depends(staff)):
    rfq = get_rfq(db, rfq_id)
    providers = db.scalars(select(Provider).options(selectinload(Provider.company))).all()
    return match(rfq, list(providers))


@router.post("/{rfq_id}/dispatch")
def dispatch_rfq(rfq_id: int, provider_ids: list[int] | None = None, db: Session = Depends(get_db),
                 user: User = Depends(staff)):
    """Send the RFQ to the top-N matched providers (or an explicit Ops-reviewed list)."""
    rfq = get_rfq(db, rfq_id)
    if rfq.status == RFQStatus.compliance_hold:
        raise HTTPException(409, "RFQ is on compliance hold; a compliance decision is required first")
    if rfq.status not in (RFQStatus.qualified, RFQStatus.dispatched, RFQStatus.quoted):
        raise HTTPException(409, f"RFQ must be qualified before dispatch (status: {rfq.status}, "
                                 f"missing: {', '.join(rfq.missing_fields) or '-'})")
    providers = db.scalars(select(Provider).options(selectinload(Provider.company))).all()
    ranked = match(rfq, list(providers))
    eligible = {r["provider_id"]: r for r in ranked}
    if provider_ids:
        bad = [pid for pid in provider_ids if pid not in eligible]
        if bad:
            raise HTTPException(422, f"Providers not eligible for this RFQ: {bad}")
        chosen = [eligible[pid] for pid in provider_ids]
    else:
        chosen = ranked[: get_settings().dispatch_top_n]
    if not chosen:
        raise HTTPException(422, "No eligible providers for this lane/mode")
    already = {d.provider_id for d in rfq.dispatches}
    sent = []
    for r in chosen:
        if r["provider_id"] in already:
            continue
        db.add(Dispatch(rfq_id=rfq.id, provider_id=r["provider_id"], match_score=r["match_score"]))
        db.get(Provider, r["provider_id"]).rfqs_dispatched += 1
        sent.append(r["provider_id"])
    if rfq.status == RFQStatus.qualified:
        rfq.status = RFQStatus.dispatched
        rfq.dispatched_at = datetime.now(timezone.utc)
    audit.log(db, user.email, "rfq.dispatch", "rfq", rfq.id, {"providers": sent})
    db.commit()
    return {"dispatched_to": sent, "status": rfq.status}


@router.post("/{rfq_id}/quotes", response_model=QuoteOut, status_code=201)
def add_quote(rfq_id: int, body: QuoteIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Quote capture. In the MVP Ops enters quotes received by email/WhatsApp (or via the AI parser)."""
    rfq = get_rfq(db, rfq_id)
    if rfq.status not in (RFQStatus.dispatched, RFQStatus.quoted):
        raise HTTPException(409, f"RFQ is {rfq.status}; quotes are accepted only after dispatch")
    dispatch = next((d for d in rfq.dispatches if d.provider_id == body.provider_id), None)
    if not dispatch:
        raise HTTPException(422, "This provider was not dispatched for this RFQ")
    if any(q.provider_id == body.provider_id and q.status == "submitted" for q in rfq.quotes):
        raise HTTPException(409, "Provider already has an active quote; reject it first to requote")
    charges = normalize_charges([c.model_dump() for c in body.charges])
    completeness = quote_completeness(charges, body.transit_days, body.valid_until, body.exclusions)
    quote = Quote(rfq_id=rfq.id, provider_id=body.provider_id, currency=body.currency.upper(), charges=charges,
                  total=round(sum(c["amount"] for c in charges), 2), transit_days=body.transit_days,
                  valid_until=body.valid_until, exclusions=body.exclusions, completeness=completeness)
    db.add(quote)
    provider = db.get(Provider, body.provider_id)
    now = datetime.now(timezone.utc)
    if dispatch.responded_at is None:
        dispatch.responded_at = now
        provider.total_response_hours += (now - _utc(dispatch.sent_at)).total_seconds() / 3600
        provider.quotes_submitted += 1
        provider.completeness_sum += completeness
    rfq.status = RFQStatus.quoted
    db.flush()
    audit.log(db, user.email, "quote.create", "quote", quote.id, {"rfq_id": rfq.id, "total": quote.total})
    db.commit()
    return quote


@router.post("/{rfq_id}/quotes/{quote_id}/reject", response_model=QuoteOut)
def reject_quote(rfq_id: int, quote_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    quote = db.get(Quote, quote_id)
    if not quote or quote.rfq_id != rfq_id:
        raise HTTPException(404, "Quote not found")
    if quote.status != "submitted":
        raise HTTPException(409, f"Quote is {quote.status}")
    quote.status = "rejected"
    audit.log(db, user.email, "quote.reject", "quote", quote.id, {})
    db.commit()
    return quote


@router.get("/{rfq_id}/compare")
def compare_quotes(rfq_id: int, db: Session = Depends(get_db), _: User = Depends(staff)):
    return compare(get_rfq(db, rfq_id).quotes)


@router.post("/{rfq_id}/book", response_model=BookingOut, status_code=201)
def book(rfq_id: int, body: BookingIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    rfq = get_rfq(db, rfq_id)
    if rfq.status != RFQStatus.quoted:
        raise HTTPException(409, f"RFQ is {rfq.status}; booking needs at least one quote")
    quote = db.get(Quote, body.quote_id)
    if not quote or quote.rfq_id != rfq.id or quote.status != "submitted":
        raise HTTPException(422, "Quote is not bookable")
    if is_expired(quote.valid_until):
        raise HTTPException(422, "Quote has expired; request a requote")
    # Rank prices among the quotes that competed, before losing quotes are marked rejected.
    rank_prices([q for q in rfq.quotes if q.status == "submitted" and not is_expired(q.valid_until)])
    for q in rfq.quotes:
        if q.status == "submitted":
            q.status = "accepted" if q.id == quote.id else "rejected"
    quote.provider.bookings_won += 1
    booking = Booking(rfq_id=rfq.id, quote_id=quote.id, platform_fee=body.platform_fee,
                      milestones=[{"at": datetime.now(timezone.utc).isoformat(), "event": "booking confirmed"}])
    rfq.status = RFQStatus.booked
    db.add(booking)
    db.flush()
    audit.log(db, user.email, "booking.create", "booking", booking.id,
              {"rfq_id": rfq.id, "quote_id": quote.id, "fee": body.platform_fee})
    db.commit()
    return booking


@bookings_router.get("", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db), _: User = Depends(staff)):
    return db.scalars(select(Booking).order_by(Booking.created_at.desc())).all()


@bookings_router.post("/{booking_id}/milestones", response_model=BookingOut)
def add_milestone(booking_id: int, body: MilestoneIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.status in ("delivered", "cancelled"):
        raise HTTPException(409, f"Booking is {booking.status}")
    provider = db.get(Quote, booking.quote_id).provider
    booking.milestones = [*booking.milestones, {"at": datetime.now(timezone.utc).isoformat(), "event": body.event,
                                                "exception": body.exception}]
    if body.exception:
        provider.exceptions += 1
    if body.status:
        booking.status = body.status
        if body.status == "delivered":
            provider.bookings_completed += 1
            db.get(RFQ, booking.rfq_id).status = RFQStatus.closed
    audit.log(db, user.email, "booking.milestone", "booking", booking.id, body.model_dump())
    db.commit()
    return booking
