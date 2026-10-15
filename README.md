# TINDA-PRICE

An Integrated Retail Price Intelligence and Predictive Analytics
Architecture for Dynamic Price Monitoring in Small Stores.

Submitted in partial fulfillment of the requirements in System
Integration and Architecture.

## What this is

A runnable, web-based Python prototype of the TINDA-PRICE system
described in the project's Enterprise Architecture (TOGAF ADM, with RAD
for the system build and CRISP-DM for the analytics models). It
implements the four modules from the System Architecture Design slide,
served through a Flask web application instead of a terminal-only tool.

| Module | File | Objective it satisfies |
|---|---|---|
| Centralized Database | `database.py`, `repository.py` | Single local SQLite repository for products, suppliers, supplier costs, retail prices, transactions, and price history — replacing notebooks/receipts/memory. |
| Search & Retrieval Interface | `search.py` | Text queries and barcode-scanner input (handled identically) for instant lookup of cost, price, and history, exposed via the search box on every page. |
| Variance-Flagging Module | `variance.py` | Computes the % margin between supplier cost and retail price per product and flags items whose margin has dropped below a configurable minimum threshold, needing a price review. |
| Trend-Analysis Forecasting Module | `forecasting.py` | Projects short-term price movement from price history using a simple moving average and a linear-regression trend line. |
| Web interface | `app.py`, `templates/`, `static/` | The "Rapid Retrieval Interface" / store terminal from the Technology Architecture phase — a browser-based dashboard, product pages, and variance report reachable from any device on the store's network. |

`seed.py` loads sample sari-sari-store data (products, suppliers, a short
price history) for a quick pilot demo, matching the Opportunities &
Migration phase's plan to encode existing price data — triggered from
the dashboard's "Load sample data" button when the database is empty.

## Requirements

Python 3.9+ and Flask:

```bash
pip install -r requirements.txt
```

## Running the web app

```bash
cd tinda_price_app   # or wherever this project lives
python app.py
```

Then open **http://localhost:5000** in a browser. On first run it
creates `tinda_price.db` in the project folder.

Typical demo flow:

1. Dashboard — click **Load sample data** to seed products and suppliers
2. Use the search box (top bar) to look up a product by name, category,
   or barcode
3. Open a product page to view its current price, price history, and
   short-term forecast (moving average + linear regression)
4. **Variance Report** — see which products have a margin below their
   configured threshold and need a price review
5. From a product page, update its supplier cost/retail price (logged
   to history automatically) or record a sale

## Running the tests

```bash
python -m unittest discover -v
```

Tests cover the variance-flagging math, both forecasting methods, the
repository/search layer (against a temporary SQLite database), and the
Flask routes (dashboard, add supplier/product, search, variance report).

## Design notes

- **Variance threshold.** Each product stores a `variance_threshold_pct`
  (default 15%), the minimum acceptable margin. A product is flagged
  when `((retail_price - supplier_cost) / supplier_cost) * 100` falls
  below that threshold — i.e. a supplier cost increase has eroded the
  margin faster than the shelf price was updated.
- **Price history** is appended automatically every time
  `repository.update_prices()` changes a product's cost or price, so the
  forecasting module always has a real time series to work from instead
  of a separate manual logging step.
- **Forecasts are analytical guidance, not guarantees** — consistent
  with the project's stated scope (moving averages / linear regression
  on historical data, following Banatao et al., 2024).
- **Why Flask.** The business logic (`database.py`, `repository.py`,
  `search.py`, `variance.py`, `forecasting.py`) has no dependency on how
  it's presented, so the same modules back the web UI today and could
  back a different front end later without changes.
