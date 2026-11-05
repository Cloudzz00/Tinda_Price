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
| Web interface | `app.py`, `templates/`, `static/`, `dashboard_metrics.py` | The "Rapid Retrieval Interface" / store terminal from the Technology Architecture phase — sidebar-navigated pages (dashboard, variance report, per-product pages), a notification bell tied to flagged products, and a self-service profile page, reachable from any device on the store's network. |
| Role-Based Access Control | `auth.py`, `accounts.py` | Session-based login with three roles (admin, supplier, store owner), each scoped to what they're actually responsible for — see [Role-based access](#role-based-access) below. |

`real_data.py` loads the system's only data source: **actual Philippine
retail prices**, not synthetic numbers — see
[Real Philippine market data](#real-philippine-market-data) below. It's
triggered from the dashboard's "Load real market data" button, which
only appears while the database is empty (the load is also idempotent,
so it's safe either way).

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
creates `tinda_price.db` in the project folder and three demo accounts
(see [Role-based access](#role-based-access)) — you'll land on a login
page first.

Typical demo flow:

1. Log in as **admin** (`admin` / `admin123`), then click **Load real
   market data** to load real Philippine retail prices (see below)
2. The dashboard's stat cards, "Needs Price Review" list, price-update
   calendar, margin chart, and risk donut all update to reflect it;
   use the category/supplier filters to narrow any of them
3. Use the search box (top bar) to look up a product by name or category
4. Open a product page to view its current price, price history, and
   short-term forecast (moving average + linear regression)
5. **Variance Report** — see every product's margin against its
   configured threshold
6. Log out and back in as **supplier** (`supplier` / `supplier123`) to
   see cost-only editing, then as **owner** (`owner` / `owner123`) to
   see price-only editing and sale recording — demonstrating the
   workflow the variance-flagging module is built around (see below)
7. The bell icon in the top bar shows how many products need a price
   review (scoped to what that role can see) and links straight to
   them; **My Profile** (sidebar) lets any logged-in user rename
   themselves and change their password
8. Every price update and sale now records who made it — visible as
   "Updated by" / "Recorded by" on each product's history and sales
   tables

## Role-based access

Three roles, matching how a real store/supplier relationship works:

| Role | Can do | Can't do |
|---|---|---|
| **Admin** | Manage suppliers, products, user accounts, and variance thresholds; full read access to everything | — |
| **Supplier** | Update the **supplier cost** of the products tied to their own supplier record; view their own products, history, and forecasts | Touch retail price; see or edit another supplier's products; add suppliers/products/users; record sales |
| **Store Owner** | Set **retail price**; record sales; view the full dashboard, reports, and forecasts | Touch supplier cost; manage suppliers/products/users |

This isn't just an access-control checkbox — it mirrors the actual
workflow TINDA-PRICE's variance-flagging module exists for: a supplier
reports a cost change (updates their product's cost), the system
recomputes the margin and flags it if needed, and the store owner
reviews the **Needs Price Review** list and adjusts the retail price.
Every permission boundary is enforced server-side in `app.py`
(`auth.login_required` / `auth.roles_required`), not just hidden in the
UI — a role-correct form field is also defense in depth, not the only
line of defense.

Demo accounts (seeded automatically, see `accounts.py`):

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin |
| `owner` | `owner123` | Store Owner |
| `supplier` | `supplier123` | Supplier (auto-linked to the real-data supplier once it's loaded) |

An admin can create more accounts from the **Users** page.

## Real Philippine market data

The dashboard's **Load real market data** button loads the system's
product catalog from actual published Philippine retail prices instead
of made-up numbers:

- **Source:** [World Bank Real-Time Food Price Monitoring (Philippines)](https://microdata.worldbank.org/catalog/6172),
  dataset version 2025-11-24.
- **Scope:** Metro Manila market, monthly retail price per kilogram (or
  per piece for eggs) for 9 items — rice, eggs, garlic, red onions,
  tomatoes, cabbage, carrots, sweet potatoes, and mung beans — from
  November 2024 through November 2025.
- **File:** `data/ph_food_prices_metro_manila.csv` (extracted from the
  World Bank's full national CSV, which is too large to ship in the
  repo). Columns: `price_date, item, retail_price_php`.
- **Supplier cost caveat:** the dataset publishes only the modeled
  retail (selling) price — not a per-store supplier/wholesale cost,
  since that figure genuinely only exists in each store's own purchase
  records (the exact gap TINDA-PRICE exists to close). `real_data.py`
  locks each product's supplier cost at 15% below its earliest price in
  the series (Nov 2024) and leaves it unchanged, standing in for a store
  that priced at a healthy margin a year ago and hasn't revisited its
  cost basis since. The retail-price trend itself is the real published
  series, unmodified — so the forecasting module's moving-average and
  linear-regression projections are computed on genuine market data
  (e.g. rice's well-documented 2025 price decline), and the
  variance-flagging module surfaces real margin drift rather than a
  scripted example.

## Running the tests

```bash
python -m unittest discover -v
```

Tests cover the variance-flagging math, both forecasting methods, the
repository/search layer (against a temporary SQLite database), password
hashing and demo-account seeding, and the Flask routes — including the
role boundaries themselves (a supplier can't touch retail price or
another supplier's products, a store owner can't manage the catalog,
only an admin reaches the Users page, and so on).

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
- **Auth is scoped to a classroom demo.** Passwords are hashed
  (`werkzeug.security`) and permissions are enforced server-side. Any
  logged-in user can rename themselves and change their own password
  from **My Profile**, but the demo credentials are intentionally
  public (see the table above), the session secret key is a hardcoded
  string, and there's no email-based "forgot password" recovery or
  account-lockout flow. Treat it as a correct access-control model, not
  a production auth system.
- **Accountability.** `price_history.updated_by` and
  `transactions.recorded_by` record which user made each change
  (nullable, so the imported real-market-data rows correctly show no
  one — nobody at the store entered those). `database.py` migrates
  these columns into any database file created before this existed, so
  an older `tinda_price.db` keeps working.
