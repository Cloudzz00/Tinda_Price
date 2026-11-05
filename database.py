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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('admin', 'supplier', 'store_owner')),
    supplier_id INTEGER REFERENCES suppliers(id)
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
    recorded_at TEXT NOT NULL,
    updated_by INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    sale_price REAL NOT NULL,
    transaction_date TEXT NOT NULL,
    recorded_by INTEGER REFERENCES users(id)
);
"""

# Columns added after the tables above first shipped. init_db() adds
# them to any pre-existing database file that predates the column,
# since CREATE TABLE IF NOT EXISTS alone won't alter a table that's
# already there.
_COLUMN_MIGRATIONS = {
    "price_history": [("updated_by", "INTEGER REFERENCES users(id)")],
    "transactions": [("recorded_by", "INTEGER REFERENCES users(id)")],
}


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


def _migrate_columns(conn):
    for table, columns in _COLUMN_MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate_columns(conn)
