"""
Geographical zone models — States, LGAs, and Distribution Points.
Nigeria has 36 states + FCT; each has LGAs; each LGA has distribution points.
"""

from app import db


class State(db.Model):
    __tablename__ = "states"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    code = db.Column(db.String(5), unique=True, nullable=False)  # e.g. "KN", "AB"
    geopolitical_zone = db.Column(
        db.Enum(
            "North Central",
            "North East",
            "North West",
            "South East",
            "South South",
            "South West",
            name="zone_enum",
        ),
        nullable=False,
    )
    capital = db.Column(db.String(80))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # Relationships
    lgas = db.relationship("LocalGovernmentArea", back_populates="state", lazy="dynamic")
    warehouses = db.relationship("Warehouse", back_populates="state", lazy="dynamic")
    users = db.relationship("User", back_populates="state", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<State {self.name}>"


class LocalGovernmentArea(db.Model):
    __tablename__ = "lgas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    population = db.Column(db.Integer)

    # Relationships
    state = db.relationship("State", back_populates="lgas")
    distribution_points = db.relationship(
        "DistributionPoint", back_populates="lga", lazy="dynamic"
    )
    beneficiaries = db.relationship(
        "Beneficiary", back_populates="lga", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<LGA {self.name}, {self.state.name}>"


class DistributionPoint(db.Model):
    """
    A physical location where relief materials are handed out to beneficiaries.
    One LGA may have several distribution points.
    """

    __tablename__ = "distribution_points"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255))
    lga_id = db.Column(db.Integer, db.ForeignKey("lgas.id"), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    capacity = db.Column(db.Integer, comment="Max beneficiaries per distribution day")
    contact_person = db.Column(db.String(100))
    contact_phone = db.Column(db.String(20))

    # Relationships
    lga = db.relationship("LocalGovernmentArea", back_populates="distribution_points")
    route_stops = db.relationship(
        "RouteStop", back_populates="distribution_point", lazy="dynamic"
    )
    distribution_records = db.relationship(
        "DistributionRecord", back_populates="distribution_point", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<DistributionPoint {self.name}>"
