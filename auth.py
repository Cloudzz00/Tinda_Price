"""Role-based access control: user accounts, password hashing, and the
login-session plumbing Flask routes use to enforce who can do what.

Three roles, matching how a real store/supplier relationship works:
  - admin:       manages suppliers, products, user accounts, and
                 variance thresholds; can see and edit everything.
  - supplier:    can only update the SUPPLIER COST of the products
                 tied to their own supplier record -- never the retail
                 price, and never another supplier's products.
  - store_owner: sets retail price, records sales, and reads the
                 dashboard/reports/forecasts -- but can't touch
                 supplier cost or manage suppliers/users.
"""
from functools import wraps

from flask import session, g, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash

from database import DEFAULT_DB_PATH, get_connection

ROLES = ("admin", "supplier", "store_owner")

ROLE_LABELS = {
    "admin": "Admin",
    "supplier": "Supplier",
    "store_owner": "Store Owner",
}


def create_user(username, password, role, display_name="", supplier_id=None,
                 db_path=DEFAULT_DB_PATH):
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO users (username, password_hash, display_name, role, supplier_id)
               VALUES (?, ?, ?, ?, ?)""",
            (username, generate_password_hash(password), display_name, role, supplier_id),
        )
        return cur.lastrowid


def get_user_by_username(username, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user_by_id(user_id, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT users.*, suppliers.name AS supplier_name
               FROM users LEFT JOIN suppliers ON users.supplier_id = suppliers.id
               ORDER BY users.role, users.username"""
        ).fetchall()


def set_user_supplier(user_id, supplier_id, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute("UPDATE users SET supplier_id = ? WHERE id = ?", (supplier_id, user_id))


def update_display_name(user_id, display_name, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))


def update_password(user_id, new_password, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new_password), user_id),
        )


def verify_password(user, password):
    return check_password_hash(user["password_hash"], password)


# ---- Flask session plumbing -------------------------------------------

def load_logged_in_user(db_path=DEFAULT_DB_PATH):
    """Call once per request (see app.py's before_request). Populates
    flask.g.user with the current user row, or None if not logged in."""
    user_id = session.get("user_id")
    g.user = get_user_by_id(user_id, db_path=db_path) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in allowed_roles:
                flash("You don't have permission to do that.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator
