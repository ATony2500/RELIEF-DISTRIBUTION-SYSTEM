"""
Admin routes — user management, system configuration, audit log viewer.
Only accessible to users with role='admin'.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request,
)
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.audit import AuditLog
from app.models.zone import DistributionPoint
from app.utils.decorators import admin_required
from app.utils.helpers import (
    paginate_query, get_or_404, form_str,
    get_all_states, get_all_lgas, commit_with_audit,
)

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
    states = get_all_states()
    error = None

    if request.method == "POST":
        username = form_str("username", max_len=64)
        email = form_str("email", max_len=120)
        full_name = form_str("full_name", max_len=120)
        role = request.form.get("role", "field_officer")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        phone = form_str("phone", max_len=20)
        organisation = form_str("organisation", max_len=120)
        state_id = request.form.get("state_id") or None

        if User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."
        else:
            # #4: strength validation
            strength_error = User.validate_password_strength(password)
            if strength_error:
                error = strength_error
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
                commit_with_audit(
                    action="CREATE_USER",
                    entity_type="User",
                    entity_id=new_user.id,
                    description=f"Admin '{current_user.username}' created user '{username}' with role '{role}'.",
                )
                flash(f"User '{username}' created successfully.", "success")
                return redirect(url_for("admin.user_list"))

    return render_template("admin/create_user.html", states=states, error=error)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    user = get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.user_list"))
    user.is_active = not user.is_active
    action = "ACTIVATE_USER" if user.is_active else "DEACTIVATE_USER"
    commit_with_audit(
        action=action, entity_type="User", entity_id=user.id,
        description=f"Admin toggled user '{user.username}' active={user.is_active}.",
    )
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
    lgas = get_all_lgas()
    error = None

    if request.method == "POST":
        name = form_str("name")
        address = form_str("address")
        lga_id = request.form.get("lga_id", type=int)
        latitude = request.form.get("latitude", type=float)
        longitude = request.form.get("longitude", type=float)
        capacity = request.form.get("capacity", type=int)
        contact_person = form_str("contact_person")
        contact_phone = form_str("contact_phone")

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
            commit_with_audit(
                action="CREATE_DISTRIBUTION_POINT",
                entity_type="DistributionPoint",
                entity_id=dp.id,
                description=f"Created distribution point '{name}'.",
            )
            flash(f"Distribution point '{name}' created.", "success")
            return redirect(url_for("admin.distribution_points"))

    return render_template("admin/create_distribution_point.html", lgas=lgas, error=error)
