"""RFQ Intake Agent (masterplan §10).

Turns free text (chat / WhatsApp / email, Persian or English) into a draft RFQ.
The output is a *draft*: it is schema-validated here and again by ``RFQIn`` and is
never dispatched without the customer or Ops confirming it.
"""
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from ..config import get_settings

SYSTEM = """You extract international freight shipping requests into a structured RFQ.
Input may be in Persian, Arabic or English. Rules:
- Only fill a field when the text states it or it is unambiguous (e.g. "Shanghai" -> origin_country "CN").
- Countries are ISO-3166 alpha-2 codes. Dates are YYYY-MM-DD; leave ready_date empty if no date is given.
- Convert tonnes to kg. containers uses the form "2x40HC" (types 20GP, 40GP, 40HC, 45HC, 20RF, 40RF), comma separated.
- mode: ocean_fcl when full containers are mentioned, ocean_lcl for sea shipments smaller than a container,
  air, or road. Leave empty if unclear.
- cargo_class "dg" for batteries, chemicals, flammables or other dangerous goods.
- List in `questions` (in the language of the input) what the customer must still answer to get a quote.
Never invent contact details, weights or dates."""


class RFQDraft(BaseModel):
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    company_name: str | None = None
    origin_country: str | None = None
    origin_city: str | None = None
    destination_country: str | None = None
    destination_city: str | None = None
    mode: Literal["ocean_fcl", "ocean_lcl", "air", "road"] | None = None
    commodity: str | None = None
    hs_code: str | None = None
    cargo_class: Literal["general", "dg", "reefer", "oversized", "fragile", "high_value"] | None = None
    weight_kg: float | None = None
    volume_cbm: float | None = None
    packages: int | None = None
    containers: str | None = None
    incoterm: Literal["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"] | None = None
    ready_date: str | None = None
    questions: list[str] = Field(default_factory=list)


class IntakeUnavailable(Exception):
    pass


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def extract(text: str) -> tuple[RFQDraft, dict]:
    settings = get_settings()
    if not settings.ai_enabled:
        raise IntakeUnavailable("AI intake is disabled (set LOGIRAD_AI_ENABLED=true and ANTHROPIC_API_KEY).")
    try:
        response = _get_client().beta.messages.parse(
            model=settings.ai_model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": text}],
            output_format=RFQDraft,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        raise IntakeUnavailable("AI provider rate limited; try again shortly.") from e
    except anthropic.APIStatusError as e:
        raise IntakeUnavailable(f"AI provider error ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise IntakeUnavailable("Could not reach AI provider.") from e

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise IntakeUnavailable("AI could not process this request; please use the form.")
    usage = {"model": response.model, "input_tokens": response.usage.input_tokens,
             "output_tokens": response.usage.output_tokens}
    return response.parsed_output, usage
