# TINDA-PRICE

An Integrated Retail Price Intelligence and Predictive Analytics
Architecture for Dynamic Price Monitoring in Small Stores.

Submitted in partial fulfillment of the requirements in System
Integration and Architecture.

## What this is

A runnable Python prototype of the TINDA-PRICE system described in the
project's Enterprise Architecture (TOGAF ADM, with RAD for system build
and CRISP-DM for the analytics models). It implements the four modules
from the System Architecture Design slide:

| Module | File | Objective it satisfies |
|---|---|---|
| Centralized Database | `database.py`, `repository.py` | Single local SQLite repository for products, suppliers, supplier costs, retail prices, transactions, and price history — replacing notebooks/receipts/memory. |
| Search & Retrieval Interface | `search.py` | Text queries and barcode-scanner input (handled identically) for instant lookup of cost, price, and history. |
| Variance-Flagging Module | `variance.py` | Computes the % margin between supplier cost and retail price per product and flags items whose margin has dropped below a configurable minimum threshold, needing a price review. |
| Trend-Analysis Forecasting Module | `forecasting.py` | Projects short-term price movement from price history using a simple moving average and a linear-regression trend line. |

`main.py` is a menu-driven CLI that ties the modules together — a stand-in
for the "Rapid Retrieval Interface" / store terminal described in the
Technology Architecture phase. `seed.py` loads sample sari-sari-store
data (products, suppliers, a short price history) for a quick pilot
demo, matching the Opportunities & Migration phase's plan to encode
existing price data.

## Requirements

Python 3.9+. No third-party packages — everything uses the standard
library (`sqlite3`, `dataclasses`, `unittest`).

## Running it

```bash
cd tinda_price_app
python main.py
```

On first run it creates `tinda_price.db` in the project folder and
shows a menu. Option **10** loads sample data so you can immediately try
search, variance-flagging, and forecasting without typing in products by
hand.

Typical demo flow:

1. `10` — load sample data
2. `3` — list products, note a product id (e.g. the rice product)
3. `7` — run the variance-flagging report; the rice product should be
   flagged because its margin has been squeezed by rising supplier cost
4. `6` — view that product's price history
5. `8` — forecast its next price with the moving-average and
   linear-regression methods

## Running the tests

```bash
cd tinda_price_app
python -m unittest discover -v
```

Tests cover the variance-flagging math, both forecasting methods, and
the repository/search layer (against a temporary SQLite database, so
your real data is never touched).

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
