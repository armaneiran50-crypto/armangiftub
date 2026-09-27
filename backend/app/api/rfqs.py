import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..models import RFQ, Booking, Dispatch, Provider, Quote, RFQStatus, User
from ..schemas import (BookingIn, BookingOut, ComplianceDecision, MilestoneIn, QuoteIn, QuoteOut, RFQIn, RFQOut,
                       RFQPublicOut, RFQUpdate)
from ..security import admin_only, staff
from ..services import audit, qualification
from ..services import notify
from ..services.quotes import compare, is_expired
from ..services.quoting import submit_quote
from ..services.scoring import lane_of, match, rank_prices

router = APIRouter(prefix="/api/rfqs", tags=["rfqs"])
bookings_router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def new_reference() -> str:
    return "LR-" + secrets.token_hex(5).upper()


def get_rfq(db: Session, rfq_id: int) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    return rfq


# ---------- Public intake ----------

@router.post("", response_model=RFQPublicOut, status_code=201)
def create_rfq(body: RFQIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Public endpoint: anyone can submit an RFQ (free for cargo owners, §6)."""
    rfq = RFQ(reference=new_reference(), **body.model_dump())
    qualification.apply(rfq)
    db.add(rfq)
    db.flush()
    audit.log(db, body.contact_email or "anonymous", "rfq.create", "rfq", rfq.id,
              {"status": rfq.status, "flags": rfq.flags}, source=body.source)
    db.commit()
    background.add_task(*notify.rfq_received(rfq.contact_email, rfq.reference))
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
def dispatch_rfq(rfq_id: int, background: BackgroundTasks, provider_ids: list[int] | None = None,
                 db: Session = Depends(get_db), user: User = Depends(staff)):
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
        provider = db.get(Provider, r["provider_id"])
        provider.rfqs_dispatched += 1
        sent.append(r["provider_id"])
        background.add_task(*notify.rfq_dispatched(provider.company.contact_email, rfq.reference, lane_of(rfq), rfq.mode))
    if rfq.status == RFQStatus.qualified:
        rfq.status = RFQStatus.dispatched
        rfq.dispatched_at = datetime.now(timezone.utc)
    audit.log(db, user.email, "rfq.dispatch", "rfq", rfq.id, {"providers": sent})
    db.commit()
    return {"dispatched_to": sent, "status": rfq.status}


@router.get("/{rfq_id}/dispatches")
def rfq_dispatches(rfq_id: int, db: Session = Depends(get_db), _: User = Depends(staff)):
    rfq = get_rfq(db, rfq_id)
    return [{"provider_id": d.provider_id, "company": d.provider.company.legal_name, "match_score": d.match_score,
             "sent_at": d.sent_at, "responded_at": d.responded_at, "declined_at": d.declined_at,
             "decline_reason": d.decline_reason} for d in rfq.dispatches]


@router.post("/{rfq_id}/quotes", response_model=QuoteOut, status_code=201)
def add_quote(rfq_id: int, body: QuoteIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    """Quote capture by Ops for quotes received by email/WhatsApp. Providers can also quote in the portal."""
    quote = submit_quote(db, get_rfq(db, rfq_id), body.provider_id, currency=body.currency,
                         charges=[c.model_dump() for c in body.charges], transit_days=body.transit_days,
                         valid_until=body.valid_until, exclusions=body.exclusions, actor=user.email, via="ops")
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
def book(rfq_id: int, body: BookingIn, background: BackgroundTasks, db: Session = Depends(get_db),
         user: User = Depends(staff)):
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
    background.add_task(*notify.quote_won(quote.provider.company.contact_email, rfq.reference))
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
