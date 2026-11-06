"""
Admin routes — user management, system configuration, audit log viewer.
Only accessible to users with role='admin'.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort,
)
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.audit import AuditLog
from app.models.zone import State, LocalGovernmentArea, DistributionPoint
from app.utils.audit import audit_log
from app.utils.decorators import admin_required
from app.utils.helpers import paginate_query

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

@admin_bp.route("/users")
@login_required
@admin_required
def user_list():
    page = request.args.get("page", 1, type=int)
    users = paginate_query(
        User.query.order_by(User.created_at.desc()), page
    )
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    states = State.query.order_by(State.name).all()
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "field_officer")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()
        organisation = request.form.get("organisation", "").strip()
        state_id = request.form.get("state_id") or None

        if User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            new_user = User(
                username=username,
                email=email,
                full_name=full_name,
                role=role,
                phone=phone,
                organisation=organisation,
                state_id=int(state_id) if state_id else None,
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()
            audit_log(
                action="CREATE_USER",
                entity_type="User",
                entity_id=new_user.id,
                description=f"Admin '{current_user.username}' created user '{username}' with role '{role}'.",
            )
            db.session.commit()
            flash(f"User '{username}' created successfully.", "success")
            return redirect(url_for("admin.user_list"))

    return render_template("admin/create_user.html", states=states, error=error)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.user_list"))
    user.is_active = not user.is_active
    action = "ACTIVATE_USER" if user.is_active else "DEACTIVATE_USER"
    audit_log(action=action, entity_type="User", entity_id=user.id,
              description=f"Admin toggled user '{user.username}' active={user.is_active}.")
    db.session.commit()
    flash(f"User '{user.username}' {'activated' if user.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.user_list"))


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

@admin_bp.route("/audit-log")
@login_required
@admin_required
def audit_log_view():
    page = request.args.get("page", 1, type=int)
    action_filter = request.args.get("action", "").strip()
    query = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if action_filter:
        query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
    logs = paginate_query(query, page)
    return render_template("admin/audit_log.html", logs=logs, action_filter=action_filter)


# ---------------------------------------------------------------------------
# Distribution Points Management
# ---------------------------------------------------------------------------

@admin_bp.route("/distribution-points")
@login_required
@admin_required
def distribution_points():
    page = request.args.get("page", 1, type=int)
    points = paginate_query(
        DistributionPoint.query.order_by(DistributionPoint.name), page
    )
    return render_template("admin/distribution_points.html", points=points)


@admin_bp.route("/distribution-points/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_distribution_point():
    lgas = LocalGovernmentArea.query.order_by(LocalGovernmentArea.name).all()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        lga_id = request.form.get("lga_id", type=int)
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        capacity = request.form.get("capacity", type=int)
        contact_person = request.form.get("contact_person", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()

        if not name or not lga_id or latitude is None or longitude is None:
            error = "Name, LGA, latitude, and longitude are required."
        else:
            dp = DistributionPoint(
                name=name,
                address=address,
                lga_id=lga_id,
                latitude=latitude,
                longitude=longitude,
                capacity=capacity,
                contact_person=contact_person,
                contact_phone=contact_phone,
            )
            db.session.add(dp)
            db.session.flush()
            audit_log(
                action="CREATE_DISTRIBUTION_POINT",
                entity_type="DistributionPoint",
                entity_id=dp.id,
                description=f"Created distribution point '{name}'.",
            )
            db.session.commit()
            flash(f"Distribution point '{name}' created.", "success")
            return redirect(url_for("admin.distribution_points"))

    return render_template("admin/create_distribution_point.html", lgas=lgas, error=error)
