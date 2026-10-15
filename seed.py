"""Loads sample sari-sari-store data so the system can be demoed without
manually encoding products first (supports Phase E/F migration: encoding
existing price data)."""
from database import DEFAULT_DB_PATH, init_db, get_connection
import repository


def seed(db_path=DEFAULT_DB_PATH):
    init_db(db_path)

    with get_connection(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    if existing:
        print("Database already has data; skipping seed.")
        return

    coke_supplier = repository.add_supplier("Coca-Cola FEMSA", "0917-000-1111", db_path=db_path)
    nestle_supplier = repository.add_supplier("Nestle Philippines", "0917-000-2222", db_path=db_path)
    local_supplier = repository.add_supplier("Local Rice Trader", "0917-000-3333", db_path=db_path)

    products = [
        ("4800016641234", "Coke 1.5L", "Beverage", coke_supplier, 55.0, 65.0, 15.0),
        ("4800016649876", "Nescafe Classic 20g", "Coffee", nestle_supplier, 8.0, 12.0, 15.0),
        ("4800016645555", "Bear Brand Powdered Milk 150g", "Dairy", nestle_supplier, 42.0, 48.0, 15.0),
        ("4800016648888", "Well-Milled Rice 1kg", "Staples", local_supplier, 48.0, 50.0, 15.0),
    ]
    product_ids = []
    for barcode, name, category, supplier_id, cost, price, threshold in products:
        pid = repository.add_product(barcode, name, category, supplier_id, cost, price, threshold, db_path=db_path)
        product_ids.append(pid)

    # Simulate a short price history (e.g. supplier cost creeping up on rice).
    history_bumps = {
        product_ids[3]: [(44.0, 48.0), (46.0, 49.0), (48.0, 50.0)],
        product_ids[0]: [(52.0, 63.0), (53.0, 64.0), (55.0, 65.0)],
    }
    for pid, bumps in history_bumps.items():
        for cost, price in bumps:
            repository.update_prices(pid, supplier_cost=cost, retail_price=price, db_path=db_path)

    repository.add_transaction(product_ids[0], 2, 65.0, db_path=db_path)
    repository.add_transaction(product_ids[3], 1, 50.0, db_path=db_path)

    print(f"Seeded {len(product_ids)} products across {3} suppliers.")


if __name__ == "__main__":
    seed()
