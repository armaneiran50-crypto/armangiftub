"""WhatsApp assisted intake (masterplan §14, §16).

A small state machine turns a chat into an RFQ:
  idle → collecting (ask for the next missing field) → confirming (summary, yes/no) → RFQ created.
When AI intake is enabled, the first free-text message is parsed by the intake agent so most fields
are filled at once; otherwise each field is asked for and parsed with simple rules. Anything the bot
cannot handle is flagged ``needs_human`` for the Ops desk, which can reply from the dashboard.
"""
import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import intake
from ..config import get_settings
from ..models import RFQ, RFQStatus, WAConversation, WAMessage
from . import audit, qualification
from .parsing import (find_containers, find_countries, find_country, find_date, find_email, find_mode,
                      find_volume_cbm, find_weight_kg, is_persian, normalize)

log = logging.getLogger("logirad.whatsapp")
SESSION_WINDOW_HOURS = 24  # WhatsApp only allows free-form replies within 24h of the customer's last message

T = {
    "welcome": {
        "fa": "سلام! به لجی‌راد خوش آمدید 👋\nبرای دریافت قیمت حمل، مشخصات بار را بنویسید (مبدأ، مقصد، نوع کالا، وزن، تاریخ آمادگی) یا به سؤال‌ها جواب دهید.",
        "en": "Hi! Welcome to Logirad 👋\nTo get freight quotes, describe your shipment (origin, destination, commodity, weight, ready date) or answer the questions.",
    },
    "origin_country": {"fa": "بار از کدام کشور یا شهر/بندر ارسال می‌شود؟", "en": "Where is the cargo shipped from (country or city/port)?"},
    "destination_country": {"fa": "مقصد بار کجاست؟ (کشور یا شهر/بندر)", "en": "Where is it going (country or city/port)?"},
    "mode": {"fa": "نوع حمل؟\n1️⃣ دریایی کانتینر کامل (FCL)\n2️⃣ دریایی خرده‌بار (LCL)\n3️⃣ هوایی\n4️⃣ زمینی",
             "en": "Shipping mode?\n1️⃣ Ocean full container (FCL)\n2️⃣ Ocean LCL\n3️⃣ Air\n4️⃣ Road"},
    "commodity": {"fa": "نوع کالا چیست؟", "en": "What is the commodity?"},
    "weight_kg": {"fa": "وزن کل بار؟ (مثلاً ۱۸۰۰۰ کیلو یا ۱۸ تن)", "en": "Total weight? (e.g. 18000 kg or 18 tons)"},
    "containers": {"fa": "تعداد و نوع کانتینر؟ (مثلاً 2x40HC یا ۱ تا ۲۰ فوت)", "en": "How many containers and what type? (e.g. 2x40HC)"},
    "volume_cbm": {"fa": "حجم بار چند متر مکعب (CBM) است؟", "en": "Volume in cubic meters (CBM)?"},
    "ready_date": {"fa": "بار چه تاریخی آماده حمل است؟ (مثلاً ۱۴۰۵/۰۹/۰۱ یا 2026-11-22)", "en": "When is the cargo ready? (e.g. 2026-11-22)"},
    "retry": {"fa": "متوجه نشدم 🙏 ", "en": "Sorry, I didn't get that 🙏 "},
    "confirm": {"fa": "خلاصه درخواست شما:\n{summary}\n\nتأیید می‌کنید؟ (بله / خیر)", "en": "Your request:\n{summary}\n\nConfirm? (yes / no)"},
    "created": {"fa": "✅ درخواست شما با کد {ref} ثبت شد.\nپیشنهادهای شرکت‌های حمل را بررسی و برایتان ارسال می‌کنیم.\nپیگیری: {url}/#track",
                "en": "✅ Your request {ref} has been registered.\nWe will collect and send you quotes from vetted forwarders.\nTrack: {url}/#track"},
    "hold": {"fa": "درخواست شما ثبت شد (کد {ref}) و پیش از ارسال به شرکت‌های حمل توسط کارشناس انطباق بررسی می‌شود.",
             "en": "Your request {ref} was registered and will be reviewed by our compliance team before it is sent to forwarders."},
    "restart": {"fa": "باشه، از اول شروع کنیم. ", "en": "OK, let's start over. "},
    "handoff": {"fa": "یکی از همکاران ما به‌زودی در همین گفتگو پاسخ می‌دهد.", "en": "A colleague will reply here shortly."},
    "status": {"fa": "وضعیت درخواست {ref}: {status}", "en": "Status of {ref}: {status}"},
    "quotes_ready": {"fa": "📦 برای درخواست {ref} پیشنهاد قیمت دریافت شد. کارشناس ما گزینه‌ها را برایتان ارسال می‌کند.",
                     "en": "📦 Quotes have arrived for {ref}. Our team will share the options with you shortly."},
}
STATUS_TEXT = {
    "fa": {"started": "ناقص", "qualified": "در حال انتخاب شرکت‌ها", "compliance_hold": "در حال بررسی", "dispatched": "ارسال‌شده به شرکت‌های حمل",
           "quoted": "پیشنهاد قیمت دریافت شده", "booked": "رزرو شده", "closed": "تحویل شده", "rejected": "رد شده"},
    "en": {"started": "incomplete", "qualified": "matching forwarders", "compliance_hold": "under review", "dispatched": "sent to forwarders",
           "quoted": "quotes received", "booked": "booked", "closed": "delivered", "rejected": "rejected"},
}
MODE_TEXT = {"fa": {"ocean_fcl": "دریایی FCL", "ocean_lcl": "دریایی LCL", "air": "هوایی", "road": "زمینی"},
             "en": {"ocean_fcl": "Ocean FCL", "ocean_lcl": "Ocean LCL", "air": "Air", "road": "Road"}}

YES = {"بله", "آره", "اره", "بلی", "تایید", "تأیید", "yes", "y", "ok", "confirm", "✅", "👍"}
NO = {"خیر", "نه", "no", "n", "لغو", "cancel"}
RESET = {"جدید", "شروع", "new", "start", "restart", "menu", "منو"}
HUMAN = {"کارشناس", "اپراتور", "پشتیبانی", "agent", "human", "operator", "support"}
STATUS_WORDS = {"وضعیت", "پیگیری", "status", "track"}


def t(key: str, lang: str, **kw) -> str:
    return T[key][lang].format(**kw)


def verify_signature(body: bytes, header: str | None) -> bool:
    secret = get_settings().whatsapp_app_secret
    if not secret:
        return True  # signature check disabled until the app secret is configured
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def send_text(to: str, body: str) -> str:
    """Send a WhatsApp text. Returns 'ok', 'logged' (not configured) or 'failed'."""
    s = get_settings()
    if not (s.whatsapp_token and s.whatsapp_phone_number_id):
        log.info("whatsapp (not sent, not configured) to=%s: %s", to, body[:80])
        return "logged"
    try:
        r = httpx.post(
            f"https://graph.facebook.com/{s.whatsapp_graph_version}/{s.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body[:4096]}},
            timeout=15,
        )
        r.raise_for_status()
        return "ok"
    except httpx.HTTPError:
        log.exception("whatsapp delivery failed to=%s", to)
        return "failed"


# ---------- conversation engine ----------

def _next_field(draft: dict) -> str | None:
    order = ["origin_country", "destination_country", "mode", "commodity", "weight_kg"]
    mode = draft.get("mode")
    if mode == "ocean_fcl":
        order.append("containers")
    elif mode in ("ocean_lcl", "air"):
        order.append("volume_cbm")
    order.append("ready_date")
    return next((f for f in order if not draft.get(f)), None)


def _parse_field(field: str, text: str) -> dict:
    if field in ("origin_country", "destination_country"):
        hit = find_country(text)
        if not hit:
            return {}
        city_key = "origin_city" if field == "origin_country" else "destination_city"
        return {field: hit[0], **({city_key: hit[1]} if hit[1] else {})}
    if field == "mode":
        m = find_mode(text)
        return {"mode": m} if m else {}
    if field == "commodity":
        return {"commodity": text.strip()[:255]} if len(text.strip()) >= 2 else {}
    if field == "weight_kg":
        w = find_weight_kg(text)
        return {"weight_kg": w} if w else {}
    if field == "containers":
        c = find_containers(text)
        return {"containers": c} if c else {}
    if field == "volume_cbm":
        v = find_volume_cbm(text)
        return {"volume_cbm": v} if v else {}
    if field == "ready_date":
        d = find_date(text)
        return {"ready_date": d} if d else {}
    return {}


def _rule_fill(text: str) -> dict:
    """Best-effort multi-field extraction from one free-text message without AI."""
    out: dict = {}
    countries = find_countries(text)
    if countries:
        out["origin_country"] = countries[0][0]
        if countries[0][1]:
            out["origin_city"] = countries[0][1]
    if len(countries) > 1:
        out["destination_country"] = countries[1][0]
        if countries[1][1]:
            out["destination_city"] = countries[1][1]
    containers = find_containers(text)
    mode = find_mode(text) or ("ocean_fcl" if containers else None)
    if mode:
        out["mode"] = mode
    if containers and mode == "ocean_fcl":
        out["containers"] = containers
    t = normalize(text).lower()
    if re.search(r"\d\s*(tons?|tonnes?|تن|kg|kgs|کیلو)", t):
        out["weight_kg"] = find_weight_kg(text)
    if date := find_date(text):
        out["ready_date"] = date
    return out


def _ai_fill(text: str) -> dict:
    try:
        draft, _ = intake.extract(text)
    except intake.IntakeUnavailable:
        return {}
    data = draft.model_dump(exclude={"questions"}, exclude_none=True)
    # The phone number is the WhatsApp sender; never trust a number typed into the message.
    data.pop("contact_phone", None)
    return data


def _summary(draft: dict, lang: str) -> str:
    rows = [
        ("مسیر" if lang == "fa" else "Route",
         f"{draft.get('origin_city') or draft.get('origin_country')} → {draft.get('destination_city') or draft.get('destination_country')}"),
        ("حمل" if lang == "fa" else "Mode", MODE_TEXT[lang].get(draft.get("mode", ""), "-")),
        ("کالا" if lang == "fa" else "Commodity", draft.get("commodity", "-")),
        ("وزن" if lang == "fa" else "Weight", f"{draft.get('weight_kg', 0):,.0f} kg"),
    ]
    if draft.get("containers"):
        rows.append(("کانتینر" if lang == "fa" else "Containers", draft["containers"]))
    if draft.get("volume_cbm"):
        rows.append(("حجم" if lang == "fa" else "Volume", f"{draft['volume_cbm']} CBM"))
    rows.append(("آمادگی" if lang == "fa" else "Ready", draft.get("ready_date", "-")))
    return "\n".join(f"• {k}: {v}" for k, v in rows)


def _create_rfq(db: Session, conv: WAConversation) -> RFQ:
    from ..api.rfqs import new_reference  # local import avoids a cycle

    fields = {k: v for k, v in conv.draft.items() if k in RFQ.__table__.columns.keys()}
    rfq = RFQ(reference=new_reference(), source="whatsapp", contact_phone="+" + conv.wa_id,
              contact_name=conv.name, **fields)
    qualification.apply(rfq)
    db.add(rfq)
    db.flush()
    audit.log(db, f"whatsapp:{conv.wa_id}", "rfq.create", "rfq", rfq.id, {"status": rfq.status, "flags": rfq.flags},
              source="whatsapp")
    return rfq


def handle_text(db: Session, conv: WAConversation, text: str) -> list[str]:
    """Advance the conversation with one inbound message; return the replies to send."""
    s = get_settings()
    raw = normalize(text)
    word = raw.lower().strip(" .!؟?")
    lang = conv.lang
    replies: list[str] = []

    if word in HUMAN:
        conv.needs_human = True
        return [t("handoff", lang)]
    if word in STATUS_WORDS:
        rfq = db.get(RFQ, conv.rfq_id) if conv.rfq_id else None
        if rfq:
            return [t("status", lang, ref=rfq.reference, status=STATUS_TEXT[lang].get(rfq.status, rfq.status))]
    if word in RESET:
        conv.state, conv.draft = "collecting", {}
        return [t("restart", lang) + t("origin_country", lang)]

    if conv.state == "handoff":
        conv.needs_human = True
        return []

    if conv.state == "confirming":
        if word in YES:
            rfq = _create_rfq(db, conv)
            conv.rfq_id, conv.state, conv.draft = rfq.id, "idle", {}
            key = "hold" if rfq.status == RFQStatus.compliance_hold else "created"
            return [t(key, lang, ref=rfq.reference, url=s.public_url.rstrip("/"))]
        if word in NO:
            conv.state, conv.draft = "collecting", {}
            return [t("restart", lang) + t("origin_country", lang)]
        # Treat anything else as a correction to the draft.
        conv.state = "collecting"

    draft = dict(conv.draft or {})
    if conv.state == "idle":
        conv.state = "collecting"
        draft = {}
        if len(raw) < 12:  # greeting only
            conv.draft = draft
            return [t("welcome", lang), t("origin_country", lang)]
        draft.update(_ai_fill(raw) if s.ai_enabled else {})
        draft.update({k: v for k, v in _rule_fill(raw).items() if not draft.get(k)})
        filled_now = True
    else:
        filled_now = False

    field = _next_field(draft)
    if field and not filled_now:
        parsed = _parse_field(field, raw)
        if not parsed and s.ai_enabled and len(raw) >= 12:
            parsed = {k: v for k, v in _ai_fill(raw).items() if not draft.get(k)}
        if parsed:
            draft.update(parsed)
        elif conv.draft:  # only complain when we actually asked a question
            replies.append(t("retry", lang))
    if not draft.get("contact_email") and (email := find_email(raw)):
        draft["contact_email"] = email

    conv.draft = draft
    field = _next_field(draft)
    if field:
        replies.append((replies.pop() if replies else "") + t(field, lang))
        return replies
    conv.state = "confirming"
    return [t("confirm", lang, summary=_summary(draft, lang))]


def get_conversation(db: Session, wa_id: str, name: str | None, first_text: str) -> WAConversation:
    conv = db.scalar(select(WAConversation).where(WAConversation.wa_id == wa_id))
    if not conv:
        conv = WAConversation(wa_id=wa_id, name=name, lang="fa" if is_persian(first_text) or not first_text else "en",
                              draft={})
        db.add(conv)
        db.flush()
    elif name and not conv.name:
        conv.name = name
    return conv


def record(db: Session, conv: WAConversation, direction: str, body: str, *, sender: str,
           wa_message_id: str | None = None, delivery: str = "ok") -> WAMessage:
    m = WAMessage(conversation_id=conv.id, direction=direction, body=body, sender=sender,
                  wa_message_id=wa_message_id, delivery=delivery)
    db.add(m)
    conv.updated_at = datetime.now(timezone.utc)
    return m


def within_session_window(conv: WAConversation) -> bool:
    if not conv.last_inbound_at:
        return False
    last = conv.last_inbound_at if conv.last_inbound_at.tzinfo else conv.last_inbound_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() < SESSION_WINDOW_HOURS * 3600


def notify_rfq_customer(db: Session, rfq: RFQ, key: str) -> tuple[list[int], str] | None:
    """Queue a status message to a WhatsApp customer if the 24h window allows it.

    Returns (message ids, wa_id) for the caller to deliver in a background task.
    """
    if rfq.source != "whatsapp":
        return None
    conv = db.scalar(select(WAConversation).where(WAConversation.rfq_id == rfq.id))
    if not conv or not within_session_window(conv):
        return None
    m = record(db, conv, "out", t(key, conv.lang, ref=rfq.reference), sender="bot", delivery="queued")
    db.flush()
    return [m.id], conv.wa_id
