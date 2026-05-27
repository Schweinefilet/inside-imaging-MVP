"""Role-based access control decorators for Flask routes."""

from __future__ import annotations

from functools import wraps

from flask import flash, jsonify, redirect, request, session, url_for

from src.db.users import has_any_role


def require_role(*roles: str):
    """Decorator: logged-in user must hold at least one of *roles*."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            username = session.get("username")
            if not username:
                if request.is_json:
                    return jsonify({"error": "Unauthorized"}), 401
                return redirect(url_for("login"))
            if not has_any_role(username, list(roles)):
                if request.is_json:
                    return jsonify({"error": "Forbidden"}), 403
                flash("Access denied.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator
