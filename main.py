"""TINDA-PRICE: An Integrated Retail Price Intelligence and Predictive
Analytics Architecture for Dynamic Price Monitoring in Small Stores.

Interactive command-line interface tying together the four modules from
the System Architecture Design:
  1. Centralized Database        -> database.py / repository.py
  2. Search & Retrieval Interface -> search.py
  3. Variance-Flagging Module     -> variance.py
  4. Trend-Analysis Forecasting   -> forecasting.py
"""
import sys

from database import DEFAULT_DB_PATH, init_db
import repository
import search as search_module
import seed as seed_module
import variance
import forecasting

MENU = """
========================================
   TINDA-PRICE - Retail Price Intelligence
========================================
 1. Add supplier
 2. Add product
 3. List all products
 4. Search product (text or barcode)
 5. Update supplier cost / retail price
 6. View price history for a product
 7. Variance-flagging report
 8. Forecast price trend for a product
 9. Record a sale (transaction)
 10. Load sample data
 0. Exit
----------------------------------------
"""


def prompt(label, cast=str, default=None):
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{label}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return cast(raw)


def print_product_row(p):
    print(f"  #{p['id']:<4} {p['name']:<30} barcode={p['barcode'] or '-':<16} "
          f"cost={p['supplier_cost']:.2f} price={p['retail_price']:.2f} "
          f"supplier={p['supplier_name']}")


def action_add_supplier():
    name = prompt("Supplier name")
    contact = prompt("Contact info", default="")
    supplier_id = repository.add_supplier(name, contact)
    print(f"Added supplier #{supplier_id}: {name}")


def action_add_product():
    suppliers = repository.list_suppliers()
    if not suppliers:
        print("No suppliers yet. Add a supplier first.")
        return
    print("Suppliers:")
    for s in suppliers:
        print(f"  #{s['id']} {s['name']}")
    barcode = prompt("Barcode (scan or type)")
    name = prompt("Product name")
    category = prompt("Category", default="")
    supplier_id = prompt("Supplier id", cast=int)
    supplier_cost = prompt("Supplier cost", cast=float)
    retail_price = prompt("Retail price", cast=float)
    threshold = prompt("Minimum margin threshold %", cast=float, default="15")
    product_id = repository.add_product(
        barcode, name, category, supplier_id, supplier_cost, retail_price, threshold
    )
    print(f"Added product #{product_id}: {name}")


def action_list_products():
    products = repository.list_products()
    if not products:
        print("No products recorded yet.")
        return
    for p in products:
        print_product_row(p)


def action_search():
    query = prompt("Enter barcode or product/category keyword")
    results = search_module.search(query)
    if not results:
        print("No matching products.")
        return
    print(f"Found {len(results)} match(es):")
    for p in results:
        print_product_row(p)


def action_update_prices():
    product_id = prompt("Product id", cast=int)
    product = repository.get_product(product_id)
    if product is None:
        print("Product not found.")
        return
    print(f"Current: cost={product['supplier_cost']:.2f} price={product['retail_price']:.2f}")
    cost_raw = input("New supplier cost (blank = unchanged): ").strip()
    price_raw = input("New retail price (blank = unchanged): ").strip()
    cost = float(cost_raw) if cost_raw else None
    price = float(price_raw) if price_raw else None
    if cost is None and price is None:
        print("Nothing to update.")
        return
    repository.update_prices(product_id, supplier_cost=cost, retail_price=price)
    print("Updated. Change logged to price history.")


def action_price_history():
    product_id = prompt("Product id", cast=int)
    rows = repository.get_price_history(product_id)
    if not rows:
        print("No history for that product id.")
        return
    for r in rows:
        print(f"  {r['recorded_at']}  cost={r['supplier_cost']:.2f}  price={r['retail_price']:.2f}")


def action_variance_report():
    products = repository.list_products()
    if not products:
        print("No products recorded yet.")
        return
    results = [variance.evaluate_product(p) for p in products]
    print(f"{'Product':<30} {'Cost':>8} {'Price':>8} {'Margin%':>9} {'Threshold%':>11} {'Flag'}")
    for r in results:
        flag = "** REVIEW **" if r.flagged else ""
        print(f"{r.name:<30} {r.supplier_cost:>8.2f} {r.retail_price:>8.2f} "
              f"{r.variance_pct:>9.2f} {r.threshold_pct:>11.2f} {flag}")
    flagged = [r for r in results if r.flagged]
    print(f"\n{len(flagged)} of {len(results)} product(s) flagged for price review.")


def action_forecast():
    product_id = prompt("Product id", cast=int)
    product = repository.get_product(product_id)
    if product is None:
        print("Product not found.")
        return
    history = repository.get_price_history(product_id)
    if len(history) < 2:
        print("Not enough price history yet for a forecast (need at least 2 records).")
        return
    result = forecasting.forecast_for_product(history)
    print(f"Based on {result.periods_used} recorded price point(s) for '{product['name']}':")
    print(f"  Moving-average forecast:     {result.moving_average}")
    print(f"  Linear-regression forecast:  {result.linear_regression}")
    print("  (Analytical guidance only -- not a guaranteed future price.)")


def action_record_transaction():
    product_id = prompt("Product id", cast=int)
    product = repository.get_product(product_id)
    if product is None:
        print("Product not found.")
        return
    quantity = prompt("Quantity sold", cast=int)
    sale_price = prompt("Sale price", cast=float, default=str(product["retail_price"]))
    repository.add_transaction(product_id, quantity, sale_price)
    print("Transaction recorded.")


def action_seed():
    seed_module.seed()


ACTIONS = {
    "1": action_add_supplier,
    "2": action_add_product,
    "3": action_list_products,
    "4": action_search,
    "5": action_update_prices,
    "6": action_price_history,
    "7": action_variance_report,
    "8": action_forecast,
    "9": action_record_transaction,
    "10": action_seed,
}


def run():
    init_db(DEFAULT_DB_PATH)
    print("TINDA-PRICE initialized. Database:", DEFAULT_DB_PATH)
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye!")
            break
        action = ACTIONS.get(choice)
        if action is None:
            print("Invalid option.")
            continue
        try:
            action()
        except Exception as exc:  # keep the demo CLI resilient to bad input
            print(f"Error: {exc}")


if __name__ == "__main__":
    try:
        run()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
        sys.exit(0)
