"""Endpoints that turn a pasted or uploaded quote into a draft (never saved automatically)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..ai import quote_parser
from ..db import get_db
from ..models import User
from ..security import staff
from ..services import audit
from .portal import my_dispatch, my_provider, provider_user, redact
from .rfqs import get_rfq

router = APIRouter(tags=["ai"])


async def _read_pdf(file: UploadFile | None) -> bytes | None:
    if file is None or not file.filename:
        return None
    data = await file.read(quote_parser.MAX_PDF_BYTES + 1)
    if len(data) > quote_parser.MAX_PDF_BYTES:
        raise HTTPException(413, "PDF is larger than 10 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Only PDF files are supported")
    return data


def _run(db: Session, rfq, text: str | None, pdf: bytes | None, actor: str, source: str) -> dict:
    if not (text and text.strip()) and not pdf:
        raise HTTPException(422, "Paste the quote text or upload a PDF")
    try:
        draft, usage = quote_parser.parse_quote(rfq, text=text, pdf=pdf)
    except quote_parser.ParserUnavailable as e:
        raise HTTPException(503, str(e))
    audit.log(db, actor, "ai.quote_parse", "rfq", rfq.id, {**usage, "pdf": bool(pdf)}, source=source)
    db.commit()
    return draft.model_dump()


@router.post("/api/rfqs/{rfq_id}/quotes/parse")
async def parse_for_ops(rfq_id: int, text: str | None = Form(None), file: UploadFile | None = File(None),
                        db: Session = Depends(get_db), user: User = Depends(staff)):
    return _run(db, get_rfq(db, rfq_id), text, await _read_pdf(file), user.email, "ops")


@router.post("/api/portal/rfqs/{rfq_id}/quote/parse")
async def parse_for_provider(rfq_id: int, text: str | None = Form(None), file: UploadFile | None = File(None),
                             db: Session = Depends(get_db), user: User = Depends(provider_user)):
    p = my_provider(user, db)
    d = my_dispatch(db, p, rfq_id)
    draft = _run(db, d.rfq, text, await _read_pdf(file), user.email, "portal")
    draft["exclusions"] = redact(draft.get("exclusions"))
    return draft
