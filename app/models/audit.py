"""
Audit Trail model — immutable log of every significant system action.
Written by the audit_log() helper in utils/audit.py.
"""

from datetime import datetime
from app import db


class AuditLog(db.Model):
    """
    Append-only record of system events.
    Never update or delete rows from this table.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)  # e.g. "CREATE_BENEFICIARY"
    entity_type = db.Column(db.String(50))              # e.g. "Beneficiary"
    entity_id = db.Column(db.Integer)                   # PK of the affected row
    description = db.Column(db.Text)                    # Human-readable detail
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user={self.user_id} at {self.timestamp}>"
