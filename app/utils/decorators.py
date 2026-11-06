"""
Custom route decorators for role-based access control (RBAC).
"""

from functools import wraps
from flask import abort
from flask_login import current_user


def roles_required(*roles):
    """
    Decorator that restricts a view to users whose role is in the given list.
    Must be applied AFTER @login_required.

    Usage:
        @login_required
        @roles_required('admin', 'programme_coord')
        def my_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    """Shorthand: restrict view to admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated
