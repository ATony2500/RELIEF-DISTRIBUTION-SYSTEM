"""
Miscellaneous helper functions used across the application.
"""

import random
import string
from datetime import datetime, timezone

from flask import request, abort

from app import db


# ---------------------------------------------------------------------------
# Timestamp helper (shared by all models)
# ---------------------------------------------------------------------------

def utc_now():
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Code generators
# ---------------------------------------------------------------------------

def generate_code(prefix: str, length: int = 8) -> str:
    """
    Generate a unique-ish alphanumeric code, e.g. 'BEN-A3F7X2Q1'.
    Not cryptographically guaranteed unique — check DB after generation.
    """
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=length))
    return f"{prefix}-{suffix}"


def generate_batch_code() -> str:
    """Generate a distribution batch code like 'BATCH-2026-A3F7'."""
    return generate_code(f"BATCH-{utc_now().year}", 4)


def generate_route_code() -> str:
    """Generate a route code like 'RTE-2026-X9B2'."""
    return generate_code(f"RTE-{utc_now().year}", 4)


def generate_household_code() -> str:
    """Generate a household code like 'HH-A3F7X2Q1'."""
    return generate_code("HH", 8)


def generate_unique_code(generator, model, column, attempts=10):
    """Retry code generation until a non-colliding value is found."""
    for _ in range(attempts):
        code = generator()
        if not model.query.filter_by(**{column: code}).first():
            return code
    raise RuntimeError(f"Could not generate unique code after {attempts} attempts.")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def paginate_query(query, page: int, per_page: int = 20):
    """Thin wrapper around SQLAlchemy pagination."""
    return query.paginate(page=page, per_page=per_page, error_out=False)


# ---------------------------------------------------------------------------
# Generic ORM helpers
# ---------------------------------------------------------------------------

def get_or_404(model, id):
    """Fetch a model instance by primary key or abort with 404."""
    obj = db.session.get(model, id)
    if not obj:
        abort(404)
    return obj


def parse_date(date_str, fmt="%Y-%m-%d"):
    """Parse a date string, returning None on failure or empty input."""
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), fmt).date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Form helpers
# ---------------------------------------------------------------------------

def form_str(name, default="", max_len=None):
    """Get a stripped string from the request form, optionally capped."""
    value = request.form.get(name, default)
    if value is None:
        return default
    value = value.strip()
    if max_len is not None:
        value = value[:max_len]
    return value


# ---------------------------------------------------------------------------
# Audit + commit helper
# ---------------------------------------------------------------------------

def commit_with_audit(action, entity_type=None, entity_id=None, description=None):
    """Log an audit event and commit the transaction in one step."""
    from app.utils.audit import audit_log
    audit_log(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Repeated query helpers
# ---------------------------------------------------------------------------

def get_all_states():
    """Return all states ordered by name."""
    from app.models.zone import State
    return State.query.order_by(State.name).all()


def get_active_warehouses():
    """Return all active warehouses ordered by name."""
    from app.models.inventory import Warehouse
    return Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()


def get_all_lgas():
    """Return all LGAs ordered by name."""
    from app.models.zone import LocalGovernmentArea
    return LocalGovernmentArea.query.order_by(LocalGovernmentArea.name).all()


# ---------------------------------------------------------------------------
# Beneficiary lookup helper (shared by api.py and distribution.py)
# ---------------------------------------------------------------------------

def beneficiary_nin_lookup(nin):
    """Look up an active beneficiary by NIN, returning a JSON-ready dict."""
    from app.models.beneficiary import Beneficiary
    b = Beneficiary.find_by_nin(nin)
    if not b or b.status != "active":
        return {"found": False, "message": "No active beneficiary found with that NIN."}
    return {
        "found": True,
        "id": b.id,
        "full_name": b.full_name,
        "nin_verified": b.nin_verified,
        "masked_nin": b.masked_nin,
        "lga": b.lga.name if b.lga else "",
    }


# ---------------------------------------------------------------------------
# Vulnerability flags helper  (#3)
# ---------------------------------------------------------------------------

def form_vulnerability_flags() -> dict:
    """
    Extract all five vulnerability checkbox values from the current request form.
    Returns a dict with boolean values, ready to be unpacked onto a Beneficiary.
    """
    return {
        "is_disabled":            request.form.get("is_disabled")            == "on",
        "is_pregnant":            request.form.get("is_pregnant")            == "on",
        "is_elderly":             request.form.get("is_elderly")             == "on",
        "is_unaccompanied_minor": request.form.get("is_unaccompanied_minor") == "on",
        "is_head_of_household":   request.form.get("is_head_of_household")   == "on",
    }


# ---------------------------------------------------------------------------
# Beneficiary-role guard decorator  (#9)
# ---------------------------------------------------------------------------

def beneficiary_role_required(f):
    """
    Redirect any non-beneficiary user to the main dashboard.
    Apply after @login_required.
    """
    from functools import wraps
    from flask import redirect, url_for
    from flask_login import current_user

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "beneficiary":
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Shared CSV response helper  (#11)
# ---------------------------------------------------------------------------

def csv_response(buf, filename_stem: str):
    """
    Return a CSV download Response from an io.StringIO buffer.
    Shared by reports.py and admin.py to avoid duplication.
    """
    import io
    from flask import Response
    stamp = utc_now().strftime("%Y%m%d_%H%M")
    filename = f"nrds_{filename_stem}_{stamp}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
