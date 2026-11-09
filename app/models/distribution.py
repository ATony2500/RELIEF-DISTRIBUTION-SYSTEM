"""
Distribution models — batches and individual records.

Improvement #6:  Unique constraint on (batch_id, beneficiary_id, item_id)
                 to prevent duplicate distributions.
Improvement #17: timezone-aware datetimes.
Improvement #22: Indexes on batch_id, beneficiary_id, status.
"""

from app import db
from app.utils.helpers import utc_now


class DistributionBatch(db.Model):
    __tablename__ = "distribution_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    disaster_type = db.Column(
        db.Enum(
            "Flood", "Conflict", "Epidemic", "Drought", "Other",
            name="disaster_type_enum",
        ),
        nullable=False,
    )
    description = db.Column(db.Text)

    source_warehouse_id = db.Column(
        db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True
    )
    route_id = db.Column(
        db.Integer, db.ForeignKey("delivery_routes.id"), nullable=True
    )
    status = db.Column(
        db.Enum(
            "planned", "in_progress", "completed", "cancelled",
            name="batch_status_enum",
        ),
        default="planned",
        nullable=False,
        index=True,
    )

    planned_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, onupdate=utc_now)

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
    __tablename__ = "distribution_records"

    # #6: Unique constraint prevents duplicate distributions
    __table_args__ = (
        db.UniqueConstraint(
            "batch_id", "beneficiary_id", "item_id",
            name="uq_distribution_batch_beneficiary_item",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("distribution_batches.id"), nullable=False, index=True
    )
    beneficiary_id = db.Column(
        db.Integer, db.ForeignKey("beneficiaries.id"), nullable=False, index=True
    )
    household_id = db.Column(
        db.Integer, db.ForeignKey("beneficiary_households.id"), nullable=True
    )
    distribution_point_id = db.Column(
        db.Integer, db.ForeignKey("distribution_points.id"), nullable=False
    )
    item_id = db.Column(db.Integer, db.ForeignKey("inventory_items.id"), nullable=False, index=True)
    quantity_given = db.Column(db.Float, nullable=False)

    status = db.Column(
        db.Enum("pending", "completed", "missed", "rejected", name="dist_status_enum"),
        default="pending",
        nullable=False,
        index=True,
    )

    nin_confirmed = db.Column(db.Boolean, default=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    distribution_timestamp = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)
    updated_at = db.Column(db.DateTime, onupdate=utc_now)

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
