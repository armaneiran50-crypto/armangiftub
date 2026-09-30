from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai import intake
from ..db import get_db
from ..models import RFQ, AuditEvent, Booking, Dispatch, Quote, RFQStatus, User
from ..schemas import CalcIn, IntakeIn
from ..security import staff
from ..services import audit
from ..services.calculator import compute

router = APIRouter(prefix="/api", tags=["tools"])


@router.post("/tools/chargeable-weight")
def chargeable_weight(body: CalcIn):
    return compute([i.model_dump() for i in body.items], body.mode)


@router.post("/intake/parse")
def parse_intake(body: IntakeIn, db: Session = Depends(get_db)):
    """AI intake: free text → draft RFQ for the customer to confirm. Never creates an RFQ by itself."""
    try:
        draft, usage = intake.extract(body.text)
    except intake.IntakeUnavailable as e:
        raise HTTPException(503, str(e))
    audit.log(db, "ai:intake", "ai.intake", "rfq", None, usage, source="ai")
    db.commit()
    return {"draft": draft.model_dump(exclude={"questions"}, exclude_none=True), "questions": draft.questions}


@router.get("/audit")
def audit_events(object_type: str | None = None, object_id: int | None = None, limit: int = Query(100, le=500),
                 db: Session = Depends(get_db), _: User = Depends(staff)):
    q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if object_type:
        q = q.where(AuditEvent.object_type == object_type)
    if object_id is not None:
        q = q.where(AuditEvent.object_id == object_id)
    return [{"id": e.id, "at": e.created_at, "actor": e.actor, "action": e.action, "object_type": e.object_type,
             "object_id": e.object_id, "data": e.data, "source": e.source} for e in db.scalars(q)]


@router.get("/kpis")
def kpis(db: Session = Depends(get_db), _: User = Depends(staff)):
    """Pilot KPIs (masterplan §21)."""
    total = db.scalar(select(func.count(RFQ.id))) or 0
    by_status = dict(db.execute(select(RFQ.status, func.count(RFQ.id)).group_by(RFQ.status)).all())
    qualified_or_later = total - by_status.get(RFQStatus.started, 0) - by_status.get(RFQStatus.rejected, 0) \
        - by_status.get(RFQStatus.compliance_hold, 0)
    dispatched_rfqs = db.scalar(select(func.count(func.distinct(Dispatch.rfq_id)))) or 0
    quoted_rfqs = db.scalar(select(func.count(func.distinct(Quote.rfq_id)))) or 0
    dispatches = db.scalar(select(func.count(Dispatch.id))) or 0
    responses = db.scalar(select(func.count(Dispatch.id)).where(Dispatch.responded_at.is_not(None))) or 0
    bookings = db.scalar(select(func.count(Booking.id))) or 0
    fees = db.scalar(select(func.coalesce(func.sum(Booking.platform_fee), 0.0))) or 0.0
    first_quote_hours = []
    for rfq_id, sent in db.execute(select(Dispatch.rfq_id, func.min(Dispatch.sent_at)).group_by(Dispatch.rfq_id)):
        first = db.scalar(select(func.min(Dispatch.responded_at)).where(Dispatch.rfq_id == rfq_id))
        if first:
            first_quote_hours.append((first - sent).total_seconds() / 3600)

    def ratio(a, b):
        return round(a / b, 3) if b else None

    return {
        "rfqs_total": total,
        "rfqs_by_status": by_status,
        "qualified_rfqs": qualified_or_later,
        "quote_coverage": ratio(quoted_rfqs, dispatched_rfqs),
        "provider_response_rate": ratio(responses, dispatches),
        "avg_time_to_first_quote_hours": round(sum(first_quote_hours) / len(first_quote_hours), 2)
        if first_quote_hours else None,
        "booking_conversion": ratio(bookings, qualified_or_later),
        "bookings": bookings,
        "gross_revenue": round(fees, 2),
        "revenue_per_shipment": ratio(fees, bookings),
    }
