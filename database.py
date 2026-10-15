"""Centralized database layer for TINDA-PRICE.

Implements the "Centralized Database" objective: a single local SQLite
repository for products, suppliers, supplier costs, retail prices,
transactions, and price history, replacing manual notebooks/receipts.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "tinda_price.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    contact TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT UNIQUE,
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    supplier_cost REAL NOT NULL,
    retail_price REAL NOT NULL,
    variance_threshold_pct REAL NOT NULL DEFAULT 15.0
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    supplier_cost REAL NOT NULL,
    retail_price REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    sale_price REAL NOT NULL,
    transaction_date TEXT NOT NULL
);
"""


@contextmanager
def get_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
