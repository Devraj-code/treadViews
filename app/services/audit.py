"""Audit logging helper."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    user_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    log = AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip_address)
    db.add(log)
    db.commit()
