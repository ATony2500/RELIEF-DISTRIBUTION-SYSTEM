"""
Beneficiary models — individuals and household units eligible for relief.
NIN (11-digit) is used as the primary verification identifier per NIMC.
"""

from datetime import datetime
from app import db


class BeneficiaryHousehold(db.Model):
    """
    A household unit. Multiple beneficiaries may belong to one household,
    but only the head of household receives distribution on behalf of all.
    """

    __tablename__ = "beneficiary_households"

    id = db.Column(db.Integer, primary_key=True)
    household_code = db.Column(db.String(20), unique=True, nullable=False)
    head_of_household_nin = db.Column(db.String(11), unique=True, nullable=False)
    address = db.Column(db.String(255))
    lga_id = db.Column(db.Integer, db.ForeignKey("lgas.id"), nullable=False)
    household_size = db.Column(db.Integer, default=1)
    vulnerability_score = db.Column(
        db.Integer,
        default=0,
        comment="0-100 composite vulnerability score",
    )
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    NIN is verified against the NIMC database (simulated in development).
    """

    __tablename__ = "beneficiaries"

    id = db.Column(db.Integer, primary_key=True)
    nin = db.Column(db.String(11), unique=True, nullable=False, index=True)
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
    lga_id = db.Column(db.Integer, db.ForeignKey("lgas.id"), nullable=False)
    address = db.Column(db.String(255))

    # Household link
    household_id = db.Column(
        db.Integer, db.ForeignKey("beneficiary_households.id"), nullable=True
    )
    is_head_of_household = db.Column(db.Boolean, default=False)

    # Vulnerability flags
    is_disabled = db.Column(db.Boolean, default=False)
    is_pregnant = db.Column(db.Boolean, default=False)
    is_elderly = db.Column(db.Boolean, default=False)
    is_unaccompanied_minor = db.Column(db.Boolean, default=False)

    # Verification
    nin_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_date = db.Column(db.DateTime)
    verification_notes = db.Column(db.Text)

    # Status
    status = db.Column(
        db.Enum("active", "inactive", "duplicate", "flagged", name="beneficiary_status_enum"),
        default="active",
        nullable=False,
    )

    # Audit
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    registered_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    lga = db.relationship("LocalGovernmentArea", back_populates="beneficiaries")
    household = db.relationship("BeneficiaryHousehold", back_populates="members")
    distribution_records = db.relationship(
        "DistributionRecord", back_populates="beneficiary", lazy="dynamic"
    )

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def masked_nin(self) -> str:
        """Return NIN with middle digits masked for display."""
        if len(self.nin) == 11:
            return self.nin[:3] + "****" + self.nin[-4:]
        return self.nin

    def __repr__(self) -> str:
        return f"<Beneficiary {self.full_name} NIN:{self.masked_nin}>"
