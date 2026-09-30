"""Quote Parser / Normalizer agent (masterplan §10).

Reads a forwarder's quote (pasted email/WhatsApp text or a PDF) and returns normalized charge lines.
The result is a draft shown to a person for review before anything is saved (human gate), and it is
checked against the quote's own stated total.
"""
import base64
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from ..config import get_settings
from .client import get_client

MAX_PDF_BYTES = 10 * 1024 * 1024

SYSTEM = """You read freight quotes from forwarders and carriers and return them as structured charge lines.
Rules:
- One charge line per fee exactly as quoted. Never invent, merge or drop fees, and never convert currencies.
- If a fee is quoted per unit (per container, per CBM, per kg, per B/L), multiply by the quantities of the
  shipment described in the request context and put the calculation in the line name, e.g. "Ocean freight 2 x 1,200/40HC".
  If the quantity is unknown, keep the unit price and add a warning.
- category: "freight" for the main carriage and its surcharges (BAF, CAF, PSS, war risk, fuel/FSC, security);
  "origin" for charges at origin (pickup, export clearance, origin THC, documentation, VGM, loading);
  "destination" for charges at destination (DTHC, delivery order, import clearance, delivery, unloading);
  "other" for anything else (insurance, inspection, admin).
- Charges marked as optional, "if required", "at cost" or "subject to" go in `exclusions`, not in charges.
- currency: ISO 4217 code of the quote. If lines use different currencies, use the currency of the freight line,
  keep other lines out of `charges` and describe them in `warnings`.
- transit_days: the quoted transit time in days (use the upper bound of a range). valid_until: YYYY-MM-DD.
- stated_total: the total the document itself states, if any.
- Write warnings in Persian, briefly."""


class ParsedCharge(BaseModel):
    name: str
    amount: float = Field(ge=0)
    category: Literal["freight", "origin", "destination", "other"]


class QuoteDraft(BaseModel):
    currency: str
    charges: list[ParsedCharge]
    transit_days: int | None = None
    valid_until: str | None = None
    exclusions: str | None = None
    stated_total: float | None = None
    carrier_or_service: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ParserUnavailable(Exception):
    pass


def _context(rfq) -> str:
    parts = [f"Lane: {rfq.origin_country} -> {rfq.destination_country}", f"Mode: {rfq.mode}"]
    for label, value in (("Containers", rfq.containers), ("Volume CBM", rfq.volume_cbm), ("Weight kg", rfq.weight_kg),
                         ("Incoterm", rfq.incoterm), ("Commodity", rfq.commodity)):
        if value:
            parts.append(f"{label}: {value}")
    return "Shipment requested:\n" + "\n".join(parts)


def parse_quote(rfq, text: str | None = None, pdf: bytes | None = None) -> tuple[QuoteDraft, dict]:
    settings = get_settings()
    if not settings.ai_enabled:
        raise ParserUnavailable("AI is disabled (set LOGIRAD_AI_ENABLED=true and ANTHROPIC_API_KEY).")
    if not text and not pdf:
        raise ValueError("Provide quote text or a PDF")
    content: list[dict] = []
    if pdf:
        content.append({"type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf",
                                   "data": base64.standard_b64encode(pdf).decode()}})
    content.append({"type": "text", "text": _context(rfq) + "\n\nQuote to parse:\n" + (text or "(see the attached PDF)")})
    try:
        response = get_client().beta.messages.parse(
            model=settings.ai_model,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_format=QuoteDraft,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        raise ParserUnavailable("AI provider rate limited; try again shortly.") from e
    except anthropic.APIStatusError as e:
        raise ParserUnavailable(f"AI provider error ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise ParserUnavailable("Could not reach AI provider.") from e
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise ParserUnavailable("AI could not read this quote; please enter it manually.")

    draft = response.parsed_output
    draft.currency = draft.currency.strip().upper()[:3]
    total = round(sum(c.amount for c in draft.charges), 2)
    if draft.stated_total is not None and abs(draft.stated_total - total) > max(1.0, 0.005 * draft.stated_total):
        draft.warnings.append(f"جمع ردیف‌ها ({total:,.2f}) با جمع ذکرشده در سند ({draft.stated_total:,.2f}) یکی نیست؛ لطفاً بررسی کنید.")
    if not draft.charges:
        draft.warnings.append("هیچ ردیف هزینه‌ای پیدا نشد.")
    usage = {"model": response.model, "input_tokens": response.usage.input_tokens,
             "output_tokens": response.usage.output_tokens}
    return draft, usage
