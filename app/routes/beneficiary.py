"""
Beneficiary management routes — register, verify NIN, view, update, search.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, jsonify,
)
from flask_login import login_required, current_user
from app import db
from app.models.beneficiary import Beneficiary, BeneficiaryHousehold
from app.models.zone import LocalGovernmentArea, State
from app.utils.audit import audit_log
from app.utils.nin_verifier import verify_nin, validate_nin_format
from app.utils.helpers import paginate_query, generate_household_code
from app.utils.decorators import roles_required
from datetime import datetime

beneficiary_bp = Blueprint("beneficiary", __name__)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@beneficiary_bp.route("/")
@login_required
def list_beneficiaries():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    state_id = request.args.get("state_id", type=int)
    status_filter = request.args.get("status", "active")

    query = Beneficiary.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Beneficiary.first_name.ilike(like),
                Beneficiary.last_name.ilike(like),
                Beneficiary.nin.ilike(like),
                Beneficiary.phone.ilike(like),
            )
        )

    if state_id:
        query = query.join(LocalGovernmentArea).filter(
            LocalGovernmentArea.state_id == state_id
        )

    query = query.order_by(Beneficiary.registered_at.desc())
    beneficiaries = paginate_query(query, page)
    states = State.query.order_by(State.name).all()

    return render_template(
        "beneficiary/list.html",
        beneficiaries=beneficiaries,
        search=search,
        state_id=state_id,
        status_filter=status_filter,
        states=states,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@beneficiary_bp.route("/register", methods=["GET", "POST"])
@login_required
@roles_required("admin", "programme_coord", "field_officer")
def register():
    lgas = LocalGovernmentArea.query.order_by(LocalGovernmentArea.name).all()
    error = None

    if request.method == "POST":
        nin = request.form.get("nin", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        middle_name = request.form.get("middle_name", "").strip()
        dob_str = request.form.get("date_of_birth", "").strip()
        gender = request.form.get("gender", "")
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        lga_id = request.form.get("lga_id", type=int)
        address = request.form.get("address", "").strip()
        is_disabled = request.form.get("is_disabled") == "on"
        is_pregnant = request.form.get("is_pregnant") == "on"
        is_elderly = request.form.get("is_elderly") == "on"
        is_unaccompanied_minor = request.form.get("is_unaccompanied_minor") == "on"
        is_head = request.form.get("is_head_of_household") == "on"

        # Validations
        if not validate_nin_format(nin):
            error = "NIN must be exactly 11 numeric digits."
        elif Beneficiary.query.filter_by(nin=nin).first():
            error = "A beneficiary with this NIN is already registered."
        elif not first_name or not last_name:
            error = "First name and last name are required."
        elif not lga_id:
            error = "Please select an LGA."
        else:
            # NIN verification
            verify_result = verify_nin(nin)

            dob = None
            if dob_str:
                try:
                    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Create household if head of household
            household = None
            if is_head:
                household = BeneficiaryHousehold(
                    household_code=generate_household_code(),
                    head_of_household_nin=nin,
                    address=address,
                    lga_id=lga_id,
                    registered_by=current_user.id,
                )
                db.session.add(household)
                db.session.flush()

            beneficiary = Beneficiary(
                nin=nin,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name or None,
                date_of_birth=dob,
                gender=gender,
                phone=phone or None,
                email=email or None,
                lga_id=lga_id,
                address=address,
                household=household,
                is_head_of_household=is_head,
                is_disabled=is_disabled,
                is_pregnant=is_pregnant,
                is_elderly=is_elderly,
                is_unaccompanied_minor=is_unaccompanied_minor,
                nin_verified=verify_result["verified"],
                verification_date=datetime.utcnow() if verify_result["verified"] else None,
                verification_notes=verify_result["message"],
                registered_by=current_user.id,
            )
            db.session.add(beneficiary)
            db.session.flush()

            audit_log(
                action="CREATE_BENEFICIARY",
                entity_type="Beneficiary",
                entity_id=beneficiary.id,
                description=(
                    f"Registered beneficiary '{beneficiary.full_name}' "
                    f"(NIN: {beneficiary.masked_nin}). "
                    f"NIN verified: {verify_result['verified']}."
                ),
            )
            db.session.commit()

            if not verify_result["verified"]:
                flash(
                    f"Beneficiary registered, but NIN could not be verified: {verify_result['message']}",
                    "warning",
                )
            else:
                flash(
                    f"Beneficiary '{beneficiary.full_name}' registered and NIN verified successfully.",
                    "success",
                )
            return redirect(url_for("beneficiary.view", beneficiary_id=beneficiary.id))

    return render_template("beneficiary/register.html", lgas=lgas, error=error)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

@beneficiary_bp.route("/<int:beneficiary_id>")
@login_required
def view(beneficiary_id):
    b = db.session.get(Beneficiary, beneficiary_id)
    if not b:
        abort(404)
    return render_template("beneficiary/view.html", beneficiary=b)


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

@beneficiary_bp.route("/<int:beneficiary_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "programme_coord", "field_officer")
def edit(beneficiary_id):
    b = db.session.get(Beneficiary, beneficiary_id)
    if not b:
        abort(404)

    lgas = LocalGovernmentArea.query.order_by(LocalGovernmentArea.name).all()
    error = None

    if request.method == "POST":
        b.first_name = request.form.get("first_name", b.first_name).strip()
        b.last_name = request.form.get("last_name", b.last_name).strip()
        b.middle_name = request.form.get("middle_name", b.middle_name or "").strip() or None
        b.phone = request.form.get("phone", b.phone or "").strip() or None
        b.email = request.form.get("email", b.email or "").strip() or None
        b.address = request.form.get("address", b.address or "").strip()
        b.lga_id = request.form.get("lga_id", b.lga_id, type=int)
        b.is_disabled = request.form.get("is_disabled") == "on"
        b.is_pregnant = request.form.get("is_pregnant") == "on"
        b.is_elderly = request.form.get("is_elderly") == "on"
        b.is_unaccompanied_minor = request.form.get("is_unaccompanied_minor") == "on"
        new_status = request.form.get("status", b.status)
        if new_status in ("active", "inactive", "duplicate", "flagged"):
            b.status = new_status

        audit_log(
            action="UPDATE_BENEFICIARY",
            entity_type="Beneficiary",
            entity_id=b.id,
            description=f"Updated beneficiary '{b.full_name}'.",
        )
        db.session.commit()
        flash("Beneficiary record updated.", "success")
        return redirect(url_for("beneficiary.view", beneficiary_id=b.id))

    return render_template("beneficiary/edit.html", b=b, lgas=lgas, error=error)


# ---------------------------------------------------------------------------
# NIN Re-verification (AJAX)
# ---------------------------------------------------------------------------

@beneficiary_bp.route("/<int:beneficiary_id>/verify-nin", methods=["POST"])
@login_required
@roles_required("admin", "programme_coord", "field_officer")
def reverify_nin(beneficiary_id):
    b = db.session.get(Beneficiary, beneficiary_id)
    if not b:
        return jsonify({"success": False, "message": "Beneficiary not found"}), 404

    result = verify_nin(b.nin)
    b.nin_verified = result["verified"]
    b.verification_date = datetime.utcnow()
    b.verification_notes = result["message"]

    audit_log(
        action="REVERIFY_NIN",
        entity_type="Beneficiary",
        entity_id=b.id,
        description=f"Re-verified NIN for '{b.full_name}'. Result: {result['verified']}.",
    )
    db.session.commit()
    return jsonify({"success": True, "verified": result["verified"], "message": result["message"]})
