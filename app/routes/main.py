"""
Main routes — dashboard and home.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.beneficiary import Beneficiary
from app.models.inventory import InventoryItem, Warehouse
from app.models.distribution import DistributionBatch, DistributionRecord
from app.models.audit import AuditLog

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    # --- Summary statistics ---
    total_beneficiaries = Beneficiary.query.filter_by(status="active").count()
    total_warehouses = Warehouse.query.filter_by(is_active=True).count()
    active_batches = DistributionBatch.query.filter_by(status="in_progress").count()
    completed_distributions = DistributionRecord.query.filter_by(status="completed").count()

    # Low-stock items
    all_items = InventoryItem.query.all()
    low_stock_items = [item for item in all_items if item.is_low_stock]

    # Recent audit entries (last 10)
    recent_logs = (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .limit(10)
        .all()
    )

    # Recent distributions (last 5 batches)
    recent_batches = (
        DistributionBatch.query
        .order_by(DistributionBatch.created_at.desc())
        .limit(5)
        .all()
    )

    stats = {
        "total_beneficiaries": total_beneficiaries,
        "total_warehouses": total_warehouses,
        "active_batches": active_batches,
        "completed_distributions": completed_distributions,
        "low_stock_count": len(low_stock_items),
    }

    return render_template(
        "main/dashboard.html",
        stats=stats,
        low_stock_items=low_stock_items[:5],
        recent_logs=recent_logs,
        recent_batches=recent_batches,
    )
