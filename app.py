"""TINDA-PRICE web application.

A Flask front end over the same centralized-database, search-&-retrieval,
variance-flagging, and forecasting modules used by the system
architecture design. This is the "Rapid Retrieval Interface" / store
terminal from the Technology Architecture phase, now reachable from any
browser on the store's network instead of a terminal-only CLI.
"""
from datetime import date, datetime

from flask import Flask, render_template, request, redirect, url_for, flash

from database import DEFAULT_DB_PATH, init_db
import repository
import search as search_module
import real_data as real_data_module
import variance
import forecasting
import dashboard_metrics


def create_app():
    app = Flask(__name__)
    app.secret_key = "tinda-price-dev-secret"  # fine for a local/offline student prototype

    with app.app_context():
        init_db(DEFAULT_DB_PATH)

    @app.route("/")
    def dashboard():
        all_products = repository.list_products()
        categories = sorted({p["category"] for p in all_products if p["category"]})
        suppliers = repository.list_suppliers()

        category_filter = request.args.get("category", "").strip()
        supplier_filter = request.args.get("supplier_id", "").strip()
        products = all_products
        if category_filter:
            products = [p for p in products if p["category"] == category_filter]
        if supplier_filter:
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

        updates_by_date = dashboard_metrics.group_updates_by_date(repository.list_all_price_history())
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
    def search():
        query = request.args.get("q", "").strip()
        results = search_module.search(query) if query else []
        return render_template("search_results.html", query=query, results=results)

    @app.route("/suppliers/new", methods=["GET", "POST"])
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
    def product_detail(product_id):
        product = repository.get_product(product_id)
        if product is None:
            flash("Product not found.", "error")
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
    def update_price(product_id):
        cost_raw = request.form.get("supplier_cost", "").strip()
        price_raw = request.form.get("retail_price", "").strip()
        cost = float(cost_raw) if cost_raw else None
        price = float(price_raw) if price_raw else None
        if cost is None and price is None:
            flash("Enter a new cost or price to update.", "error")
        else:
            repository.update_prices(product_id, supplier_cost=cost, retail_price=price)
            flash("Price updated and logged to history.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    @app.route("/products/<int:product_id>/sell", methods=["POST"])
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
    def variance_report():
        products = repository.list_products()
        results = [variance.evaluate_product(p) for p in products]
        results.sort(key=lambda r: r.flagged, reverse=True)
        return render_template("variance_report.html", results=results)

    @app.route("/seed-real-data", methods=["POST"])
    def load_real_data():
        real_data_module.load()
        flash("Real Philippine market data loaded (World Bank RTFP, Metro Manila).", "success")
        return redirect(url_for("dashboard"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
