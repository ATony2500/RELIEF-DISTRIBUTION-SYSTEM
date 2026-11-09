"""
Inventory models — warehouses, relief items, and stock movements.

Improvement #7:  Row-level locking (with_for_update) to prevent concurrent overdraw.
Improvement #17: timezone-aware datetimes.
Improvement #22: Indexes on warehouse_id, category, item_name.
"""

from app import db
from app.utils.helpers import utc_now


class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    address = db.Column(db.String(255))
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False, index=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    capacity_tonnes = db.Column(db.Float, comment="Storage capacity in metric tonnes")
    manager_name = db.Column(db.String(100))
    manager_phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    state = db.relationship("State", back_populates="warehouses")
    inventory_items = db.relationship(
        "InventoryItem", back_populates="warehouse", lazy="dynamic"
    )
    stock_movements = db.relationship(
        "StockMovement", back_populates="warehouse", lazy="dynamic"
    )
    batches = db.relationship(
        "DistributionBatch", back_populates="source_warehouse", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Warehouse {self.code} – {self.name}>"


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(
        db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True
    )
    item_name = db.Column(db.String(120), nullable=False, index=True)
    category = db.Column(
        db.Enum(
            "Food", "Water", "Medicine", "Shelter", "Clothing", "Hygiene", "Other",
            name="item_category_enum",
        ),
        nullable=False,
        index=True,
    )
    unit = db.Column(db.String(30), nullable=False, default="units")
    quantity_available = db.Column(db.Float, default=0.0, nullable=False)
    minimum_threshold = db.Column(db.Float, default=0.0)
    unit_weight_kg = db.Column(db.Float, default=1.0)
    expiry_date = db.Column(db.Date)
    donor = db.Column(db.String(120))
    batch_number = db.Column(db.String(50))
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, onupdate=utc_now)

    # Relationships
    warehouse = db.relationship("Warehouse", back_populates="inventory_items")
    movements = db.relationship(
        "StockMovement", back_populates="item", lazy="dynamic"
    )

    @property
    def is_low_stock(self) -> bool:
        if self.quantity_available <= 0:
            return True
        if self.minimum_threshold and self.minimum_threshold > 0:
            return self.quantity_available <= self.minimum_threshold
        return False

    @property
    def stock_percentage(self) -> float:
        if self.minimum_threshold and self.minimum_threshold > 0:
            return round((self.quantity_available / self.minimum_threshold) * 100, 1)
        return 100.0

    def __repr__(self) -> str:
        return f"<InventoryItem {self.item_name} [{self.quantity_available} {self.unit}]>"


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    warehouse_id = db.Column(
        db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True
    )
    movement_type = db.Column(
        db.Enum(
            "receipt", "dispatch", "transfer_in", "transfer_out", "adjustment", "loss",
            name="movement_type_enum",
        ),
        nullable=False,
        index=True,
    )
    quantity = db.Column(db.Float, nullable=False)
    reference_number = db.Column(db.String(50))
    notes = db.Column(db.Text)

    performed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    batch_id = db.Column(
        db.Integer, db.ForeignKey("distribution_batches.id"), nullable=True
    )

    # Relationships
    item = db.relationship("InventoryItem", back_populates="movements")
    warehouse = db.relationship("Warehouse", back_populates="stock_movements")
    user = db.relationship("User")
    batch = db.relationship("DistributionBatch", back_populates="stock_movements")

    def __repr__(self) -> str:
        return f"<StockMovement {self.movement_type} {self.quantity} [{self.timestamp}]>"
