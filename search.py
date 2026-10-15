"""Search & Retrieval Interface.

Supports both text queries and barcode-scanner input (a barcode scanner
simply emits the barcode string followed by Enter, so it's handled the
same way as typed text) for immediate access to a product's cost, price,
and price history.
"""
from database import DEFAULT_DB_PATH, get_connection


def search_by_barcode(barcode, db_path=DEFAULT_DB_PATH):
    """Exact-match lookup, as used by a barcode scanner."""
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT products.*, suppliers.name AS supplier_name
               FROM products JOIN suppliers ON products.supplier_id = suppliers.id
               WHERE products.barcode = ?""",
            (barcode,),
        ).fetchone()


def search_by_text(query, db_path=DEFAULT_DB_PATH):
    """Case-insensitive partial match on product name or category."""
    like = f"%{query}%"
    with get_connection(db_path) as conn:
        return conn.execute(
            """SELECT products.*, suppliers.name AS supplier_name
               FROM products JOIN suppliers ON products.supplier_id = suppliers.id
               WHERE products.name LIKE ? COLLATE NOCASE
                  OR products.category LIKE ? COLLATE NOCASE
               ORDER BY products.name""",
            (like, like),
        ).fetchall()


def search(query, db_path=DEFAULT_DB_PATH):
    """Unified entry point: try an exact barcode match first, then fall
    back to a text search. This is what the UI should call regardless of
    whether the input came from a keyboard or a barcode scanner."""
    exact = search_by_barcode(query, db_path=db_path)
    if exact is not None:
        return [exact]
    return search_by_text(query, db_path=db_path)
