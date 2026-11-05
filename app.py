"""TINDA-PRICE web application.

A Flask front end over the same centralized-database, search-&-retrieval,
variance-flagging, and forecasting modules used by the system
architecture design. This is the "Rapid Retrieval Interface" / store
terminal from the Technology Architecture phase, now reachable from any
browser on the store's network instead of a terminal-only CLI.

Access is role-based (see auth.py): an admin manages suppliers,
products, user accounts and variance thresholds; a supplier can only
update the supplier cost of their own products; a store owner sets
retail price, records sales, and reads the dashboard/reports/forecasts.
"""
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, session, g

from database import DEFAULT_DB_PATH, init_db
import repository
import search as search_module
import real_data as real_data_module
import variance
import forecasting
import dashboard_metrics
import auth
import accounts


def _scope_products_for_user(products, user):
    """A supplier only ever sees the products tied to their own supplier
    record; admin and store_owner see everything."""
    if user["role"] == "supplier":
        return [p for p in products if p["supplier_id"] == user["supplier_id"]]
    return products


def create_app():
    app = Flask(__name__)
    app.secret_key = "tinda-price-dev-secret"  # fine for a local/offline student prototype
    app.permanent_session_lifetime = timedelta(days=30)

    with app.app_context():
        init_db(DEFAULT_DB_PATH)
        accounts.ensure_default_accounts(DEFAULT_DB_PATH)

    @app.before_request
    def _load_user():
        auth.load_logged_in_user()
        if g.user is None and request.endpoint not in ("login", "static"):
            return redirect(url_for("login", next=request.path))

    @app.context_processor
    def _inject_user():
        return {"current_user": g.get("user"), "role_labels": auth.ROLE_LABELS}

    # ---- Auth ---------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = auth.get_user_by_username(username)
            if user is None or not auth.verify_password(user, password):
                flash("Invalid username or password.", "error")
            else:
                session.clear()
                session.permanent = bool(request.form.get("remember"))
                session["user_id"] = user["id"]
                flash(f"Welcome, {user['display_name'] or user['username']}!", "success")
                return redirect(request.form.get("next") or url_for("dashboard"))
        return render_template("login.html", next=request.args.get("next", ""))

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Logged out.", "success")
        return redirect(url_for("login"))

    # ---- Dashboard ------------------------------------------------------

    @app.route("/")
    @auth.login_required
    def dashboard():
        all_products = _scope_products_for_user(repository.list_products(), g.user)
        categories = sorted({p["category"] for p in all_products if p["category"]})
        suppliers = repository.list_suppliers()

        category_filter = request.args.get("category", "").strip()
        supplier_filter = request.args.get("supplier_id", "").strip()
        products = all_products
        if category_filter:
            products = [p for p in products if p["category"] == category_filter]
        if supplier_filter and g.user["role"] != "supplier":
            products = [p for p in products if str(p["supplier_id"]) == supplier_filter]

        results = [variance.evaluate_product(p) for p in products]
        flagged = [r for r in results if r.flagged]
        avg_margin = round(sum(r.variance_pct for r in results) / len(results), 1) if results else 0.0
        needs_review = sorted(flagged, key=lambda r: r.variance_pct)[:5]
        risk_summary, risk_total = dashboard_metrics.risk_tier_summary(results)

        today = date.today()
        try:
            cal_year = int(request.args.get("year", today.year))
            cal_month = int(request.args.get("month", today.month))
        except ValueError:
            cal_year, cal_month = today.year, today.month
        try:
            selected_date = date.fromisoformat(request.args.get("date", today.isoformat())).isoformat()
        except ValueError:
            selected_date = today.isoformat()
        selected_date_label = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%b %d, %Y")

        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

        history_rows = repository.list_all_price_history()
        if g.user["role"] == "supplier":
            history_rows = [r for r in history_rows if r["product_supplier_id"] == g.user["supplier_id"]]
        updates_by_date = dashboard_metrics.group_updates_by_date(history_rows)
        calendar_weeks = dashboard_metrics.build_calendar_weeks(cal_year, cal_month, updates_by_date)
        prev_year, prev_month = dashboard_metrics.shift_month(cal_year, cal_month, -1)
        next_year, next_month = dashboard_metrics.shift_month(cal_year, cal_month, 1)

        return render_template(
            "dashboard.html",
            products=products,
            all_products=all_products,
            total_products=len(products),
            flagged_count=len(flagged),
            healthy_count=len(products) - len(flagged),
            avg_margin=avg_margin,
            suppliers=suppliers,
            categories=categories,
            category_filter=category_filter,
            supplier_filter=supplier_filter,
            needs_review=needs_review,
            risk_summary=risk_summary,
            risk_total=risk_total,
            donut_gradient=dashboard_metrics.donut_gradient(risk_summary),
            bars=dashboard_metrics.bar_chart_data(results),
            calendar_weeks=calendar_weeks,
            month_label=dashboard_metrics.month_label(cal_year, cal_month),
            cal_year=cal_year,
            cal_month=cal_month,
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month,
            selected_date=selected_date,
            selected_date_label=selected_date_label,
            selected_entries=updates_by_date.get(selected_date, []),
            today=today.isoformat(),
            greeting=greeting,
            today_label=today.strftime("%B %d, %Y"),
        )

    @app.route("/search")
    @auth.login_required
    def search():
        query = request.args.get("q", "").strip()
        results = search_module.search(query) if query else []
        results = _scope_products_for_user(results, g.user)
        return render_template("search_results.html", query=query, results=results)

    # ---- Suppliers & products (admin manages the catalog) ---------------

    @app.route("/suppliers/new", methods=["GET", "POST"])
    @auth.roles_required("admin")
    def new_supplier():
        if request.method == "POST":
            name = request.form["name"].strip()
            contact = request.form.get("contact", "").strip()
            if not name:
                flash("Supplier name is required.", "error")
            else:
                repository.add_supplier(name, contact)
                flash(f"Supplier '{name}' added.", "success")
                return redirect(url_for("dashboard"))
        return render_template("new_supplier.html")

    @app.route("/products/new", methods=["GET", "POST"])
    @auth.roles_required("admin")
    def new_product():
        suppliers = repository.list_suppliers()
        if request.method == "POST":
            if not suppliers:
                flash("Add a supplier before adding a product.", "error")
                return redirect(url_for("new_supplier"))
            try:
                product_id = repository.add_product(
                    barcode=request.form.get("barcode", "").strip() or None,
                    name=request.form["name"].strip(),
                    category=request.form.get("category", "").strip(),
                    supplier_id=int(request.form["supplier_id"]),
                    supplier_cost=float(request.form["supplier_cost"]),
                    retail_price=float(request.form["retail_price"]),
                    variance_threshold_pct=float(request.form.get("variance_threshold_pct") or 15.0),
                )
            except (KeyError, ValueError) as exc:
                flash(f"Could not add product: {exc}", "error")
                return render_template("new_product.html", suppliers=suppliers)
            flash("Product added.", "success")
            return redirect(url_for("product_detail", product_id=product_id))
        return render_template("new_product.html", suppliers=suppliers)

    @app.route("/products/<int:product_id>")
    @auth.login_required
    def product_detail(product_id):
        product = repository.get_product(product_id)
        if product is None:
            flash("Product not found.", "error")
            return redirect(url_for("dashboard"))
        if g.user["role"] == "supplier" and product["supplier_id"] != g.user["supplier_id"]:
            flash("You don't have access to that product.", "error")
            return redirect(url_for("dashboard"))
        history = repository.get_price_history(product_id)
        transactions = repository.list_transactions(product_id)
        variance_result = variance.evaluate_product(product)
        forecast_result = (
            forecasting.forecast_for_product(history) if len(history) >= 2 else None
        )
        return render_template(
            "product_detail.html",
            product=product,
            history=history,
            transactions=transactions,
            variance_result=variance_result,
            forecast_result=forecast_result,
        )

    @app.route("/products/<int:product_id>/update-price", methods=["POST"])
    @auth.login_required
    def update_price(product_id):
        product = repository.get_product(product_id)
        if product is None:
            flash("Product not found.", "error")
            return redirect(url_for("dashboard"))

        role = g.user["role"]
        if role == "supplier" and product["supplier_id"] != g.user["supplier_id"]:
            flash("You can only update your own products.", "error")
            return redirect(url_for("product_detail", product_id=product_id))
        if role not in ("admin", "supplier", "store_owner"):
            flash("You don't have permission to do that.", "error")
            return redirect(url_for("product_detail", product_id=product_id))

        cost_raw = request.form.get("supplier_cost", "").strip()
        price_raw = request.form.get("retail_price", "").strip()
        cost = float(cost_raw) if cost_raw else None
        price = float(price_raw) if price_raw else None

        # Enforce the role split server-side even if the form is tampered with:
        # suppliers set cost only, store owners set retail price only.
        if role == "supplier":
            price = None
        elif role == "store_owner":
            cost = None

        if cost is None and price is None:
            flash("Enter a new value to update.", "error")
        else:
            repository.update_prices(product_id, supplier_cost=cost, retail_price=price)
            flash("Price updated and logged to history.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    @app.route("/products/<int:product_id>/update-threshold", methods=["POST"])
    @auth.roles_required("admin")
    def update_threshold(product_id):
        try:
            threshold = float(request.form["variance_threshold_pct"])
        except (KeyError, ValueError):
            flash("Enter a valid threshold percentage.", "error")
            return redirect(url_for("product_detail", product_id=product_id))
        repository.update_threshold(product_id, threshold)
        flash("Variance threshold updated.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    @app.route("/products/<int:product_id>/sell", methods=["POST"])
    @auth.roles_required("admin", "store_owner")
    def record_sale(product_id):
        try:
            quantity = int(request.form["quantity"])
            sale_price = float(request.form["sale_price"])
        except (KeyError, ValueError):
            flash("Enter a valid quantity and sale price.", "error")
            return redirect(url_for("product_detail", product_id=product_id))
        repository.add_transaction(product_id, quantity, sale_price)
        flash("Sale recorded.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    @app.route("/variance")
    @auth.login_required
    def variance_report():
        products = _scope_products_for_user(repository.list_products(), g.user)
        results = [variance.evaluate_product(p) for p in products]
        results.sort(key=lambda r: r.flagged, reverse=True)
        return render_template("variance_report.html", results=results)

    @app.route("/seed-real-data", methods=["POST"])
    @auth.roles_required("admin")
    def load_real_data():
        real_data_module.load()
        accounts.ensure_default_accounts()
        flash("Real Philippine market data loaded (World Bank RTFP, Metro Manila).", "success")
        return redirect(url_for("dashboard"))

    # ---- User management (admin only) ------------------------------------

    @app.route("/users")
    @auth.roles_required("admin")
    def list_users():
        return render_template(
            "users.html",
            users=auth.list_users(),
            suppliers=repository.list_suppliers(),
            roles=auth.ROLES,
        )

    @app.route("/users/new", methods=["POST"])
    @auth.roles_required("admin")
    def create_user():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        display_name = request.form.get("display_name", "").strip()
        supplier_id_raw = request.form.get("supplier_id", "").strip()
        supplier_id = int(supplier_id_raw) if supplier_id_raw else None

        if not username or not password or role not in auth.ROLES:
            flash("Fill in username, password, and a valid role.", "error")
        elif auth.get_user_by_username(username) is not None:
            flash(f"Username '{username}' is already taken.", "error")
        else:
            auth.create_user(username, password, role, display_name,
                              supplier_id=supplier_id if role == "supplier" else None)
            flash(f"User '{username}' created.", "success")
        return redirect(url_for("list_users"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
