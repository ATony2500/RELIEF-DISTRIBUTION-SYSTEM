"""
Inventory management routes — warehouses, items, stock movements.
"""

from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort,
)
from flask_login import login_required, current_user
from app import db
from app.models.inventory import InventoryItem, Warehouse, StockMovement
from app.models.zone import State
from app.utils.audit import audit_log
from app.utils.helpers import paginate_query
from app.utils.decorators import roles_required

inventory_bp = Blueprint("inventory", __name__)


# ---------------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------------

@inventory_bp.route("/warehouses")
@login_required
def warehouses():
    page = request.args.get("page", 1, type=int)
    whs = paginate_query(Warehouse.query.order_by(Warehouse.name), page)
    return render_template("inventory/warehouses.html", warehouses=whs)


@inventory_bp.route("/warehouses/create", methods=["GET", "POST"])
@login_required
@roles_required("admin", "warehouse")
def create_warehouse():
    states = State.query.order_by(State.name).all()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        address = request.form.get("address", "").strip()
        state_id = request.form.get("state_id", type=int)
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        capacity = request.form.get("capacity_tonnes", type=float)
        manager_name = request.form.get("manager_name", "").strip()
        manager_phone = request.form.get("manager_phone", "").strip()

        if not name or not code or not state_id:
            error = "Name, code, and state are required."
        elif Warehouse.query.filter_by(code=code).first():
            error = f"Warehouse code '{code}' already exists."
        else:
            wh = Warehouse(
                name=name, code=code, address=address, state_id=state_id,
                latitude=latitude, longitude=longitude,
                capacity_tonnes=capacity,
                manager_name=manager_name, manager_phone=manager_phone,
            )
            db.session.add(wh)
            db.session.flush()
            audit_log("CREATE_WAREHOUSE", "Warehouse", wh.id,
                      f"Created warehouse '{name}' ({code}).")
            db.session.commit()
            flash(f"Warehouse '{name}' created.", "success")
            return redirect(url_for("inventory.warehouses"))

    return render_template("inventory/create_warehouse.html", states=states, error=error)


@inventory_bp.route("/warehouses/<int:wh_id>")
@login_required
def warehouse_detail(wh_id):
    wh = db.session.get(Warehouse, wh_id)
    if not wh:
        abort(404)
    items = wh.inventory_items.order_by(InventoryItem.item_name).all()
    low_stock = [i for i in items if i.is_low_stock]
    return render_template(
        "inventory/warehouse_detail.html",
        warehouse=wh, items=items, low_stock=low_stock,
    )


# ---------------------------------------------------------------------------
# Inventory Items
# ---------------------------------------------------------------------------

@inventory_bp.route("/items")
@login_required
def item_list():
    page = request.args.get("page", 1, type=int)
    wh_id = request.args.get("warehouse_id", type=int)
    category = request.args.get("category", "").strip()
    low_only = request.args.get("low_stock") == "1"

    query = InventoryItem.query

    if wh_id:
        query = query.filter_by(warehouse_id=wh_id)
    if category:
        query = query.filter_by(category=category)

    all_items = query.order_by(InventoryItem.item_name).all()
    if low_only:
        all_items = [i for i in all_items if i.is_low_stock]

    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()

    return render_template(
        "inventory/items.html",
        items=all_items,
        warehouses=warehouses,
        wh_id=wh_id,
        category=category,
        low_only=low_only,
    )


@inventory_bp.route("/items/add", methods=["GET", "POST"])
@login_required
@roles_required("admin", "warehouse")
def add_item():
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    error = None

    if request.method == "POST":
        warehouse_id = request.form.get("warehouse_id", type=int)
        item_name = request.form.get("item_name", "").strip()
        category = request.form.get("category", "")
        unit = request.form.get("unit", "units").strip()
        quantity = request.form.get("quantity_available", 0.0, type=float)
        threshold = request.form.get("minimum_threshold", 0.0, type=float)
        donor = request.form.get("donor", "").strip()
        batch_number = request.form.get("batch_number", "").strip()
        expiry_str = request.form.get("expiry_date", "").strip()
        notes = request.form.get("notes", "").strip()

        if not warehouse_id or not item_name or not category:
            error = "Warehouse, item name, and category are required."
        else:
            expiry = None
            if expiry_str:
                try:
                    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            item = InventoryItem(
                warehouse_id=warehouse_id,
                item_name=item_name,
                category=category,
                unit=unit,
                quantity_available=quantity,
                minimum_threshold=threshold,
                donor=donor or None,
                batch_number=batch_number or None,
                expiry_date=expiry,
                notes=notes or None,
            )
            db.session.add(item)
            db.session.flush()

            # Record initial receipt movement
            if quantity > 0:
                mv = StockMovement(
                    item_id=item.id,
                    warehouse_id=warehouse_id,
                    movement_type="receipt",
                    quantity=quantity,
                    notes="Initial stock entry",
                    performed_by=current_user.id,
                )
                db.session.add(mv)

            audit_log("ADD_INVENTORY_ITEM", "InventoryItem", item.id,
                      f"Added item '{item_name}' ({quantity} {unit}) to warehouse ID {warehouse_id}.")
            db.session.commit()
            flash(f"Item '{item_name}' added to inventory.", "success")
            return redirect(url_for("inventory.item_list"))

    return render_template("inventory/add_item.html", warehouses=warehouses, error=error)


# ---------------------------------------------------------------------------
# Stock Movement (Receipt / Dispatch / Adjustment)
# ---------------------------------------------------------------------------

@inventory_bp.route("/items/<int:item_id>/move", methods=["GET", "POST"])
@login_required
@roles_required("admin", "warehouse")
def stock_movement(item_id):
    item = db.session.get(InventoryItem, item_id)
    if not item:
        abort(404)
    error = None

    if request.method == "POST":
        movement_type = request.form.get("movement_type", "")
        quantity = request.form.get("quantity", 0.0, type=float)
        reference = request.form.get("reference_number", "").strip()
        notes = request.form.get("notes", "").strip()

        valid_types = ("receipt", "dispatch", "transfer_in", "transfer_out", "adjustment", "loss")
        if movement_type not in valid_types:
            error = "Invalid movement type."
        elif quantity <= 0:
            error = "Quantity must be greater than zero."
        else:
            # Adjust available quantity
            if movement_type in ("receipt", "transfer_in", "adjustment"):
                item.quantity_available += quantity
            elif movement_type in ("dispatch", "transfer_out", "loss"):
                if item.quantity_available < quantity:
                    error = f"Insufficient stock. Available: {item.quantity_available} {item.unit}."
                else:
                    item.quantity_available -= quantity

            if not error:
                mv = StockMovement(
                    item_id=item.id,
                    warehouse_id=item.warehouse_id,
                    movement_type=movement_type,
                    quantity=quantity,
                    reference_number=reference or None,
                    notes=notes or None,
                    performed_by=current_user.id,
                )
                db.session.add(mv)
                audit_log(
                    action="STOCK_MOVEMENT",
                    entity_type="InventoryItem",
                    entity_id=item.id,
                    description=f"{movement_type.upper()} {quantity} {item.unit} of '{item.item_name}'.",
                )
                db.session.commit()
                flash(f"Stock movement recorded. New balance: {item.quantity_available} {item.unit}.", "success")
                return redirect(url_for("inventory.warehouse_detail", wh_id=item.warehouse_id))

    recent_movements = (
        StockMovement.query
        .filter_by(item_id=item_id)
        .order_by(StockMovement.timestamp.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "inventory/stock_movement.html",
        item=item,
        movements=recent_movements,
        error=error,
    )
