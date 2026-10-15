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
                 retail_price, variance_threshold_pct=15.0, db_path=DEFAULT_DB_PATH):
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
            """INSERT INTO price_history (product_id, supplier_cost, retail_price, recorded_at)
               VALUES (?, ?, ?, ?)""",
            (product_id, supplier_cost, retail_price, _now()),
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


def update_prices(product_id, supplier_cost=None, retail_price=None, db_path=DEFAULT_DB_PATH):
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
            """INSERT INTO price_history (product_id, supplier_cost, retail_price, recorded_at)
               VALUES (?, ?, ?, ?)""",
            (product_id, new_cost, new_price, _now()),
        )


def get_price_history(product_id, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT * FROM price_history WHERE product_id = ?
               ORDER BY recorded_at ASC""",
            (product_id,),
        ).fetchall()


# ---- Transactions ----------------------------------------------------------

def add_transaction(product_id, quantity, sale_price, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO transactions (product_id, quantity, sale_price, transaction_date)
               VALUES (?, ?, ?, ?)""",
            (product_id, quantity, sale_price, _now()),
        )
        return cur.lastrowid


def list_transactions(product_id=None, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        if product_id is None:
            return conn.execute(
                "SELECT * FROM transactions ORDER BY transaction_date DESC"
            ).fetchall()
        return conn.execute(
            """SELECT * FROM transactions WHERE product_id = ?
               ORDER BY transaction_date DESC""",
            (product_id,),
        ).fetchall()
