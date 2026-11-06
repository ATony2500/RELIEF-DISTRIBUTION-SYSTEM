"""
Miscellaneous helper functions used across the application.
"""

import random
import string
from datetime import datetime


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
    year = datetime.utcnow().year
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"BATCH-{year}-{suffix}"


def generate_route_code() -> str:
    """Generate a route code like 'RTE-2026-X9B2'."""
    year = datetime.utcnow().year
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"RTE-{year}-{suffix}"


def generate_household_code() -> str:
    """Generate a household code like 'HH-A3F7X2Q1'."""
    return generate_code("HH", 8)


def paginate_query(query, page: int, per_page: int = 20):
    """
    Thin wrapper around SQLAlchemy pagination.
    Returns a Pagination object.
    """
    return query.paginate(page=page, per_page=per_page, error_out=False)


def format_datetime(dt) -> str:
    """Return a nicely formatted datetime string."""
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y, %H:%M")


def format_date(d) -> str:
    """Return a nicely formatted date string."""
    if d is None:
        return "—"
    return d.strftime("%d %b %Y")
