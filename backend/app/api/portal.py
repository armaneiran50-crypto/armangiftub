"""Provider portal (masterplan §7, §13).

Providers see only RFQs dispatched to them, with the cargo owner's identity and contact
details withheld: the relationship and the transaction stay on the platform.
"""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RFQ, Dispatch, Provider, Role, RFQStatus, User
from ..schemas import ChargeLine, QuoteOut
from ..security import require
from ..services import audit
from ..services.quoting import submit_quote
from ..services.scoring import lane_of, provider_score

router = APIRouter(prefix="/api/portal", tags=["portal"])
provider_user = require(Role.provider)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
OPEN = (RFQStatus.dispatched, RFQStatus.quoted)


def redact(text: str | None) -> str | None:
    if not text:
        return text
    return _URL.sub("[link hidden]", _PHONE.sub("[phone hidden]", _EMAIL.sub("[email hidden]", text)))


class PortalQuoteIn(BaseModel):
    currency: str = Field("USD", min_length=3, max_length=3)
    charges: list[ChargeLine] = Field(min_length=1)
    transit_days: int | None = Field(None, gt=0)
    valid_until: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    exclusions: str | None = Field(None, max_length=1000)


class DeclineIn(BaseModel):
    reason: str = Field(min_length=2, max_length=255)


def my_provider(user: User, db: Session) -> Provider:
    p = db.scalar(select(Provider).where(Provider.company_id == user.company_id)) if user.company_id else None
    if not p:
        raise HTTPException(403, "This account is not linked to a provider")
    if p.suspended:
        raise HTTPException(403, "Provider account is suspended")
    return p


def my_dispatch(db: Session, provider: Provider, rfq_id: int) -> Dispatch:
    d = db.scalar(select(Dispatch).where(Dispatch.rfq_id == rfq_id, Dispatch.provider_id == provider.id))
    if not d:
        raise HTTPException(404, "RFQ not found")
    return d


def _state(rfq: RFQ, d: Dispatch, quote) -> str:
    if quote is not None:
        return {"submitted": "quoted", "accepted": "won", "rejected": "lost"}.get(quote.status, quote.status)
    if d.declined_at:
        return "declined"
    return "pending" if rfq.status in OPEN else "closed"


def _view(rfq: RFQ, d: Dispatch, provider_id: int, detail: bool = False) -> dict:
    quotes = [q for q in rfq.quotes if q.provider_id == provider_id]
    quote = max(quotes, key=lambda q: q.id) if quotes else None
    out = {
        "rfq_id": rfq.id, "reference": rfq.reference, "lane": lane_of(rfq),
        "origin_city": rfq.origin_city, "destination_city": rfq.destination_city,
        "mode": rfq.mode, "commodity": rfq.commodity, "cargo_class": rfq.cargo_class,
        "weight_kg": rfq.weight_kg, "volume_cbm": rfq.volume_cbm, "packages": rfq.packages,
        "containers": rfq.containers, "incoterm": rfq.incoterm, "ready_date": rfq.ready_date,
        "dispatched_at": d.sent_at, "state": _state(rfq, d, quote), "open": rfq.status in OPEN,
    }
    if detail:
        out["hs_code"] = rfq.hs_code
        out["notes"] = redact(rfq.notes)
        out["decline_reason"] = d.decline_reason
        out["quote"] = QuoteOut.model_validate(quote).model_dump() if quote else None
    return out


@router.get("/me")
def me(user: User = Depends(provider_user), db: Session = Depends(get_db)):
    p = my_provider(user, db)
    s = provider_score(p)
    return {"company": p.company.legal_name, "tier": p.tier, "verified": p.verified, "lanes": p.lanes,
            "modes": p.modes, "cargo_classes": p.cargo_classes, "score": s["score"], "components": s["components"],
            "stats": {"rfqs_received": p.rfqs_dispatched, "quotes_submitted": p.quotes_submitted,
                      "bookings_won": p.bookings_won, "bookings_completed": p.bookings_completed}}


@router.get("/rfqs")
def list_rfqs(user: User = Depends(provider_user), db: Session = Depends(get_db)):
    p = my_provider(user, db)
    dispatches = db.scalars(select(Dispatch).where(Dispatch.provider_id == p.id).order_by(Dispatch.id.desc())).all()
    return [_view(d.rfq, d, p.id) for d in dispatches]


@router.get("/rfqs/{rfq_id}")
def read_rfq(rfq_id: int, user: User = Depends(provider_user), db: Session = Depends(get_db)):
    p = my_provider(user, db)
    d = my_dispatch(db, p, rfq_id)
    return _view(d.rfq, d, p.id, detail=True)


@router.post("/rfqs/{rfq_id}/quote", response_model=QuoteOut, status_code=201)
def quote(rfq_id: int, body: PortalQuoteIn, background: BackgroundTasks, user: User = Depends(provider_user),
          db: Session = Depends(get_db)):
    p = my_provider(user, db)
    d = my_dispatch(db, p, rfq_id)
    q = submit_quote(db, d.rfq, p.id, currency=body.currency, charges=[c.model_dump() for c in body.charges],
                     transit_days=body.transit_days, valid_until=body.valid_until,
                     exclusions=redact(body.exclusions), actor=user.email, via="portal", background=background)
    db.commit()
    return q


@router.post("/rfqs/{rfq_id}/decline")
def decline(rfq_id: int, body: DeclineIn, user: User = Depends(provider_user), db: Session = Depends(get_db)):
    p = my_provider(user, db)
    d = my_dispatch(db, p, rfq_id)
    if d.rfq.status not in OPEN:
        raise HTTPException(409, "RFQ is no longer open")
    if any(q.provider_id == p.id and q.status == "submitted" for q in d.rfq.quotes):
        raise HTTPException(409, "You already quoted this RFQ")
    d.declined_at = datetime.now(timezone.utc)
    d.decline_reason = body.reason
    audit.log(db, user.email, "dispatch.decline", "rfq", rfq_id, {"provider_id": p.id, "reason": body.reason},
              source="portal")
    db.commit()
    return {"state": "declined"}
