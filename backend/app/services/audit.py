"""Audit log helper. Only server code writes audit records."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..core.enums import AuditAction
from ..db.models import AuditLog


def audit(
    session: Session,
    action: AuditAction | str,
    *,
    user_id: int | None = None,
    target_type: str = "",
    target_id: str = "",
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        action=action.value if isinstance(action, AuditAction) else str(action),
        target_type=target_type,
        target_id=str(target_id),
        detail=detail,
    )
    session.add(row)
    if commit:
        session.commit()
    return row
