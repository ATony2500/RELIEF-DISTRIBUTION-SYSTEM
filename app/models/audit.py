"""
Audit Trail model.
Improvement #17: timezone-aware datetimes.
Improvement #22: Index on timestamp and action for fast log queries.
"""

from app import db
from app.utils.helpers import utc_now


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    # Relationships
    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user={self.user_id} at {self.timestamp}>"
