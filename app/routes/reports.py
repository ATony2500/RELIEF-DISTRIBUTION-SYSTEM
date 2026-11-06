"""
Reports routes — summary statistics and export-ready views.
"""

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models.beneficiary import Beneficiary
from app.models.inventory import InventoryItem, StockMovement, Warehouse
from app.models.distribution import DistributionBatch, DistributionRecord
from app.models.zone import State
from app.utils.decorators import roles_required

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/")
@login_required
@roles_required("admin", "programme_coord", "partner")
def index():
    return render_template("reports/index.html")


@reports_bp.route("/beneficiary-summary")
@login_required
@roles_required("admin", "programme_coord", "partner")
def beneficiary_summary():
    # Beneficiaries by state
    by_state = (
        db.session.query(State.name, func.count(Beneficiary.id).label("count"))
        .join(Beneficiary.lga)
        .join(State, State.id == db.text("lgas.state_id"))
        .filter(Beneficiary.status == "active")
        .group_by(State.name)
        .order_by(func.count(Beneficiary.id).desc())
        .all()
    )

    total = Beneficiary.query.filter_by(status="active").count()
    verified = Beneficiary.query.filter_by(status="active", nin_verified=True).count()
    unverified = total - verified

    gender_counts = (
        db.session.query(Beneficiary.gender, func.count(Beneficiary.id))
        .filter_by(status="active")
        .group_by(Beneficiary.gender)
        .all()
    )

    vulnerability = {
        "disabled": Beneficiary.query.filter_by(status="active", is_disabled=True).count(),
        "pregnant": Beneficiary.query.filter_by(status="active", is_pregnant=True).count(),
        "elderly": Beneficiary.query.filter_by(status="active", is_elderly=True).count(),
        "unaccompanied": Beneficiary.query.filter_by(
            status="active", is_unaccompanied_minor=True
        ).count(),
    }

    return render_template(
        "reports/beneficiary_summary.html",
        by_state=by_state,
        total=total,
        verified=verified,
        unverified=unverified,
        gender_counts=gender_counts,
        vulnerability=vulnerability,
    )


@reports_bp.route("/inventory-report")
@login_required
@roles_required("admin", "programme_coord", "warehouse", "partner")
def inventory_report():
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()

    wh_id = request.args.get("warehouse_id", type=int)
    items_query = InventoryItem.query
    if wh_id:
        items_query = items_query.filter_by(warehouse_id=wh_id)

    items = items_query.order_by(InventoryItem.category, InventoryItem.item_name).all()
    low_stock = [i for i in items if i.is_low_stock]

    by_category = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)

    return render_template(
        "reports/inventory_report.html",
        warehouses=warehouses,
        items=items,
        low_stock=low_stock,
        by_category=by_category,
        selected_wh_id=wh_id,
    )


@reports_bp.route("/distribution-report")
@login_required
@roles_required("admin", "programme_coord", "partner")
def distribution_report():
    batches = (
        DistributionBatch.query
        .order_by(DistributionBatch.planned_date.desc())
        .all()
    )

    batch_stats = []
    for b in batches:
        total = b.records.count()
        completed = b.records.filter_by(status="completed").count()
        batch_stats.append({
            "batch": b,
            "total": total,
            "completed": completed,
            "rate": round((completed / total * 100) if total else 0, 1),
        })

    overall_completed = DistributionRecord.query.filter_by(status="completed").count()
    overall_total = DistributionRecord.query.count()

    return render_template(
        "reports/distribution_report.html",
        batch_stats=batch_stats,
        overall_completed=overall_completed,
        overall_total=overall_total,
    )


@reports_bp.route("/audit-summary")
@login_required
@roles_required("admin")
def audit_summary():
    from app.models.audit import AuditLog
    from app.models.user import User
    page = request.args.get("page", 1, type=int)
    logs = (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .paginate(page=page, per_page=30, error_out=False)
    )
    return render_template("reports/audit_summary.html", logs=logs)
