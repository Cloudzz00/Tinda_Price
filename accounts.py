"""Seeds the demo accounts used to present each role.

The supplier account is linked to the supplier record real_data.py
creates once that data is loaded -- before that, it's still usable for
login, it just won't own any products yet.
"""
import auth
from database import DEFAULT_DB_PATH
from real_data import SUPPLIER_NAME
import repository

DEFAULT_ACCOUNTS = [
    # username, password, role, display name
    ("admin", "admin123", "admin", "System Admin"),
    ("owner", "owner123", "store_owner", "Store Owner"),
    ("supplier", "supplier123", "supplier", "Metro Manila Wet Market"),
]


def ensure_default_accounts(db_path=DEFAULT_DB_PATH):
    for username, password, role, display_name in DEFAULT_ACCOUNTS:
        if auth.get_user_by_username(username, db_path=db_path) is None:
            auth.create_user(username, password, role, display_name, db_path=db_path)

    _link_supplier_account(db_path)


def _link_supplier_account(db_path):
    """Once the real-data supplier exists, point the demo supplier
    account at it so "update own products' cost" has something to own."""
    supplier_user = auth.get_user_by_username("supplier", db_path=db_path)
    if supplier_user is None or supplier_user["supplier_id"] is not None:
        return
    for supplier in repository.list_suppliers(db_path=db_path):
        if supplier["name"] == SUPPLIER_NAME:
            auth.set_user_supplier(supplier_user["id"], supplier["id"], db_path=db_path)
            return
