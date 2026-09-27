from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ModeT = Literal["ocean_fcl", "ocean_lcl", "air", "road"]
CargoClassT = Literal["general", "dg", "reefer", "oversized", "fragile", "high_value"]
IncotermT = Literal["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]


def _upper2(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    v = v.strip().upper()
    if len(v) != 2 or not v.isalpha():
        raise ValueError("must be an ISO-3166 alpha-2 country code")
    return v


class RFQIn(BaseModel):
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    company_name: str | None = None
    origin_country: str | None = None
    origin_city: str | None = None
    destination_country: str | None = None
    destination_city: str | None = None
    mode: ModeT | None = None
    commodity: str | None = Field(None, max_length=255)
    hs_code: str | None = None
    cargo_class: CargoClassT | None = "general"
    weight_kg: float | None = Field(None, gt=0)
    volume_cbm: float | None = Field(None, gt=0)
    packages: int | None = Field(None, gt=0)
    containers: str | None = Field(None, pattern=r"^\d+x(20GP|40GP|40HC|45HC|20RF|40RF)(,\d+x(20GP|40GP|40HC|45HC|20RF|40RF))*$")
    incoterm: IncotermT | None = None
    ready_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: str | None = Field(None, max_length=4000)
    source: str = "web"

    _cc = field_validator("origin_country", "destination_country")(_upper2)


class RFQUpdate(RFQIn):
    source: str | None = None  # type: ignore[assignment]


class RFQOut(RFQIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reference: str
    status: str
    completeness: float
    lead_score: float
    flags: list[str]
    missing_fields: list[str]
    created_at: datetime
    contact_email: str | None = None  # type: ignore[assignment]


class RFQPublicOut(BaseModel):
    reference: str
    status: str
    completeness: float
    missing_fields: list[str]


def _normalize_lanes(v: list[str] | None) -> list[str] | None:
    if v is None:
        return None
    out = []
    for lane in v:
        parts = lane.upper().replace(" ", "").split("->")
        if len(parts) != 2 or not all(p == "*" or (len(p) == 2 and p.isalpha()) for p in parts) or parts == ["*", "*"]:
            raise ValueError(f"lane '{lane}' must look like 'CN->AE' ('*' allowed on one side)")
        out.append("->".join(parts))
    return out


class ProviderIn(BaseModel):
    legal_name: str
    country: str
    contact_email: EmailStr | None = None
    lanes: list[str] = []
    modes: list[ModeT] = []
    cargo_classes: list[CargoClassT] = ["general"]
    ports: list[str] = []
    certifications: list[str] = []
    tier: Literal["preferred", "standard", "probation"] = "standard"
    verified: bool = False

    _cc = field_validator("country")(_upper2)

    _lanes = field_validator("lanes")(_normalize_lanes)


class ProviderUpdate(BaseModel):
    lanes: list[str] | None = None
    modes: list[ModeT] | None = None
    cargo_classes: list[CargoClassT] | None = None
    tier: Literal["preferred", "standard", "probation"] | None = None
    verified: bool | None = None
    suspended: bool | None = None

    _lanes = field_validator("lanes")(_normalize_lanes)


class ProviderOut(BaseModel):
    id: int
    company_id: int
    legal_name: str
    country: str
    lanes: list[str]
    modes: list[str]
    cargo_classes: list[str]
    tier: str
    verified: bool
    suspended: bool
    score: float
    score_components: dict


class ChargeLine(BaseModel):
    name: str
    amount: float = Field(ge=0)
    category: Literal["freight", "origin", "destination", "other"] | None = None


class QuoteIn(BaseModel):
    provider_id: int
    currency: str = Field("USD", min_length=3, max_length=3)
    charges: list[ChargeLine] = Field(min_length=1)
    transit_days: int | None = Field(None, gt=0)
    valid_until: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    exclusions: str | None = None


class QuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rfq_id: int
    provider_id: int
    currency: str
    charges: list[dict]
    total: float
    transit_days: int | None
    valid_until: str | None
    exclusions: str | None
    completeness: float
    status: str


class BookingIn(BaseModel):
    quote_id: int
    platform_fee: float = Field(0, ge=0)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rfq_id: int
    quote_id: int
    status: str
    milestones: list
    platform_fee: float
    created_at: datetime


class MilestoneIn(BaseModel):
    status: Literal["in_transit", "delivered", "cancelled"] | None = None
    event: str
    exception: bool = False


class ComplianceDecision(BaseModel):
    decision: Literal["release", "reject"]
    reason: str = Field(min_length=5)


class CalcItem(BaseModel):
    length_cm: float = Field(gt=0)
    width_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    quantity: int = Field(1, gt=0)


class CalcIn(BaseModel):
    mode: ModeT
    items: list[CalcItem] = Field(min_length=1)


class IntakeIn(BaseModel):
    text: str = Field(min_length=10, max_length=8000)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["admin", "ops", "provider", "customer"] = "ops"


class ProviderUserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
