"""
Distribution routes — batches, route optimization, individual records.
"""

from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, jsonify,
)
from flask_login import login_required, current_user
from app import db
from app.models.distribution import DistributionBatch, DistributionRecord
from app.models.inventory import InventoryItem, Warehouse, StockMovement
from app.models.beneficiary import Beneficiary
from app.models.route import DeliveryRoute, RouteStop
from app.models.zone import DistributionPoint, State
from app.utils.audit import audit_log
from app.utils.helpers import paginate_query, generate_batch_code, generate_route_code
from app.utils.decorators import roles_required
from app.utils.route_optimizer import optimise_route_for_points

distribution_bp = Blueprint("distribution", __name__)


# ---------------------------------------------------------------------------
# Batch list
# ---------------------------------------------------------------------------

@distribution_bp.route("/")
@login_required
def batch_list():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    query = DistributionBatch.query
    if status:
        query = query.filter_by(status=status)
    batches = paginate_query(query.order_by(DistributionBatch.created_at.desc()), page)
    return render_template("distribution/batches.html", batches=batches, status=status)


# ---------------------------------------------------------------------------
# Create batch
# ---------------------------------------------------------------------------

@distribution_bp.route("/create", methods=["GET", "POST"])
@login_required
@roles_required("admin", "programme_coord")
def create_batch():
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        disaster_type = request.form.get("disaster_type", "")
        description = request.form.get("description", "").strip()
        warehouse_id = request.form.get("source_warehouse_id", type=int)
        planned_date_str = request.form.get("planned_date", "").strip()

        if not title or not disaster_type or not warehouse_id or not planned_date_str:
            error = "Title, disaster type, source warehouse, and planned date are required."
        else:
            try:
                planned_date = datetime.strptime(planned_date_str, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date format."
                planned_date = None

            if not error:
                batch = DistributionBatch(
                    batch_code=generate_batch_code(),
                    title=title,
                    disaster_type=disaster_type,
                    description=description or None,
                    source_warehouse_id=warehouse_id,
                    planned_date=planned_date,
                    created_by=current_user.id,
                )
                db.session.add(batch)
                db.session.flush()
                audit_log("CREATE_BATCH", "DistributionBatch", batch.id,
                          f"Created distribution batch '{title}' ({batch.batch_code}).")
                db.session.commit()
                flash(f"Batch '{batch.batch_code}' created.", "success")
                return redirect(url_for("distribution.batch_detail", batch_id=batch.id))

    return render_template("distribution/create_batch.html", warehouses=warehouses, error=error)


# ---------------------------------------------------------------------------
# Batch detail
# ---------------------------------------------------------------------------

@distribution_bp.route("/<int:batch_id>")
@login_required
def batch_detail(batch_id):
    batch = db.session.get(DistributionBatch, batch_id)
    if not batch:
        abort(404)
    records = batch.records.order_by(DistributionRecord.created_at.desc()).limit(50).all()
    return render_template("distribution/batch_detail.html", batch=batch, records=records)


# ---------------------------------------------------------------------------
# Update batch status
# ---------------------------------------------------------------------------

@distribution_bp.route("/<int:batch_id>/status", methods=["POST"])
@login_required
@roles_required("admin", "programme_coord")
def update_batch_status(batch_id):
    batch = db.session.get(DistributionBatch, batch_id)
    if not batch:
        abort(404)
    new_status = request.form.get("status", "")
    valid = ("planned", "in_progress", "completed", "cancelled")
    if new_status not in valid:
        flash("Invalid status.", "danger")
    else:
        old_status = batch.status
        batch.status = new_status
        if new_status == "in_progress" and not batch.start_date:
            batch.start_date = datetime.utcnow()
        if new_status == "completed" and not batch.end_date:
            batch.end_date = datetime.utcnow()
        audit_log("UPDATE_BATCH_STATUS", "DistributionBatch", batch.id,
                  f"Status changed from '{old_status}' to '{new_status}'.")
        db.session.commit()
        flash(f"Batch status updated to '{new_status}'.", "success")
    return redirect(url_for("distribution.batch_detail", batch_id=batch.id))


# ---------------------------------------------------------------------------
# Add distribution record
# ---------------------------------------------------------------------------

@distribution_bp.route("/<int:batch_id>/record", methods=["GET", "POST"])
@login_required
@roles_required("admin", "programme_coord", "field_officer")
def add_record(batch_id):
    batch = db.session.get(DistributionBatch, batch_id)
    if not batch:
        abort(404)

    wh = batch.source_warehouse
    items = wh.inventory_items.filter(InventoryItem.quantity_available > 0).all()
    states = State.query.order_by(State.name).all()
    error = None

    if request.method == "POST":
        beneficiary_id = request.form.get("beneficiary_id", type=int)
        item_id = request.form.get("item_id", type=int)
        quantity = request.form.get("quantity_given", type=float)
        dp_id = request.form.get("distribution_point_id", type=int)
        nin_confirmed = request.form.get("nin_confirmed") == "on"

        beneficiary = db.session.get(Beneficiary, beneficiary_id) if beneficiary_id else None
        item = db.session.get(InventoryItem, item_id) if item_id else None
        dp = db.session.get(DistributionPoint, dp_id) if dp_id else None

        if not beneficiary:
            error = "Please select a valid beneficiary."
        elif not item:
            error = "Please select a valid inventory item."
        elif not quantity or quantity <= 0:
            error = "Quantity must be greater than zero."
        elif item.quantity_available < quantity:
            error = f"Insufficient stock. Available: {item.quantity_available} {item.unit}."
        elif not dp:
            error = "Please select a distribution point."
        else:
            record = DistributionRecord(
                batch_id=batch.id,
                beneficiary_id=beneficiary.id,
                household_id=beneficiary.household_id,
                distribution_point_id=dp.id,
                item_id=item.id,
                quantity_given=quantity,
                nin_confirmed=nin_confirmed,
                confirmed_by=current_user.id if nin_confirmed else None,
                distribution_timestamp=datetime.utcnow(),
                status="completed",
                recorded_by=current_user.id,
            )
            db.session.add(record)

            # Deduct from inventory
            item.quantity_available -= quantity
            mv = StockMovement(
                item_id=item.id,
                warehouse_id=wh.id,
                movement_type="dispatch",
                quantity=quantity,
                reference_number=batch.batch_code,
                notes=f"Distribution batch {batch.batch_code}",
                performed_by=current_user.id,
                batch_id=batch.id,
            )
            db.session.add(mv)

            audit_log(
                action="RECORD_DISTRIBUTION",
                entity_type="DistributionRecord",
                entity_id=None,
                description=(
                    f"Distributed {quantity} {item.unit} of '{item.item_name}' "
                    f"to beneficiary '{beneficiary.full_name}' in batch {batch.batch_code}."
                ),
            )
            db.session.commit()
            flash("Distribution recorded successfully.", "success")
            return redirect(url_for("distribution.batch_detail", batch_id=batch.id))

    return render_template(
        "distribution/add_record.html",
        batch=batch,
        items=items,
        states=states,
        error=error,
    )


# ---------------------------------------------------------------------------
# Route optimization
# ---------------------------------------------------------------------------

@distribution_bp.route("/<int:batch_id>/optimise-route", methods=["GET", "POST"])
@login_required
@roles_required("admin", "logistics", "programme_coord")
def optimise_route(batch_id):
    batch = db.session.get(DistributionBatch, batch_id)
    if not batch:
        abort(404)

    wh = batch.source_warehouse
    states = State.query.order_by(State.name).all()
    optimized_result = None
    error = None

    if request.method == "POST":
        point_ids = request.form.getlist("point_ids", type=int)
        if not point_ids:
            error = "Select at least one distribution point."
        elif not wh.latitude or not wh.longitude:
            error = "Source warehouse does not have GPS coordinates set."
        else:
            points = DistributionPoint.query.filter(
                DistributionPoint.id.in_(point_ids),
                DistributionPoint.is_active == True,
            ).all()

            result = optimise_route_for_points(wh, points)
            optimized_result = result

            # Save action — create / replace route
            route_code = generate_route_code()
            route = DeliveryRoute(
                route_code=route_code,
                name=f"Route for {batch.batch_code}",
                origin_warehouse_id=wh.id,
                total_distance_km=result["total_distance_km"],
                status="draft",
                created_by=current_user.id,
            )
            db.session.add(route)
            db.session.flush()

            for idx, stop in enumerate(result["ordered_stops"], start=1):
                rs = RouteStop(
                    route_id=route.id,
                    distribution_point_id=stop["id"],
                    stop_order=idx,
                    distance_from_prev_km=stop["distance_from_prev_km"],
                )
                db.session.add(rs)

            batch.route_id = route.id
            audit_log("OPTIMISE_ROUTE", "DeliveryRoute", route.id,
                      f"Generated route {route_code} for batch {batch.batch_code}. "
                      f"Total: {result['total_distance_km']} km.")
            db.session.commit()
            flash(
                f"Route optimised: {result['total_distance_km']:.1f} km over "
                f"{len(result['ordered_stops'])} stops. Route code: {route_code}.",
                "success",
            )

    all_points = DistributionPoint.query.filter_by(is_active=True).order_by(
        DistributionPoint.name
    ).all()

    return render_template(
        "distribution/optimise_route.html",
        batch=batch,
        warehouse=wh,
        all_points=all_points,
        states=states,
        optimized_result=optimized_result,
        error=error,
    )


# ---------------------------------------------------------------------------
# Beneficiary lookup (AJAX for distribution form)
# ---------------------------------------------------------------------------

@distribution_bp.route("/lookup-beneficiary")
@login_required
def lookup_beneficiary():
    nin = request.args.get("nin", "").strip()
    if not nin:
        return jsonify({"found": False})
    b = Beneficiary.query.filter_by(nin=nin, status="active").first()
    if not b:
        return jsonify({"found": False, "message": "No active beneficiary found with that NIN."})
    return jsonify({
        "found": True,
        "id": b.id,
        "full_name": b.full_name,
        "nin_verified": b.nin_verified,
        "masked_nin": b.masked_nin,
        "lga": b.lga.name if b.lga else "",
    })
