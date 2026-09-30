"""WhatsApp Cloud API webhook + Ops desk inbox."""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from ..db import get_db
from ..models import RFQ, User, WAConversation, WAMessage
from ..security import staff
from ..services import audit
from ..services import whatsapp as wa

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
def verify(mode: str = Query(alias="hub.mode", default=""), token: str = Query(alias="hub.verify_token", default=""),
           challenge: str = Query(alias="hub.challenge", default="")):
    """Meta calls this once when the webhook URL is registered."""
    expected = get_settings().whatsapp_verify_token
    if mode == "subscribe" and expected and token == expected:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(403, "Verification failed")


def _deliver(bind, message_ids: list[int], to: str) -> None:
    """Send queued outbound messages and store the delivery result."""
    with sessionmaker(bind=bind)() as db:
        for mid in message_ids:
            m = db.get(WAMessage, mid)
            m.delivery = wa.send_text(to, m.body)
        db.commit()


@router.post("/webhook")
async def receive(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.body()
    if not wa.verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "Invalid signature")
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                _handle_message(db, background, msg, names)
    return {"ok": True}


def _handle_message(db: Session, background: BackgroundTasks, msg: dict, names: dict) -> None:
    wa_id, msg_id = msg.get("from"), msg.get("id")
    if not wa_id or (msg_id and db.scalar(select(WAMessage.id).where(WAMessage.wa_message_id == msg_id))):
        return  # Meta retries deliveries; ignore duplicates
    if msg.get("type") == "text":
        text = msg.get("text", {}).get("body", "")
    elif msg.get("type") == "interactive":
        reply = msg.get("interactive", {})
        text = (reply.get("button_reply") or reply.get("list_reply") or {}).get("title", "")
    else:
        text = f"[{msg.get('type', 'unknown')} message]"
    conv = wa.get_conversation(db, wa_id, names.get(wa_id), text)
    conv.last_inbound_at = datetime.now(timezone.utc)
    wa.record(db, conv, "in", text, sender="customer", wa_message_id=msg_id)
    if msg.get("type") in ("text", "interactive"):
        replies = wa.handle_text(db, conv, text)
    else:  # media, location, etc. → a human looks at it
        conv.needs_human = True
        replies = [wa.t("handoff", conv.lang)]
    out = [wa.record(db, conv, "out", r, sender="bot", delivery="queued") for r in replies]
    db.commit()
    if out:
        background.add_task(_deliver, db.get_bind(), [m.id for m in out], wa_id)


# ---------- Ops inbox ----------

class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class ConversationPatch(BaseModel):
    needs_human: bool | None = None
    bot_paused: bool | None = None


def _conv_out(c: WAConversation, with_messages: bool = False) -> dict:
    last = c.messages[-1] if c.messages else None
    out = {"id": c.id, "wa_id": c.wa_id, "name": c.name, "lang": c.lang, "state": c.state, "draft": c.draft,
           "rfq_id": c.rfq_id, "needs_human": c.needs_human, "updated_at": c.updated_at,
           "window_open": wa.within_session_window(c),
           "last_message": {"direction": last.direction, "body": last.body[:140]} if last else None}
    if with_messages:
        out["messages"] = [{"id": m.id, "direction": m.direction, "body": m.body, "sender": m.sender,
                            "delivery": m.delivery, "at": m.created_at} for m in c.messages]
    return out


@router.get("/conversations")
def conversations(needs_human: bool | None = None, db: Session = Depends(get_db), _: User = Depends(staff)):
    q = select(WAConversation).order_by(WAConversation.updated_at.desc()).limit(200)
    if needs_human is not None:
        q = q.where(WAConversation.needs_human == needs_human)
    return [_conv_out(c) for c in db.scalars(q)]


@router.get("/conversations/{conv_id}")
def conversation(conv_id: int, db: Session = Depends(get_db), _: User = Depends(staff)):
    c = db.get(WAConversation, conv_id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    out = _conv_out(c, with_messages=True)
    if c.rfq_id:
        rfq = db.get(RFQ, c.rfq_id)
        out["rfq"] = {"id": rfq.id, "reference": rfq.reference, "status": rfq.status}
    return out


@router.post("/conversations/{conv_id}/reply")
def reply(conv_id: int, body: ReplyIn, background: BackgroundTasks, db: Session = Depends(get_db),
          user: User = Depends(staff)):
    c = db.get(WAConversation, conv_id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    if not wa.within_session_window(c):
        raise HTTPException(409, "The 24-hour WhatsApp window is closed; the customer must message first "
                                 "(or use an approved template).")
    m = wa.record(db, c, "out", body.text, sender=user.email, delivery="queued")
    c.needs_human = False
    audit.log(db, user.email, "whatsapp.reply", "wa_conversation", c.id, {"chars": len(body.text)})
    db.commit()
    background.add_task(_deliver, db.get_bind(), [m.id], c.wa_id)
    return {"id": m.id}


@router.patch("/conversations/{conv_id}")
def update_conversation(conv_id: int, body: ConversationPatch, db: Session = Depends(get_db),
                        user: User = Depends(staff)):
    """Take over a chat (pause the bot) or give it back."""
    c = db.get(WAConversation, conv_id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    if body.needs_human is not None:
        c.needs_human = body.needs_human
    if body.bot_paused is not None:
        c.state = "handoff" if body.bot_paused else "idle"
    audit.log(db, user.email, "whatsapp.update", "wa_conversation", c.id, body.model_dump(exclude_none=True))
    db.commit()
    return _conv_out(c)
