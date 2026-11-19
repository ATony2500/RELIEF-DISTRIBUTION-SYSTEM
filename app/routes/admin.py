"""
Admin routes — user management, system configuration, audit log viewer.
Only accessible to users with role='admin'.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request,
)
from flask_login import login_required, current_user
import csv
import io
from app import db
from app.models.user import User
from app.models.audit import AuditLog
from app.models.beneficiary import Beneficiary
from app.models.zone import DistributionPoint
from app.models.nin_record import NinRecord
from app.utils.decorators import admin_required
from app.utils.helpers import (
    paginate_query, get_or_404, form_str,
    get_all_states, get_all_lgas, commit_with_audit, utc_now, csv_response,
)
from app.utils.nin_verifier import validate_nin_format

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


# ---------------------------------------------------------------------------
# Beneficiary Application Review
# ---------------------------------------------------------------------------

@admin_bp.route("/applications")
@login_required
@admin_required
def applications():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "pending")
    sort = request.args.get("sort", "priority")  # priority | date

    q = Beneficiary.query.filter(Beneficiary.user_id.isnot(None))
    if status_filter:
        q = q.filter_by(status=status_filter)

    if sort == "priority":
        q = q.order_by(Beneficiary.priority_score.desc(), Beneficiary.registered_at.asc())
    else:
        q = q.order_by(Beneficiary.registered_at.desc())

    apps = paginate_query(q, page)
    return render_template(
        "admin/applications.html",
        apps=apps,
        status_filter=status_filter,
        sort=sort,
    )


@admin_bp.route("/applications/<int:b_id>")
@login_required
@admin_required
def application_detail(b_id):
    b = get_or_404(Beneficiary, b_id)
    return render_template("admin/application_detail.html", b=b)


@admin_bp.route("/applications/<int:b_id>/review", methods=["POST"])
@login_required
@admin_required
def review_application(b_id):
    b = get_or_404(Beneficiary, b_id)
    action           = request.form.get("action")
    rejection_reason = request.form.get("rejection_reason", "").strip() or None
    review_notes     = request.form.get("review_notes", "").strip() or None

    if action == "approve":
        b.status           = "active"
        b.reviewed_by      = current_user.id
        b.reviewed_at      = utc_now()
        b.rejection_reason = None          # clear any previous reason
        b.review_notes     = review_notes
        flash(f"Application for {b.full_name} approved.", "success")
        audit_action = "APPROVE_APPLICATION"

    elif action == "reject":
        if not rejection_reason:
            flash("Please provide a reason for rejection.", "warning")
            return redirect(url_for("admin.application_detail", b_id=b_id))
        b.status           = "rejected"
        b.reviewed_by      = current_user.id
        b.reviewed_at      = utc_now()
        b.rejection_reason = rejection_reason
        b.review_notes     = review_notes
        flash(f"Application for {b.full_name} rejected.", "warning")
        audit_action = "REJECT_APPLICATION"

    else:
        flash("Invalid action.", "danger")
        return redirect(url_for("admin.application_detail", b_id=b_id))

    commit_with_audit(
        action=audit_action,
        entity_type="Beneficiary",
        entity_id=b.id,
        description=(
            f"Admin '{current_user.username}' {action}d application for '{b.full_name}'."
            + (f" Reason: {rejection_reason}" if rejection_reason else "")
        ),
    )
    return redirect(url_for("admin.applications"))


# ---------------------------------------------------------------------------
# NIN Registry — local NIMC stand-in
# ---------------------------------------------------------------------------

@admin_bp.route("/nin-registry")
@login_required
@admin_required
def nin_registry():
    page   = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()[:80]
    q = NinRecord.query
    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                NinRecord.firstname.ilike(like),
                NinRecord.lastname.ilike(like),
                NinRecord.nin_masked.ilike(like),
            )
        )
    records = paginate_query(q.order_by(NinRecord.created_at.desc()), page)
    return render_template("admin/nin_registry.html",
                           records=records, search=search)


@admin_bp.route("/nin-registry/add", methods=["GET", "POST"])
@login_required
@admin_required
def nin_registry_add():
    error = None

    if request.method == "POST":
        nin        = form_str("nin", max_len=11)
        firstname  = form_str("firstname", max_len=80)
        lastname   = form_str("lastname",  max_len=80)
        middlename = form_str("middlename", max_len=80) or None
        gender     = request.form.get("gender", "")
        birthdate  = form_str("birthdate", max_len=20) or None
        phone      = form_str("phone", max_len=20) or None
        state_of_origin = form_str("state_of_origin", max_len=80) or None
        lga_of_origin   = form_str("lga_of_origin",   max_len=80) or None

        if not validate_nin_format(nin):
            error = "NIN must be exactly 11 numeric digits."
        elif NinRecord.nin_exists(nin):
            error = "A record with this NIN already exists."
        elif not firstname or not lastname or not gender:
            error = "First name, last name, and gender are required."
        else:
            rec = NinRecord(
                firstname=firstname, lastname=lastname,
                middlename=middlename, gender=gender,
                birthdate=birthdate, phone=phone,
                state_of_origin=state_of_origin,
                lga_of_origin=lga_of_origin,
            )
            NinRecord.set_nin(rec, nin)
            db.session.add(rec)
            db.session.flush()
            commit_with_audit("NIN_REGISTRY_ADD", "NinRecord", rec.id,
                              f"Added NIN record for {rec.full_name}.")
            flash(f"NIN record for {rec.full_name} added.", "success")
            return redirect(url_for("admin.nin_registry"))

    return render_template("admin/nin_registry_add.html", error=error)


@admin_bp.route("/nin-registry/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def nin_registry_edit(rec_id):
    rec = get_or_404(NinRecord, rec_id)
    error = None

    if request.method == "POST":
        rec.firstname  = form_str("firstname", max_len=80) or rec.firstname
        rec.lastname   = form_str("lastname",  max_len=80) or rec.lastname
        rec.middlename = form_str("middlename", max_len=80) or None
        rec.gender     = request.form.get("gender", rec.gender)
        rec.birthdate  = form_str("birthdate", max_len=20) or rec.birthdate
        rec.phone      = form_str("phone", max_len=20) or None
        rec.state_of_origin = form_str("state_of_origin", max_len=80) or None
        rec.lga_of_origin   = form_str("lga_of_origin",   max_len=80) or None
        rec.is_active  = request.form.get("is_active") == "on"
        commit_with_audit("NIN_REGISTRY_EDIT", "NinRecord", rec.id,
                          f"Edited NIN record for {rec.full_name}.")
        flash("Record updated.", "success")
        return redirect(url_for("admin.nin_registry"))

    return render_template("admin/nin_registry_edit.html", rec=rec, error=error)


@admin_bp.route("/nin-registry/<int:rec_id>/delete", methods=["POST"])
@login_required
@admin_required
def nin_registry_delete(rec_id):
    rec = get_or_404(NinRecord, rec_id)
    name = rec.full_name
    db.session.delete(rec)
    commit_with_audit("NIN_REGISTRY_DELETE", "NinRecord", rec_id,
                      f"Deleted NIN record for {name}.")
    flash(f"Record for {name} deleted.", "success")
    return redirect(url_for("admin.nin_registry"))


@admin_bp.route("/nin-registry/import", methods=["GET", "POST"])
@login_required
@admin_required
def nin_registry_import():
    """Bulk import NIN records from an uploaded CSV file."""
    error = None
    results = None

    if request.method == "POST":
        f = request.files.get("csv_file")
        if not f or not f.filename.endswith(".csv"):
            error = "Please upload a .csv file."
        else:
            stream = io.StringIO(f.stream.read().decode("utf-8-sig"), newline="")
            reader = csv.DictReader(stream)
            added = skipped = errors_count = 0
            row_errors = []

            for i, row in enumerate(reader, start=2):   # row 1 = header
                nin = row.get("nin", "").strip()
                firstname  = row.get("firstname",  "").strip()
                lastname   = row.get("lastname",   "").strip()
                middlename = row.get("middlename", "").strip() or None
                gender     = row.get("gender",     "").strip()
                birthdate  = row.get("birthdate",  "").strip() or None
                phone      = row.get("phone",      "").strip() or None
                state_of_origin = row.get("state_of_origin", "").strip() or None
                lga_of_origin   = row.get("lga_of_origin",   "").strip() or None

                if not validate_nin_format(nin):
                    row_errors.append(f"Row {i}: invalid NIN '{nin}'")
                    errors_count += 1
                    continue
                if NinRecord.nin_exists(nin):
                    skipped += 1
                    continue
                if not firstname or not lastname or not gender:
                    row_errors.append(f"Row {i}: firstname, lastname, gender required.")
                    errors_count += 1
                    continue

                rec = NinRecord(
                    firstname=firstname, lastname=lastname,
                    middlename=middlename, gender=gender,
                    birthdate=birthdate, phone=phone,
                    state_of_origin=state_of_origin,
                    lga_of_origin=lga_of_origin,
                )
                NinRecord.set_nin(rec, nin)
                db.session.add(rec)
                added += 1

            db.session.commit()
            commit_with_audit("NIN_REGISTRY_IMPORT", "NinRecord", None,
                              f"CSV import: {added} added, {skipped} skipped, {errors_count} errors.")
            results = {"added": added, "skipped": skipped,
                       "errors": errors_count, "row_errors": row_errors[:20]}

    return render_template("admin/nin_registry_import.html",
                           error=error, results=results)


@admin_bp.route("/nin-registry/csv-template")
@login_required
@admin_required
def nin_registry_csv_template():
    """Return a blank CSV template for bulk NIN import."""
    buf = io.StringIO()
    buf.write("nin,firstname,lastname,middlename,gender,birthdate,phone,state_of_origin,lga_of_origin\n")
    buf.write("12345678901,Amina,Bello,Fatima,Female,12-03-1990,08012345678,Kano,Kano Municipal\n")
    return csv_response(buf, "nin_registry_template")
