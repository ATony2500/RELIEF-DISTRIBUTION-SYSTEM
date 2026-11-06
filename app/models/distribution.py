"""
Distribution models — batches and individual records.

A DistributionBatch groups one distribution event (e.g., "Flood Response – Kogi Oct 2026").
Each beneficiary at each point gets a DistributionRecord within that batch.
"""

from datetime import datetime
from app import db


class DistributionBatch(db.Model):
    """
    A distribution campaign or exercise.
    """

    __tablename__ = "distribution_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_code = db.Column(db.String(30), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    disaster_type = db.Column(
        db.Enum(
            "Flood",
            "Conflict",
            "Epidemic",
            "Drought",
            "Other",
            name="disaster_type_enum",
        ),
        nullable=False,
    )
    description = db.Column(db.Text)

    # Source warehouse
    source_warehouse_id = db.Column(
        db.Integer, db.ForeignKey("warehouses.id"), nullable=False
    )

    # Linked route
    route_id = db.Column(
        db.Integer, db.ForeignKey("delivery_routes.id"), nullable=True
    )

    status = db.Column(
        db.Enum(
            "planned",
            "in_progress",
            "completed",
            "cancelled",
            name="batch_status_enum",
        ),
        default="planned",
        nullable=False,
    )

    planned_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    source_warehouse = db.relationship("Warehouse", back_populates="batches")
    route = db.relationship("DeliveryRoute", back_populates="batch")
    records = db.relationship(
        "DistributionRecord", back_populates="batch", lazy="dynamic"
    )
    stock_movements = db.relationship(
        "StockMovement", back_populates="batch", lazy="dynamic"
    )

    @property
    def total_beneficiaries(self) -> int:
        return self.records.count()

    @property
    def completed_distributions(self) -> int:
        return self.records.filter_by(status="completed").count()

    def __repr__(self) -> str:
        return f"<DistributionBatch {self.batch_code}>"


class DistributionRecord(db.Model):
    """
    A single distribution event — one beneficiary receiving items at a point.
    """

    __tablename__ = "distribution_records"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("distribution_batches.id"), nullable=False
    )
    beneficiary_id = db.Column(
        db.Integer, db.ForeignKey("beneficiaries.id"), nullable=False
    )
    household_id = db.Column(
        db.Integer, db.ForeignKey("beneficiary_households.id"), nullable=True
    )
    distribution_point_id = db.Column(
        db.Integer, db.ForeignKey("distribution_points.id"), nullable=False
    )

    # What was distributed
    item_id = db.Column(db.Integer, db.ForeignKey("inventory_items.id"), nullable=False)
    quantity_given = db.Column(db.Float, nullable=False)

    status = db.Column(
        db.Enum("pending", "completed", "missed", "rejected", name="dist_status_enum"),
        default="pending",
        nullable=False,
    )

    # Verification at distribution point
    nin_confirmed = db.Column(db.Boolean, default=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    distribution_timestamp = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    # Audit
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    batch = db.relationship("DistributionBatch", back_populates="records")
    beneficiary = db.relationship("Beneficiary", back_populates="distribution_records")
    household = db.relationship(
        "BeneficiaryHousehold", back_populates="distribution_records"
    )
    distribution_point = db.relationship(
        "DistributionPoint", back_populates="distribution_records"
    )
    item = db.relationship("InventoryItem")
    recorded_by_user = db.relationship(
        "User", foreign_keys=[recorded_by], back_populates="distributions"
    )

    def __repr__(self) -> str:
        return f"<DistributionRecord batch={self.batch_id} beneficiary={self.beneficiary_id}>"
