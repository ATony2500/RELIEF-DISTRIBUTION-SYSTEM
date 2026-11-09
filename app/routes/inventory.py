"""
Inventory management routes — warehouses, items, stock movements.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request,
)
from flask_login import login_required, current_user
from app import db
from app.models.inventory import InventoryItem, Warehouse, StockMovement
from app.utils.helpers import (
    paginate_query, get_or_404, parse_date, form_str,
    get_all_states, get_active_warehouses, commit_with_audit,
)
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
    states = get_all_states()
    error = None

    if request.method == "POST":
        name = form_str("name")
        code = form_str("code").upper()
        address = form_str("address")
        state_id = request.form.get("state_id", type=int)
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        capacity = request.form.get("capacity_tonnes", type=float)
        manager_name = form_str("manager_name")
        manager_phone = form_str("manager_phone")

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
            commit_with_audit(
                "CREATE_WAREHOUSE", "Warehouse", wh.id,
                f"Created warehouse '{name}' ({code}).",
            )
            flash(f"Warehouse '{name}' created.", "success")
            return redirect(url_for("inventory.warehouses"))

    return render_template("inventory/create_warehouse.html", states=states, error=error)


@inventory_bp.route("/warehouses/<int:wh_id>")
@login_required
def warehouse_detail(wh_id):
    wh = get_or_404(Warehouse, wh_id)
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()[:100]

    q = InventoryItem.query.filter_by(warehouse_id=wh_id)
    if category:
        q = q.filter_by(category=category)
    if search:
        q = q.filter(InventoryItem.item_name.ilike(f"%{search}%"))

    # Paginated list
    items_page = paginate_query(q.order_by(InventoryItem.item_name), page)

    # Low-stock items — DB-level filter (no full table load)
    low_stock = (
        q.filter(
            db.or_(
                InventoryItem.quantity_available <= 0,
                db.and_(
                    InventoryItem.minimum_threshold > 0,
                    InventoryItem.quantity_available <= InventoryItem.minimum_threshold,
                ),
            )
        ).all()
    )

    return render_template(
        "inventory/warehouse_detail.html",
        warehouse=wh,
        items=items_page,
        low_stock=low_stock,
        category=category,
        search=search,
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
    if low_only:
        query = query.filter(
            db.or_(
                InventoryItem.quantity_available <= 0,
                db.and_(
                    InventoryItem.minimum_threshold > 0,
                    InventoryItem.quantity_available <= InventoryItem.minimum_threshold,
                ),
            )
        )

    all_items = query.order_by(InventoryItem.item_name).all()

    warehouses = get_active_warehouses()

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
    warehouses = get_active_warehouses()
    error = None

    if request.method == "POST":
        warehouse_id = request.form.get("warehouse_id", type=int)
        item_name = form_str("item_name")
        category = request.form.get("category", "")
        unit = form_str("unit", default="units")
        quantity = request.form.get("quantity_available", 0.0, type=float)
        threshold = request.form.get("minimum_threshold", 0.0, type=float)
        donor = form_str("donor") or None
        batch_number = form_str("batch_number") or None
        expiry_str = request.form.get("expiry_date", "").strip()
        notes = form_str("notes") or None
        expiry = parse_date(expiry_str)

        if not warehouse_id or not item_name or not category:
            error = "Warehouse, item name, and category are required."
        else:
            item = InventoryItem(
                warehouse_id=warehouse_id,
                item_name=item_name,
                category=category,
                unit=unit,
                quantity_available=quantity,
                minimum_threshold=threshold,
                donor=donor,
                batch_number=batch_number,
                expiry_date=expiry,
                notes=notes,
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

            commit_with_audit(
                "ADD_INVENTORY_ITEM", "InventoryItem", item.id,
                f"Added item '{item_name}' ({quantity} {unit}) to warehouse ID {warehouse_id}.",
            )
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
    item = get_or_404(InventoryItem, item_id)
    error = None

    if request.method == "POST":
        movement_type = request.form.get("movement_type", "")
        quantity = request.form.get("quantity", 0.0, type=float)
        reference = form_str("reference_number") or None
        notes = form_str("notes") or None

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
                    reference_number=reference,
                    notes=notes,
                    performed_by=current_user.id,
                )
                db.session.add(mv)
                commit_with_audit(
                    action="STOCK_MOVEMENT",
                    entity_type="InventoryItem",
                    entity_id=item.id,
                    description=f"{movement_type.upper()} {quantity} {item.unit} of '{item.item_name}'.",
                )
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
