import uuid
from sqlalchemy.orm import Session
from app.models.identity import AuditLog
from app.clock import get_now


def log_audit(db: Session, user_id: str, action: str, entity_type: str, entity_id: str, details: dict, role: str | None = None):
    audit = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ts=get_now()
    )
    db.add(audit)
