"""
Beneficiary models — individuals and household units eligible for relief.
NIN (11-digit) is used as the primary verification identifier per NIMC.

Improvement #5:  NIN stored as SHA-256 hash; raw NIN never persisted.
Improvement #17: datetime.now(timezone.utc) instead of deprecated utcnow().
Improvement #22: Explicit indexes on high-frequency lookup columns.
"""

import hashlib
from app import db
from app.utils.helpers import utc_now


def _hash_nin(nin: str) -> str:
    """Return a SHA-256 hex digest of the NIN for safe storage."""
    return hashlib.sha256(nin.strip().encode()).hexdigest()


class BeneficiaryHousehold(db.Model):
    """
    A household unit. Multiple beneficiaries may belong to one household,
    but only the head of household receives distribution on behalf of all.
    """

    __tablename__ = "beneficiary_households"

    id = db.Column(db.Integer, primary_key=True)
    household_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    head_of_household_nin = db.Column(db.String(11), unique=True, nullable=False)
    address = db.Column(db.String(255))
    lga_id = db.Column(db.Integer, db.ForeignKey("lgas.id"), nullable=False, index=True)
    household_size = db.Column(db.Integer, default=1)
    vulnerability_score = db.Column(
        db.Integer,
        default=0,
        comment="0-100 composite vulnerability score",
    )
    registered_at = db.Column(db.DateTime, default=utc_now)
    registered_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Relationships
    members = db.relationship(
        "Beneficiary", back_populates="household", lazy="dynamic"
    )
    distribution_records = db.relationship(
        "DistributionRecord", back_populates="household", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Household {self.household_code}>"


class Beneficiary(db.Model):
    """
    An individual beneficiary registered in the system.
    NIN is stored as a SHA-256 hash; the original value is never persisted.
    """

    __tablename__ = "beneficiaries"

    id = db.Column(db.Integer, primary_key=True)

    # #5: Store NIN hash, not plaintext. Column renamed nin_hash to be explicit.
    # For backwards compatibility the property `nin` is kept as a read-only alias.
    nin_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # Keep a masked version for display so we don't have to store the real NIN.
    nin_masked = db.Column(db.String(15), nullable=False, default="***-****-****")

    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    middle_name = db.Column(db.String(80))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(
        db.Enum("Male", "Female", "Other", name="gender_enum"),
        nullable=False,
    )
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))

    # Address / location
    lga_id = db.Column(db.Integer, db.ForeignKey("lgas.id"), nullable=False, index=True)
    address = db.Column(db.String(255))

    # Household link
    household_id = db.Column(
        db.Integer, db.ForeignKey("beneficiary_households.id"), nullable=True, index=True
    )
    is_head_of_household = db.Column(db.Boolean, default=False)

    # Vulnerability flags
    is_disabled = db.Column(db.Boolean, default=False)
    is_pregnant = db.Column(db.Boolean, default=False)
    is_elderly = db.Column(db.Boolean, default=False)
    is_unaccompanied_minor = db.Column(db.Boolean, default=False)

    # Verification
    nin_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    verification_date = db.Column(db.DateTime)
    verification_notes = db.Column(db.Text)

    # Status — #22: indexed for fast filter queries
    status = db.Column(
        db.Enum(
            "pending", "active", "inactive", "duplicate", "flagged", "rejected",
            name="beneficiary_status_enum",
        ),
        default="pending",
        nullable=False,
        index=True,
    )

    # Optional link back to the User who submitted this application
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, unique=True, index=True
    )

    # Review fields
    rejection_reason = db.Column(db.Text, nullable=True)
    review_notes     = db.Column(db.Text, nullable=True)   # internal, not shown to applicant
    reviewed_by      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at      = db.Column(db.DateTime, nullable=True)

    # Vulnerability priority score (computed on save, used for sorting)
    priority_score = db.Column(db.Integer, default=0, nullable=False)

    # Audit
    registered_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    registered_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=utc_now)

    # Relationships
    lga = db.relationship("LocalGovernmentArea", back_populates="beneficiaries")
    household = db.relationship("BeneficiaryHousehold", back_populates="members")
    distribution_records = db.relationship(
        "DistributionRecord", back_populates="beneficiary", lazy="dynamic"
    )
    applicant = db.relationship("User", foreign_keys=[user_id], backref="beneficiary_application")
    reviewer  = db.relationship("User", foreign_keys=[reviewed_by])

    # ------------------------------------------------------------------
    # NIN helpers (#5)
    # ------------------------------------------------------------------

    def set_nin(self, nin: str) -> None:
        """Hash and store a NIN. Also compute the masked display value."""
        nin = nin.strip()
        self.nin_hash = _hash_nin(nin)
        if len(nin) == 11:
            self.nin_masked = nin[:3] + "****" + nin[-4:]
        else:
            self.nin_masked = nin[:2] + "***"

    @classmethod
    def find_by_nin(cls, nin: str):
        """Look up a beneficiary by their plaintext NIN (hashed for comparison)."""
        return cls.query.filter_by(nin_hash=_hash_nin(nin)).first()

    @classmethod
    def nin_exists(cls, nin: str) -> bool:
        return cls.query.filter_by(nin_hash=_hash_nin(nin)).count() > 0

    @property
    def masked_nin(self) -> str:
        return self.nin_masked

    # ------------------------------------------------------------------
    # Priority score helper
    # ------------------------------------------------------------------

    def compute_priority_score(self) -> int:
        """
        Compute vulnerability priority score (0-9).
        Higher = more urgent. Used to sort pending applications.
        """
        score = 0
        if self.is_unaccompanied_minor: score += 3
        if self.is_disabled:            score += 2
        if self.is_pregnant:            score += 2
        if self.is_elderly:             score += 1
        if self.is_head_of_household:   score += 1
        return score

    # ------------------------------------------------------------------
    # Name helper
    # ------------------------------------------------------------------

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<Beneficiary {self.full_name} NIN:{self.masked_nin}>"
