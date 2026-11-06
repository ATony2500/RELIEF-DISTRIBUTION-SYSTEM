"""
Audit Trail helper.
Call audit_log() anywhere in route handlers to record a system event.
"""

from flask import request
from flask_login import current_user
from app import db
from app.models.audit import AuditLog


def audit_log(
    action: str,
    entity_type: str = None,
    entity_id: int = None,
    description: str = None,
) -> None:
    """
    Persist an audit log entry.

    Parameters
    ----------
    action       : Short action code, e.g. 'CREATE_BENEFICIARY'.
    entity_type  : Model name, e.g. 'Beneficiary'.
    entity_id    : Primary key of the affected record.
    description  : Human-readable detail string.
    """
    user_id = current_user.id if current_user and current_user.is_authenticated else None

    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        ip_address=_get_ip(),
        user_agent=request.user_agent.string[:255] if request else None,
    )
    db.session.add(log)
    # Flush but do not commit — let the calling code commit the full transaction.
    db.session.flush()


def _get_ip() -> str:
    """Return the real client IP, accounting for reverse proxies."""
    if request:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr
    return "0.0.0.0"
