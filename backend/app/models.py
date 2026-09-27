"""Core data model (masterplan §11)."""
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    admin = "admin"
    ops = "ops"
    provider = "provider"
    customer = "customer"


class Mode(StrEnum):
    ocean_fcl = "ocean_fcl"
    ocean_lcl = "ocean_lcl"
    air = "air"
    road = "road"


class RFQStatus(StrEnum):
    # CRM stages (masterplan §16)
    started = "started"            # partial data
    qualified = "qualified"        # schema complete, no blocking flags
    compliance_hold = "compliance_hold"  # needs human review before dispatch
    dispatched = "dispatched"
    quoted = "quoted"
    booked = "booked"
    closed = "closed"
    rejected = "rejected"


class ProviderTier(StrEnum):
    preferred = "preferred"
    standard = "standard"
    probation = "probation"


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(2))
    kyb_status: Mapped[str] = mapped_column(String(32), default="pending")
    is_provider: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    provider: Mapped["Provider | None"] = relationship(back_populates="company", uselist=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=Role.customer)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Provider(Base):
    """Provider capability profile + running performance stats (§13)."""
    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True)
    # Lanes as "CN->AE" country-pair strings; modes / cargo classes as lists
    lanes: Mapped[list] = mapped_column(JSON, default=list)
    modes: Mapped[list] = mapped_column(JSON, default=list)
    cargo_classes: Mapped[list] = mapped_column(JSON, default=list)
    ports: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    tier: Mapped[str] = mapped_column(String(16), default=ProviderTier.standard)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)

    # Performance counters feeding the provider score
    rfqs_dispatched: Mapped[int] = mapped_column(Integer, default=0)
    quotes_submitted: Mapped[int] = mapped_column(Integer, default=0)
    total_response_hours: Mapped[float] = mapped_column(Float, default=0.0)
    completeness_sum: Mapped[float] = mapped_column(Float, default=0.0)
    price_rank_sum: Mapped[float] = mapped_column(Float, default=0.0)
    quotes_ranked: Mapped[int] = mapped_column(Integer, default=0)
    bookings_won: Mapped[int] = mapped_column(Integer, default=0)
    bookings_completed: Mapped[int] = mapped_column(Integer, default=0)
    exceptions: Mapped[int] = mapped_column(Integer, default=0)
    compliance_issues: Mapped[int] = mapped_column(Integer, default=0)

    company: Mapped[Company] = relationship(back_populates="provider")


class RFQ(Base):
    __tablename__ = "rfqs"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default=RFQStatus.started, index=True)
    source: Mapped[str] = mapped_column(String(32), default="web")

    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    company_name: Mapped[str | None] = mapped_column(String(255))

    origin_country: Mapped[str | None] = mapped_column(String(2))
    origin_city: Mapped[str | None] = mapped_column(String(128))
    destination_country: Mapped[str | None] = mapped_column(String(2))
    destination_city: Mapped[str | None] = mapped_column(String(128))
    mode: Mapped[str | None] = mapped_column(String(16))
    commodity: Mapped[str | None] = mapped_column(String(255))
    hs_code: Mapped[str | None] = mapped_column(String(16))
    cargo_class: Mapped[str | None] = mapped_column(String(32), default="general")
    weight_kg: Mapped[float | None] = mapped_column(Float)
    volume_cbm: Mapped[float | None] = mapped_column(Float)
    packages: Mapped[int | None] = mapped_column(Integer)
    containers: Mapped[str | None] = mapped_column(String(64))  # e.g. "2x40HC"
    incoterm: Mapped[str | None] = mapped_column(String(8))
    ready_date: Mapped[str | None] = mapped_column(String(10))  # ISO date
    notes: Mapped[str | None] = mapped_column(Text)

    completeness: Mapped[float] = mapped_column(Float, default=0.0)
    lead_score: Mapped[float] = mapped_column(Float, default=0.0)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dispatches: Mapped[list["Dispatch"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")


class Dispatch(Base):
    __tablename__ = "dispatches"
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(String(255))

    rfq: Mapped[RFQ] = relationship(back_populates="dispatches")
    provider: Mapped[Provider] = relationship()


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    # Normalized charge lines: [{"category": "freight|origin|destination|other", "name", "amount"}]
    charges: Mapped[list] = mapped_column(JSON, default=list)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    transit_days: Mapped[int | None] = mapped_column(Integer)
    valid_until: Mapped[str | None] = mapped_column(String(10))
    exclusions: Mapped[str | None] = mapped_column(Text)
    completeness: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="submitted")  # submitted|accepted|rejected|expired
    submitted_via: Mapped[str] = mapped_column(String(16), default="ops")  # ops|portal|ai
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rfq: Mapped[RFQ] = relationship(back_populates="quotes")
    provider: Mapped[Provider] = relationship()


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"), unique=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="confirmed")  # confirmed|in_transit|delivered|cancelled
    milestones: Mapped[list] = mapped_column(JSON, default=list)
    platform_fee: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), index=True)
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[int | None] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(32), default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WAConversation(Base):
    """A WhatsApp chat with one phone number (masterplan §14: WhatsApp = conversion + assisted intake)."""
    __tablename__ = "wa_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    wa_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # sender phone in E.164 digits
    name: Mapped[str | None] = mapped_column(String(255))
    lang: Mapped[str] = mapped_column(String(2), default="fa")
    state: Mapped[str] = mapped_column(String(32), default="idle")  # idle|collecting|confirming|handoff
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    rfq_id: Mapped[int | None] = mapped_column(ForeignKey("rfqs.id"))
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True)

    messages: Mapped[list["WAMessage"]] = relationship(back_populates="conversation", order_by="WAMessage.id",
                                                       cascade="all, delete-orphan")


class WAMessage(Base):
    __tablename__ = "wa_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("wa_conversations.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3))  # in|out
    body: Mapped[str] = mapped_column(Text)
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    sender: Mapped[str] = mapped_column(String(64), default="bot")  # bot|customer|<ops email>
    delivery: Mapped[str] = mapped_column(String(16), default="ok")  # ok|logged|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[WAConversation] = relationship(back_populates="messages")
