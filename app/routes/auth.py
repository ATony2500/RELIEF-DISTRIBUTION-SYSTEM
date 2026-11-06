"""
Authentication routes — login, logout, profile, change password.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.utils.audit import audit_log

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        user = User.query.filter_by(username=username).first()

        if user and user.is_active and user.check_password(password):
            from datetime import datetime
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            audit_log(
                action="LOGIN",
                entity_type="User",
                entity_id=user.id,
                description=f"User '{user.username}' logged in.",
            )
            db.session.commit()

            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))
        else:
            error = "Invalid username or password. Please try again."
            if user and not user.is_active:
                error = "Your account has been deactivated. Contact the administrator."

    return render_template("auth/login.html", error=error)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout")
@login_required
def logout():
    audit_log(
        action="LOGOUT",
        entity_type="User",
        entity_id=current_user.id,
        description=f"User '{current_user.username}' logged out.",
    )
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", current_user.full_name).strip()
        current_user.phone = request.form.get("phone", current_user.phone).strip()
        current_user.organisation = request.form.get(
            "organisation", current_user.organisation or ""
        ).strip()
        db.session.commit()
        audit_log(
            action="UPDATE_PROFILE",
            entity_type="User",
            entity_id=current_user.id,
            description="User updated their profile.",
        )
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")


# ---------------------------------------------------------------------------
# Change Password
# ---------------------------------------------------------------------------

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if not current_user.check_password(current_pw):
            error = "Current password is incorrect."
        elif len(new_pw) < 8:
            error = "New password must be at least 8 characters."
        elif new_pw != confirm_pw:
            error = "New passwords do not match."
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            audit_log(
                action="CHANGE_PASSWORD",
                entity_type="User",
                entity_id=current_user.id,
                description="User changed their password.",
            )
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/change_password.html", error=error)
