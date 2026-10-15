"""Loads real Philippine retail price data into the centralized database.

Source: World Bank Real-Time Food Price Monitoring, Philippines
(dataset version 2025-11-24), Metro Manila market, Nov 2024-Nov 2025.
https://microdata.worldbank.org/catalog/6172

The dataset only publishes the modeled retail (selling) price per month
-- it has no per-store supplier cost, since that figure genuinely only
exists in each store's own purchase records (the exact problem
TINDA-PRICE is built to solve). To still demonstrate the
variance-flagging module on real price movement, each product's
supplier cost is locked at a typical ASSUMED_STARTING_MARGIN_PCT below
its earliest available retail price (Nov 2024) and then left unchanged,
standing in for a store that priced at a healthy margin a year ago and
hasn't reviewed its cost basis since while the market price moved --
the scenario the module exists to catch. The retail-price trend itself,
used by the forecasting module, is the real published series unmodified.
"""
import csv
from pathlib import Path

import repository
from database import DEFAULT_DB_PATH, get_connection

DATA_FILE = Path(__file__).resolve().parent / "data" / "ph_food_prices_metro_manila.csv"

ITEM_LABELS = {
    "beans": ("Mung Beans (1kg)", "Legumes"),
    "cabbage": ("Cabbage (1kg)", "Vegetables"),
    "carrots": ("Carrots (1kg)", "Vegetables"),
    "eggs": ("Eggs (per piece)", "Eggs & Dairy"),
    "garlic": ("Garlic (1kg)", "Vegetables"),
    "onions": ("Red Onions (1kg)", "Vegetables"),
    "potatoes": ("Sweet Potatoes (1kg)", "Vegetables"),
    "rice": ("Well-Milled Rice (1kg)", "Staples"),
    "tomatoes": ("Tomatoes (1kg)", "Vegetables"),
}

SUPPLIER_NAME = "Metro Manila Wet Market (World Bank RTFP data)"

# Assumed margin the store was pricing at when it last set its cost
# basis (Nov 2024) -- see module docstring. Chosen to match the
# products' default variance_threshold_pct.
ASSUMED_STARTING_MARGIN_PCT = 15.0


def _load_series():
    """Returns {item: [(price_date, price), ...]} ordered oldest-first."""
    series = {}
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = row["item"]
            price = row["retail_price_php"]
            if not price:
                continue
            series.setdefault(item, []).append((row["price_date"], float(price)))
    for values in series.values():
        values.sort(key=lambda pair: pair[0])
    return series


def load(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT COUNT(*) AS n FROM suppliers WHERE name = ?", (SUPPLIER_NAME,)
        ).fetchone()["n"]
    if existing:
        print("Philippine market data already loaded; skipping.")
        return

    supplier_id = repository.add_supplier(
        SUPPLIER_NAME,
        "World Bank Real-Time Food Price Monitoring, dataset version 2025-11-24",
        db_path=db_path,
    )

    series = _load_series()
    loaded = 0
    for item, points in series.items():
        if item not in ITEM_LABELS or len(points) < 2:
            continue
        name, category = ITEM_LABELS[item]

        locked_cost = round(points[0][1] / (1 + ASSUMED_STARTING_MARGIN_PCT / 100), 2)
        latest_price = points[-1][1]

        product_id = repository.add_product(
            barcode=None,
            name=name,
            category=category,
            supplier_id=supplier_id,
            supplier_cost=locked_cost,
            retail_price=latest_price,
            db_path=db_path,
        )

        # Backfill the real monthly series (price_history), cost held at
        # its earliest value so variance-flagging reflects genuine drift.
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
            for price_date, price in points[1:]:
                conn.execute(
                    """INSERT INTO price_history
                       (product_id, supplier_cost, retail_price, recorded_at)
                       VALUES (?, ?, ?, ?)""",
                    (product_id, locked_cost, price, price_date),
                )
        loaded += 1

    print(f"Loaded {loaded} products from real Philippine market data "
          f"({SUPPLIER_NAME}).")


if __name__ == "__main__":
    load()
