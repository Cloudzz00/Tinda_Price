"""Data-access functions over the centralized database.

Every write to a product's supplier cost or retail price appends a row to
price_history, so the Trend-Analysis Forecasting module always has a time
series to work from.
"""
from datetime import datetime, timezone

from database import get_connection, DEFAULT_DB_PATH


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- Suppliers -----------------------------------------------------------

def add_supplier(name, contact="", db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO suppliers (name, contact) VALUES (?, ?)", (name, contact)
        )
        return cur.lastrowid


def list_suppliers(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()


# ---- Products --------------------------------------------------------------

def add_product(barcode, name, category, supplier_id, supplier_cost,
                 retail_price, variance_threshold_pct=15.0, created_by=None,
                 db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO products
               (barcode, name, category, supplier_id, supplier_cost,
                retail_price, variance_threshold_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (barcode, name, category, supplier_id, supplier_cost,
             retail_price, variance_threshold_pct),
        )
        product_id = cur.lastrowid
        conn.execute(
            """INSERT INTO price_history (product_id, supplier_cost, retail_price, recorded_at, updated_by)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, supplier_cost, retail_price, _now(), created_by),
        )
        return product_id


def list_products(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT products.*, suppliers.name AS supplier_name
               FROM products JOIN suppliers ON products.supplier_id = suppliers.id
               ORDER BY products.name"""
        ).fetchall()


def get_product(product_id, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT products.*, suppliers.name AS supplier_name
               FROM products JOIN suppliers ON products.supplier_id = suppliers.id
               WHERE products.id = ?""",
            (product_id,),
        ).fetchone()


def update_prices(product_id, supplier_cost=None, retail_price=None, updated_by=None,
                   db_path=DEFAULT_DB_PATH):
    """Update a product's current cost/price and log the change to history."""
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if row is None:
            raise ValueError(f"No product with id {product_id}")

        new_cost = row["supplier_cost"] if supplier_cost is None else supplier_cost
        new_price = row["retail_price"] if retail_price is None else retail_price

        conn.execute(
            "UPDATE products SET supplier_cost = ?, retail_price = ? WHERE id = ?",
            (new_cost, new_price, product_id),
        )
        conn.execute(
            """INSERT INTO price_history (product_id, supplier_cost, retail_price, recorded_at, updated_by)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, new_cost, new_price, _now(), updated_by),
        )


def update_threshold(product_id, variance_threshold_pct, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE products SET variance_threshold_pct = ? WHERE id = ?",
            (variance_threshold_pct, product_id),
        )


def get_price_history(product_id, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT price_history.*, users.display_name AS updated_by_name,
                      users.username AS updated_by_username
               FROM price_history LEFT JOIN users ON price_history.updated_by = users.id
               WHERE price_history.product_id = ?
               ORDER BY price_history.recorded_at ASC""",
            (product_id,),
        ).fetchall()


def list_all_price_history(db_path=DEFAULT_DB_PATH):
    """Every price-history entry across all products, newest first, with
    the product name attached. Used to build the dashboard's price-update
    calendar."""
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT price_history.*, products.name AS product_name,
                      products.supplier_id AS product_supplier_id,
                      users.display_name AS updated_by_name,
                      users.username AS updated_by_username
               FROM price_history
               JOIN products ON price_history.product_id = products.id
               LEFT JOIN users ON price_history.updated_by = users.id
               ORDER BY price_history.recorded_at DESC"""
        ).fetchall()


# ---- Transactions ----------------------------------------------------------

def add_transaction(product_id, quantity, sale_price, recorded_by=None, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO transactions (product_id, quantity, sale_price, transaction_date, recorded_by)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, quantity, sale_price, _now(), recorded_by),
        )
        return cur.lastrowid


def list_transactions(product_id=None, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        if product_id is None:
            return conn.execute(
                """SELECT transactions.*, users.display_name AS recorded_by_name,
                          users.username AS recorded_by_username
                   FROM transactions LEFT JOIN users ON transactions.recorded_by = users.id
                   ORDER BY transactions.transaction_date DESC"""
            ).fetchall()
        return conn.execute(
            """SELECT transactions.*, users.display_name AS recorded_by_name,
                      users.username AS recorded_by_username
               FROM transactions LEFT JOIN users ON transactions.recorded_by = users.id
               WHERE transactions.product_id = ?
               ORDER BY transactions.transaction_date DESC""",
            (product_id,),
        ).fetchall()


# ---- Product requests (supplier proposes, admin approves) ------------------

_REQUEST_SELECT = """
    SELECT product_requests.*,
           suppliers.name AS supplier_name,
           requester.display_name AS requested_by_name,
           requester.username AS requested_by_username,
           reviewer.display_name AS reviewed_by_name,
           reviewer.username AS reviewed_by_username
    FROM product_requests
    JOIN suppliers ON product_requests.supplier_id = suppliers.id
    LEFT JOIN users AS requester ON product_requests.requested_by = requester.id
    LEFT JOIN users AS reviewer ON product_requests.reviewed_by = reviewer.id
"""


def create_product_request(name, category, barcode, supplier_id, supplier_cost,
                            requested_by, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO product_requests
               (name, category, barcode, supplier_id, supplier_cost, requested_by, requested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, category, barcode, supplier_id, supplier_cost, requested_by, _now()),
        )
        return cur.lastrowid


def list_product_requests(status=None, supplier_id=None, db_path=DEFAULT_DB_PATH):
    query = _REQUEST_SELECT
    clauses = []
    params = []
    if status:
        clauses.append("product_requests.status = ?")
        params.append(status)
    if supplier_id is not None:
        clauses.append("product_requests.supplier_id = ?")
        params.append(supplier_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY product_requests.requested_at DESC"
    with get_connection(db_path) as conn:
        return conn.execute(query, params).fetchall()


def get_product_request(request_id, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute(
            _REQUEST_SELECT + " WHERE product_requests.id = ?", (request_id,)
        ).fetchone()


def approve_product_request(request_id, retail_price, variance_threshold_pct,
                             reviewed_by, db_path=DEFAULT_DB_PATH):
    """Creates the live product from a pending request and marks it approved.
    Returns the new product's id."""
    with get_connection(db_path) as conn:
        req = conn.execute(
            "SELECT * FROM product_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if req is None:
            raise ValueError(f"No product request with id {request_id}")
        if req["status"] != "pending":
            raise ValueError("This request has already been reviewed")

        cur = conn.execute(
            """INSERT INTO products
               (barcode, name, category, supplier_id, supplier_cost,
                retail_price, variance_threshold_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (req["barcode"], req["name"], req["category"], req["supplier_id"],
             req["supplier_cost"], retail_price, variance_threshold_pct),
        )
        product_id = cur.lastrowid
        conn.execute(
            """INSERT INTO price_history (product_id, supplier_cost, retail_price, recorded_at, updated_by)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, req["supplier_cost"], retail_price, _now(), reviewed_by),
        )
        conn.execute(
            """UPDATE product_requests
               SET status = 'approved', reviewed_by = ?, reviewed_at = ?, product_id = ?
               WHERE id = ?""",
            (reviewed_by, _now(), product_id, request_id),
        )
        return product_id


def reject_product_request(request_id, reviewed_by, reason, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        req = conn.execute(
            "SELECT * FROM product_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if req is None:
            raise ValueError(f"No product request with id {request_id}")
        if req["status"] != "pending":
            raise ValueError("This request has already been reviewed")
        conn.execute(
            """UPDATE product_requests
               SET status = 'rejected', reviewed_by = ?, reviewed_at = ?, rejection_reason = ?
               WHERE id = ?""",
            (reviewed_by, _now(), reason, request_id),
        )
