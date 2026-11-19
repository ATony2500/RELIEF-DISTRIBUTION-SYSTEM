"""
Local NIN Registry — NinRecord model.

Stores a hashed NIN alongside demographic data for local verification.
Acts as a local stand-in for the NIMC database.

The raw NIN is never stored — only its SHA-256 hash (same scheme as
the Beneficiary model).  Admins can add, edit, and delete records.
CSV bulk import is also supported.
"""

import hashlib
from app import db
from app.utils.helpers import utc_now


def _hash_nin(nin: str) -> str:
    return hashlib.sha256(nin.strip().encode()).hexdigest()


class NinRecord(db.Model):
    """One entry in the local NIN registry."""

    __tablename__ = "nin_records"

    id = db.Column(db.Integer, primary_key=True)

    # NIN stored as hash only
    nin_hash   = db.Column(db.String(64), unique=True, nullable=False, index=True)
    nin_masked = db.Column(db.String(15), nullable=False)   # for display, e.g. 123****7890

    # Demographics — used for field-matching
    firstname  = db.Column(db.String(80),  nullable=False)
    lastname   = db.Column(db.String(80),  nullable=False)
    middlename = db.Column(db.String(80))
    gender     = db.Column(db.Enum("Male", "Female", "Other", name="nin_gender_enum"), nullable=False)
    birthdate  = db.Column(db.String(20))   # stored as "DD-MM-YYYY" (matches VerifyMe format)
    phone      = db.Column(db.String(20))
    state_of_origin = db.Column(db.String(80))
    lga_of_origin   = db.Column(db.String(80))

    # Admin metadata
    is_active  = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=utc_now)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def set_nin(cls, instance, nin: str) -> None:
        """Hash and mask the NIN on an instance."""
        nin = nin.strip()
        instance.nin_hash   = _hash_nin(nin)
        instance.nin_masked = nin[:3] + "****" + nin[-4:] if len(nin) == 11 else nin[:2] + "***"

    @classmethod
    def find_by_nin(cls, nin: str):
        """Look up an active record by plaintext NIN."""
        return cls.query.filter_by(nin_hash=_hash_nin(nin), is_active=True).first()

    @classmethod
    def nin_exists(cls, nin: str) -> bool:
        return cls.query.filter_by(nin_hash=_hash_nin(nin)).count() > 0

    @property
    def full_name(self) -> str:
        parts = [self.firstname, self.middlename, self.lastname]
        return " ".join(p for p in parts if p)

    def to_verification_dict(self) -> dict:
        """Return a VerifyMe-compatible data dict."""
        return {
            "nin":        self.nin_masked,
            "firstname":  self.firstname,
            "lastname":   self.lastname,
            "middlename": self.middlename or "",
            "gender":     self.gender,
            "birthdate":  self.birthdate or "",
            "phone":      self.phone or "",
        }

    def __repr__(self) -> str:
        return f"<NinRecord {self.full_name} NIN:{self.nin_masked}>"
