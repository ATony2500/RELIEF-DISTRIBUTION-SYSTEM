"""
Reports routes.
Improvement #13: CSV export for each report.
Improvement #16: Consistent partner role access across all report endpoints.
"""

import csv
import io
from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models.audit import AuditLog
from app.models.beneficiary import Beneficiary
from app.models.inventory import InventoryItem, StockMovement, Warehouse
from app.models.distribution import DistributionBatch, DistributionRecord
from app.models.zone import State, LocalGovernmentArea
from app.utils.decorators import roles_required
from app.utils.helpers import paginate_query, get_active_warehouses, csv_response

reports_bp = Blueprint("reports", __name__)

# Roles allowed to view/export all reports (partner included, #16)
_REPORT_ROLES = ("admin", "programme_coord", "warehouse", "partner")


@reports_bp.route("/")
@login_required
@roles_required(*_REPORT_ROLES)
def index():
    return render_template("reports/index.html")


# ---------------------------------------------------------------------------
# Beneficiary Summary
# ---------------------------------------------------------------------------

@reports_bp.route("/beneficiary-summary")
@login_required
@roles_required(*_REPORT_ROLES)
def beneficiary_summary():
    by_state = (
        db.session.query(State.name, func.count(Beneficiary.id).label("count"))
        .join(LocalGovernmentArea, LocalGovernmentArea.id == Beneficiary.lga_id)
        .join(State, State.id == LocalGovernmentArea.state_id)
        .filter(Beneficiary.status == "active")
        .group_by(State.name)
        .order_by(func.count(Beneficiary.id).desc())
        .all()
    )

    total    = Beneficiary.query.filter_by(status="active").count()
    verified = Beneficiary.query.filter_by(status="active", nin_verified=True).count()

    gender_counts = (
        db.session.query(Beneficiary.gender, func.count(Beneficiary.id))
        .filter_by(status="active")
        .group_by(Beneficiary.gender)
        .all()
    )

    vulnerability = {
        "disabled":     Beneficiary.query.filter_by(status="active", is_disabled=True).count(),
        "pregnant":     Beneficiary.query.filter_by(status="active", is_pregnant=True).count(),
        "elderly":      Beneficiary.query.filter_by(status="active", is_elderly=True).count(),
        "unaccompanied": Beneficiary.query.filter_by(
            status="active", is_unaccompanied_minor=True
        ).count(),
    }

    return render_template(
        "reports/beneficiary_summary.html",
        by_state=by_state,
        total=total,
        verified=verified,
        unverified=total - verified,
        gender_counts=gender_counts,
        vulnerability=vulnerability,
    )


@reports_bp.route("/beneficiary-summary/export")
@login_required
@roles_required(*_REPORT_ROLES)
def export_beneficiary_summary():
    rows = (
        db.session.query(State.name, func.count(Beneficiary.id).label("count"))
        .join(LocalGovernmentArea, LocalGovernmentArea.id == Beneficiary.lga_id)
        .join(State, State.id == LocalGovernmentArea.state_id)
        .filter(Beneficiary.status == "active")
        .group_by(State.name)
        .order_by(State.name)
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["State", "Active Beneficiaries"])
    for state_name, count in rows:
        w.writerow([state_name, count])
    return csv_response(buf, "beneficiary_summary")


# ---------------------------------------------------------------------------
# Inventory Report
# ---------------------------------------------------------------------------

@reports_bp.route("/inventory-report")
@login_required
@roles_required(*_REPORT_ROLES)
def inventory_report():
    warehouses = get_active_warehouses()
    wh_id      = request.args.get("warehouse_id", type=int)
    items_query = InventoryItem.query
    if wh_id:
        items_query = items_query.filter_by(warehouse_id=wh_id)

    items = items_query.order_by(InventoryItem.category, InventoryItem.item_name).all()

    low_stock = (
        items_query.filter(
            db.or_(
                InventoryItem.quantity_available <= 0,
                db.and_(
                    InventoryItem.minimum_threshold > 0,
                    InventoryItem.quantity_available <= InventoryItem.minimum_threshold,
                ),
            )
        ).all()
    )

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


@reports_bp.route("/inventory-report/export")
@login_required
@roles_required(*_REPORT_ROLES)
def export_inventory_report():
    wh_id = request.args.get("warehouse_id", type=int)
    q = InventoryItem.query
    if wh_id:
        q = q.filter_by(warehouse_id=wh_id)
    items = q.order_by(InventoryItem.category, InventoryItem.item_name).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Warehouse", "Category", "Item", "Unit", "Available",
                "Threshold", "Status", "Expiry", "Donor"])
    for item in items:
        w.writerow([
            item.warehouse.code,
            item.category,
            item.item_name,
            item.unit,
            item.quantity_available,
            item.minimum_threshold,
            "Low Stock" if item.is_low_stock else "OK",
            item.expiry_date.strftime("%Y-%m-%d") if item.expiry_date else "",
            item.donor or "",
        ])
    return csv_response(buf, "inventory_report")


# ---------------------------------------------------------------------------
# Distribution Report
# ---------------------------------------------------------------------------

@reports_bp.route("/distribution-report")
@login_required
@roles_required(*_REPORT_ROLES)
def distribution_report():
    batches = (
        DistributionBatch.query
        .order_by(DistributionBatch.planned_date.desc())
        .all()
    )

    batch_stats = []
    for b in batches:
        total     = b.records.count()
        completed = b.records.filter_by(status="completed").count()
        batch_stats.append({
            "batch":     b,
            "total":     total,
            "completed": completed,
            "rate":      round((completed / total * 100) if total else 0, 1),
        })

    overall_completed = DistributionRecord.query.filter_by(status="completed").count()
    overall_total     = DistributionRecord.query.count()

    return render_template(
        "reports/distribution_report.html",
        batch_stats=batch_stats,
        overall_completed=overall_completed,
        overall_total=overall_total,
    )


@reports_bp.route("/distribution-report/export")
@login_required
@roles_required(*_REPORT_ROLES)
def export_distribution_report():
    records = (
        DistributionRecord.query
        .order_by(DistributionRecord.distribution_timestamp.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Batch Code", "Beneficiary", "NIN (Masked)",
        "Item", "Quantity", "Unit", "Distribution Point",
        "NIN Confirmed", "Status", "Timestamp",
    ])
    for r in records:
        w.writerow([
            r.batch.batch_code,
            r.beneficiary.full_name,
            r.beneficiary.masked_nin,
            r.item.item_name,
            r.quantity_given,
            r.item.unit,
            r.distribution_point.name if r.distribution_point else "",
            "Yes" if r.nin_confirmed else "No",
            r.status,
            r.distribution_timestamp.strftime("%Y-%m-%d %H:%M") if r.distribution_timestamp else "",
        ])
    return csv_response(buf, "distribution_report")


# ---------------------------------------------------------------------------
# Applications Report (admin only)
# ---------------------------------------------------------------------------

@reports_bp.route("/applications-report")
@login_required
@roles_required("admin")
def applications_report():
    total    = Beneficiary.query.filter(Beneficiary.user_id.isnot(None)).count()
    pending  = Beneficiary.query.filter_by(status="pending").filter(Beneficiary.user_id.isnot(None)).count()
    approved = Beneficiary.query.filter_by(status="active").filter(Beneficiary.user_id.isnot(None)).count()
    rejected = Beneficiary.query.filter_by(status="rejected").filter(Beneficiary.user_id.isnot(None)).count()

    by_state = (
        db.session.query(State.name, func.count(Beneficiary.id).label("count"))
        .join(LocalGovernmentArea, LocalGovernmentArea.id == Beneficiary.lga_id)
        .join(State, State.id == LocalGovernmentArea.state_id)
        .filter(Beneficiary.user_id.isnot(None))
        .group_by(State.name)
        .order_by(func.count(Beneficiary.id).desc())
        .all()
    )

    vuln = {
        "disabled": Beneficiary.query.filter(Beneficiary.user_id.isnot(None), Beneficiary.is_disabled == True).count(),
        "pregnant": Beneficiary.query.filter(Beneficiary.user_id.isnot(None), Beneficiary.is_pregnant == True).count(),
        "elderly":  Beneficiary.query.filter(Beneficiary.user_id.isnot(None), Beneficiary.is_elderly == True).count(),
        "minor":    Beneficiary.query.filter(Beneficiary.user_id.isnot(None), Beneficiary.is_unaccompanied_minor == True).count(),
    }

    return render_template(
        "reports/applications_report.html",
        total=total, pending=pending, approved=approved, rejected=rejected,
        by_state=by_state, vuln=vuln,
    )


@reports_bp.route("/applications-report/export")
@login_required
@roles_required("admin")
def export_applications_report():
    apps = (
        Beneficiary.query
        .filter(Beneficiary.user_id.isnot(None))
        .order_by(Beneficiary.registered_at.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Full Name", "NIN (Masked)", "Gender", "LGA", "State",
        "NIN Verified", "Status", "Priority Score",
        "Disabled", "Pregnant", "Elderly", "Unaccompanied Minor",
        "Submitted", "Reviewed By", "Reviewed At", "Rejection Reason",
    ])
    for b in apps:
        w.writerow([
            b.full_name,
            b.masked_nin,
            b.gender,
            b.lga.name if b.lga else "",
            b.lga.state.name if b.lga else "",
            "Yes" if b.nin_verified else "No",
            b.status,
            b.priority_score,
            "Yes" if b.is_disabled else "No",
            "Yes" if b.is_pregnant else "No",
            "Yes" if b.is_elderly else "No",
            "Yes" if b.is_unaccompanied_minor else "No",
            b.registered_at.strftime("%Y-%m-%d %H:%M"),
            b.reviewer.username if b.reviewer else "",
            b.reviewed_at.strftime("%Y-%m-%d %H:%M") if b.reviewed_at else "",
            b.rejection_reason or "",
        ])
    return csv_response(buf, "applications_report")


# ---------------------------------------------------------------------------
# Audit Summary
# ---------------------------------------------------------------------------

@reports_bp.route("/audit-summary")
@login_required
@roles_required("admin")
def audit_summary():
    page = request.args.get("page", 1, type=int)
    logs = (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .paginate(page=page, per_page=30, error_out=False)
    )
    return render_template("reports/audit_summary.html", logs=logs)
