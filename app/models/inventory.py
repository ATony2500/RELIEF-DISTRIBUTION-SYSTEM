"""
Inventory models — warehouses, relief items, and stock movements.
"""

from datetime import datetime
from app import db


class Warehouse(db.Model):
    """
    A physical storage facility for relief materials.
    Each state has at least one warehouse.
    """

    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    address = db.Column(db.String(255))
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    capacity_tonnes = db.Column(db.Float, comment="Storage capacity in metric tonnes")
    manager_name = db.Column(db.String(100))
    manager_phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    """
    A type of relief item tracked within a specific warehouse.
    Quantity is updated via StockMovement transactions.
    """

    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)

    # Item details
    item_name = db.Column(db.String(120), nullable=False)
    category = db.Column(
        db.Enum(
            "Food",
            "Water",
            "Medicine",
            "Shelter",
            "Clothing",
            "Hygiene",
            "Other",
            name="item_category_enum",
        ),
        nullable=False,
    )
    unit = db.Column(db.String(30), nullable=False, default="units")  # e.g. kg, litres, units
    quantity_available = db.Column(db.Float, default=0.0, nullable=False)
    minimum_threshold = db.Column(
        db.Float,
        default=0.0,
        comment="Trigger restocking alert when stock falls below this",
    )
    unit_weight_kg = db.Column(db.Float, default=1.0)
    expiry_date = db.Column(db.Date)
    donor = db.Column(db.String(120))
    batch_number = db.Column(db.String(50))
    notes = db.Column(db.Text)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    warehouse = db.relationship("Warehouse", back_populates="inventory_items")
    movements = db.relationship(
        "StockMovement", back_populates="item", lazy="dynamic"
    )

    @property
    def is_low_stock(self) -> bool:
        if self.minimum_threshold and self.minimum_threshold > 0:
            return self.quantity_available <= self.minimum_threshold
        return False

    @property
    def stock_percentage(self) -> float:
        """Rough percentage of stock relative to threshold (>100 = healthy)."""
        if self.minimum_threshold and self.minimum_threshold > 0:
            return round((self.quantity_available / self.minimum_threshold) * 100, 1)
        return 100.0

    def __repr__(self) -> str:
        return f"<InventoryItem {self.item_name} [{self.quantity_available} {self.unit}]>"


class StockMovement(db.Model):
    """
    Records every inbound (receipt) or outbound (distribution/transfer) movement.
    Provides a complete audit trail for inventory.
    """

    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("inventory_items.id"), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)

    movement_type = db.Column(
        db.Enum(
            "receipt",
            "dispatch",
            "transfer_in",
            "transfer_out",
            "adjustment",
            "loss",
            name="movement_type_enum",
        ),
        nullable=False,
    )
    quantity = db.Column(db.Float, nullable=False)
    reference_number = db.Column(db.String(50))  # Waybill, PO, batch ref
    notes = db.Column(db.Text)

    performed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Links to distribution batch (optional)
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
