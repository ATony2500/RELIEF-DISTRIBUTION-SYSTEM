"""
Authentication routes.
Improvement #2:  Rate-limit login to 10 attempts/minute per IP.
Improvement #4:  Password strength validation on change-password.
Improvement #17: timezone-aware datetimes.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from app.models.user import User
from app.models.beneficiary import Beneficiary
from app.utils.helpers import (
    commit_with_audit, form_str, form_vulnerability_flags,
    get_all_states, get_all_lgas, parse_date,
    beneficiary_role_required, utc_now,
)
from app.utils.nin_verifier import validate_nin_format, verify_nin

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Self-registration (new user account request)
# Default role is field_officer; admin can change it afterwards.
# Rate-limited to prevent account abuse.
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    states = get_all_states()
    error = None

    if request.method == "POST":
        username = form_str("username", max_len=64)
        email = form_str("email", max_len=120)
        full_name = form_str("full_name", max_len=120)
        phone = form_str("phone", max_len=20) or None
        organisation = form_str("organisation", max_len=120) or None
        state_id = request.form.get("state_id") or None
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not full_name:
            error = "Username, email, and full name are required."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."
        elif User.query.filter_by(email=email).first():
            error = "An account with that email already exists."
        else:
            strength_err = User.validate_password_strength(password)
            if strength_err:
                error = strength_err
            elif password != confirm:
                error = "Passwords do not match."
            else:
                new_user = User(
                    username=username,
                    email=email,
                    full_name=full_name,
                    phone=phone,
                    organisation=organisation,
                    state_id=int(state_id) if state_id else None,
                    role="beneficiary",
                    is_active=True,
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.flush()
                commit_with_audit(
                    action="SELF_REGISTER",
                    entity_type="User",
                    entity_id=new_user.id,
                    description=f"New beneficiary applicant '{username}' self-registered.",
                )
                # Auto-login and redirect to the application form
                login_user(new_user)
                flash("Account created! Please complete your relief application below.", "success")
                return redirect(url_for("auth.apply"))

    return render_template("auth/register.html", states=states, error=error)


# ---------------------------------------------------------------------------
# Beneficiary apply — aspirant submits personal details after account creation
# ---------------------------------------------------------------------------

@auth_bp.route("/apply", methods=["GET", "POST"])
@login_required
@beneficiary_role_required
@limiter.limit("5 per minute", methods=["POST"])
def apply():
    """Portal for users with role='beneficiary' to submit their application."""
    # Already applied?
    existing = Beneficiary.query.filter_by(user_id=current_user.id).first()

    lgas = get_all_lgas()
    error = None

    if request.method == "POST":
        # Double-submit guard
        if existing:
            error = "You have already submitted an application."
        else:
            nin         = form_str("nin", max_len=11)
            first_name  = form_str("first_name", max_len=80)
            last_name   = form_str("last_name",  max_len=80)
            middle_name = form_str("middle_name", max_len=80) or None
            dob_str     = request.form.get("date_of_birth", "").strip()
            gender      = request.form.get("gender", "")
            phone       = form_str("phone", max_len=20) or None
            email       = form_str("email", max_len=120) or None
            lga_id      = request.form.get("lga_id", type=int)
            address     = form_str("address", max_len=255)
            vuln        = form_vulnerability_flags()

            if not validate_nin_format(nin):
                error = "NIN must be exactly 11 numeric digits."
            elif Beneficiary.nin_exists(nin):
                error = "A beneficiary with this NIN is already registered."
            elif not first_name or not last_name:
                error = "First name and last name are required."
            elif not gender:
                error = "Please select your gender."
            elif not lga_id:
                error = "Please select your LGA."
            else:
                verify_result = verify_nin(
                    nin, firstname=first_name, lastname=last_name, dob=dob_str,
                )
                dob = parse_date(dob_str)

                b = Beneficiary(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    date_of_birth=dob,
                    gender=gender,
                    phone=phone,
                    email=email,
                    lga_id=lga_id,
                    address=address,
                    nin_verified=verify_result["verified"],
                    verification_date=utc_now() if verify_result["verified"] else None,
                    verification_notes=verify_result["message"],
                    status="pending",
                    registered_by=current_user.id,
                    user_id=current_user.id,
                    **vuln,
                )
                b.set_nin(nin)
                b.priority_score = b.compute_priority_score()
                db.session.add(b)
                db.session.flush()
                commit_with_audit(
                    action="BENEFICIARY_APPLY",
                    entity_type="Beneficiary",
                    entity_id=b.id,
                    description=f"User '{current_user.username}' submitted relief application.",
                )
                flash("Application submitted! You will be notified once it is reviewed.", "success")
                return redirect(url_for("auth.portal"))

    return render_template(
        "auth/apply.html",
        lgas=lgas,
        existing=existing,
        error=error,
    )


# ---------------------------------------------------------------------------
# Beneficiary portal — shows application status after login
# ---------------------------------------------------------------------------

@auth_bp.route("/portal")
@login_required
@beneficiary_role_required
def portal():
    """Landing page for beneficiary-role users."""
    application = Beneficiary.query.filter_by(user_id=current_user.id).first()
    return render_template("auth/portal.html", application=application)


# ---------------------------------------------------------------------------
# Edit pending application
# ---------------------------------------------------------------------------

@auth_bp.route("/apply/edit", methods=["GET", "POST"])
@login_required
@beneficiary_role_required
@limiter.limit("10 per minute", methods=["POST"])
def apply_edit():
    """Allow a beneficiary user to edit their application while it is still pending."""
    b = Beneficiary.query.filter_by(user_id=current_user.id).first()
    if not b:
        flash("You have not submitted an application yet.", "warning")
        return redirect(url_for("auth.apply"))
    if b.status != "pending":
        flash("Your application can no longer be edited.", "info")
        return redirect(url_for("auth.portal"))

    lgas = get_all_lgas()
    error = None

    if request.method == "POST":
        first_name  = form_str("first_name", max_len=80)
        last_name   = form_str("last_name",  max_len=80)
        middle_name = form_str("middle_name", max_len=80) or None
        dob_str     = request.form.get("date_of_birth", "").strip()
        gender      = request.form.get("gender", "")
        phone       = form_str("phone", max_len=20) or None
        email       = form_str("email", max_len=120) or None
        lga_id      = request.form.get("lga_id", type=int)
        address     = form_str("address", max_len=255)
        vuln        = form_vulnerability_flags()

        if not first_name or not last_name:
            error = "First name and last name are required."
        elif not gender:
            error = "Please select your gender."
        elif not lga_id:
            error = "Please select your LGA."
        else:
            b.first_name    = first_name
            b.last_name     = last_name
            b.middle_name   = middle_name
            b.date_of_birth = parse_date(dob_str)
            b.gender        = gender
            b.phone         = phone
            b.email         = email
            b.lga_id        = lga_id
            b.address       = address
            for k, v in vuln.items():
                setattr(b, k, v)
            b.priority_score = b.compute_priority_score()
            commit_with_audit(
                action="EDIT_APPLICATION",
                entity_type="Beneficiary",
                entity_id=b.id,
                description=f"Applicant '{current_user.username}' updated their application.",
            )
            flash("Application updated successfully.", "success")
            return redirect(url_for("auth.portal"))

    return render_template("auth/apply_edit.html", b=b, lgas=lgas, error=error)


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
            # Beneficiary-role users land on their portal, not the ops dashboard
            if user.role == "beneficiary":
                return redirect(url_for("auth.portal"))
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
        full_name    = form_str("full_name",    max_len=120)
        phone        = form_str("phone",        max_len=20)
        organisation = form_str("organisation", max_len=120)

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
