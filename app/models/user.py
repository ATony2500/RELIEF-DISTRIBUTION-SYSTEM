"""
User model — accounts, roles, and authentication.

Roles (RBAC):
  admin           – full system access
  programme_coord – manages distributions and beneficiaries
  warehouse       – manages inventory and stock movements
  field_officer   – registers beneficiaries, records distributions
  logistics       – manages routes and deliveries
  partner         – read-only partner organisation access
"""

from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager, bcrypt


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(
        db.Enum(
            "admin",
            "programme_coord",
            "warehouse",
            "field_officer",
            "logistics",
            "partner",
            name="user_role_enum",
        ),
        nullable=False,
        default="field_officer",
    )
    phone = db.Column(db.String(20))
    organisation = db.Column(db.String(120))
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)

    # Relationships
    state = db.relationship("State", back_populates="users")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")
    distributions = db.relationship(
        "DistributionRecord",
        back_populates="recorded_by_user",
        foreign_keys="DistributionRecord.recorded_by",
        lazy="dynamic",
    )

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hash and store a plaintext password."""
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Return True if plaintext password matches stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_warehouse_staff(self) -> bool:
        return self.role in ("admin", "warehouse")

    @property
    def is_field_officer(self) -> bool:
        return self.role in ("admin", "field_officer", "programme_coord")

    @property
    def is_logistics(self) -> bool:
        return self.role in ("admin", "logistics")

    @property
    def can_view_reports(self) -> bool:
        return self.role in ("admin", "programme_coord", "partner")

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login callback to reload user from session."""
    return db.session.get(User, int(user_id))
