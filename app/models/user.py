"""
User model.
Improvement #4:  Password strength validation helper.
Improvement #17: timezone-aware datetimes.
Improvement #22: Index on username, email, role.
"""

from flask_login import UserMixin
from app import db, login_manager, bcrypt
from app.utils.helpers import utc_now


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(
        db.Enum(
            "admin", "programme_coord", "warehouse",
            "field_officer", "logistics", "partner",
            name="user_role_enum",
        ),
        nullable=False,
        default="field_officer",
        index=True,
    )
    phone = db.Column(db.String(20))
    organisation = db.Column(db.String(120))
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
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
    # Password helpers (#4 — strength validation)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_password_strength(password: str) -> str | None:
        """
        Return an error message if the password is too weak, else None.
        Rules: min 8 chars, at least one digit, at least one non-alphanumeric char.
        """
        if len(password) < 8:
            return "Password must be at least 8 characters."
        if not any(c.isdigit() for c in password):
            return "Password must contain at least one number."
        if all(c.isalnum() for c in password):
            return "Password must contain at least one special character (e.g. @, #, !)."
        return None

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))
