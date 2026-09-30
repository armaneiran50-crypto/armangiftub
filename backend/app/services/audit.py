from sqlalchemy.orm import Session

from ..models import AuditEvent


def log(db: Session, actor: str, action: str, object_type: str, object_id: int | None, data: dict | None = None,
        source: str = "api") -> None:
    db.add(AuditEvent(actor=actor, action=action, object_type=object_type, object_id=object_id,
                      data=data or {}, source=source))
