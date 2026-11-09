"""
Authentication routes.
Improvement #2:  Rate-limit login to 10 attempts/minute per IP.
Improvement #4:  Password strength validation on change-password.
Improvement #17: timezone-aware datetimes.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import limiter
from app.models.user import User
from app.utils.helpers import commit_with_audit

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Login  (#2 — 10 attempts per minute per IP)
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
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
            user.last_login = datetime.now(timezone.utc)
            login_user(user, remember=remember)
            commit_with_audit(
                action="LOGIN",
                entity_type="User",
                entity_id=user.id,
                description=f"User '{user.username}' logged in.",
            )

            next_page = request.args.get("next")
            # Guard against open-redirect
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("main.dashboard"))
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
    commit_with_audit(
        action="LOGOUT",
        entity_type="User",
        entity_id=current_user.id,
        description=f"User '{current_user.username}' logged out.",
    )
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
        # Input length validation (#18)
        full_name = request.form.get("full_name", "").strip()[:120]
        phone = request.form.get("phone", "").strip()[:20]
        organisation = request.form.get("organisation", "").strip()[:120]

        if not full_name:
            flash("Full name cannot be empty.", "danger")
            return redirect(url_for("auth.profile"))

        current_user.full_name = full_name
        current_user.phone = phone or None
        current_user.organisation = organisation or None
        commit_with_audit(
            action="UPDATE_PROFILE",
            entity_type="User",
            entity_id=current_user.id,
            description="User updated their profile.",
        )
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")


# ---------------------------------------------------------------------------
# Change Password  (#4 — strength validation)
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
        elif new_pw != confirm_pw:
            error = "New passwords do not match."
        else:
            # #4: strength check
            strength_error = User.validate_password_strength(new_pw)
            if strength_error:
                error = strength_error
            else:
                current_user.set_password(new_pw)
                commit_with_audit(
                    action="CHANGE_PASSWORD",
                    entity_type="User",
                    entity_id=current_user.id,
                    description="User changed their password.",
                )
                flash("Password changed successfully.", "success")
                return redirect(url_for("auth.profile"))

    return render_template("auth/change_password.html", error=error)
