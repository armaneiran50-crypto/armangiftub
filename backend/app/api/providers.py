from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Company, Provider, User
from ..schemas import ProviderIn, ProviderOut, ProviderUpdate
from ..security import admin_only, staff
from ..services import audit
from ..services.scoring import provider_score

router = APIRouter(prefix="/api/providers", tags=["providers"])


def to_out(p: Provider) -> ProviderOut:
    s = provider_score(p)
    return ProviderOut(id=p.id, company_id=p.company_id, legal_name=p.company.legal_name, country=p.company.country,
                       lanes=p.lanes, modes=p.modes, cargo_classes=p.cargo_classes, tier=p.tier,
                       verified=p.verified, suspended=p.suspended, score=s["score"], score_components=s["components"])


@router.get("", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db), _: User = Depends(staff)):
    rows = db.scalars(select(Provider).options(joinedload(Provider.company)).order_by(Provider.id)).all()
    return sorted((to_out(p) for p in rows), key=lambda o: o.score, reverse=True)


@router.post("", response_model=ProviderOut, status_code=201)
def create_provider(body: ProviderIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    company = Company(legal_name=body.legal_name, country=body.country, contact_email=body.contact_email,
                      is_provider=True, kyb_status="verified" if body.verified else "pending")
    db.add(company)
    db.flush()
    p = Provider(company_id=company.id, lanes=body.lanes, modes=list(body.modes), cargo_classes=list(body.cargo_classes),
                 ports=body.ports, certifications=body.certifications, tier=body.tier, verified=body.verified)
    p.company = company
    db.add(p)
    db.flush()
    audit.log(db, user.email, "provider.create", "provider", p.id, {"lanes": body.lanes})
    db.commit()
    return to_out(p)


@router.patch("/{provider_id}", response_model=ProviderOut)
def update_provider(provider_id: int, body: ProviderUpdate, db: Session = Depends(get_db), user: User = Depends(staff)):
    p = db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    changes = body.model_dump(exclude_unset=True)
    # Suspension is a sensitive decision (RACI §18): admin only.
    if "suspended" in changes and user.role != "admin":
        admin_only(user)
    for k, v in changes.items():
        setattr(p, k, list(v) if isinstance(v, list) else v)
    if "verified" in changes:
        p.company.kyb_status = "verified" if p.verified else "pending"
    audit.log(db, user.email, "provider.update", "provider", p.id, changes)
    db.commit()
    return to_out(p)
