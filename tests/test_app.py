import os
import unittest

from database import DEFAULT_DB_PATH
import repository
import auth
from app import create_app


class TestWebApp(unittest.TestCase):
    """Exercises the Flask routes against the real default database file,
    since repository's functions bind their db_path default at import
    time (monkeypatching the module attribute afterwards would not
    reach them). The file is removed before and after each test so
    runs start clean and don't leave data behind."""

    def setUp(self):
        if os.path.exists(DEFAULT_DB_PATH):
            os.remove(DEFAULT_DB_PATH)
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(DEFAULT_DB_PATH):
            os.remove(DEFAULT_DB_PATH)

    def _login(self, username, password):
        return self.client.post(
            "/login", data={"username": username, "password": password}, follow_redirects=True
        )

    def _add_product_as_admin(self):
        self._login("admin", "admin123")
        self.client.post("/suppliers/new", data={"name": "Test Supplier", "contact": "0917"})
        supplier = repository.list_suppliers()[0]
        self.client.post(
            "/products/new",
            data={
                "barcode": "1234567890",
                "name": "Test Item",
                "category": "Snacks",
                "supplier_id": str(supplier["id"]),
                "supplier_cost": "10.0",
                "retail_price": "15.0",
                "variance_threshold_pct": "15",
            },
        )
        self.client.post("/logout")
        return repository.list_products()[0], supplier

    # ---- Auth -------------------------------------------------------------

    def test_dashboard_requires_login(self):
        response = self.client.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sign in to your account", response.data)

    def test_login_with_demo_admin_account(self):
        response = self._login("admin", "admin123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome", response.data)

    def test_login_rejects_bad_password(self):
        response = self._login("admin", "wrong-password")
        self.assertIn(b"Invalid username or password", response.data)

    def test_logout_clears_session(self):
        self._login("admin", "admin123")
        self.client.post("/logout")
        response = self.client.get("/", follow_redirects=True)
        self.assertIn(b"Sign in to your account", response.data)

    # ---- Basic routes (as admin) ------------------------------------------

    def test_dashboard_loads_empty(self):
        self._login("admin", "admin123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TINDA-PRICE", response.data)

    def test_add_supplier_and_product_flow(self):
        self._login("admin", "admin123")
        self.client.post("/suppliers/new", data={"name": "Test Supplier", "contact": "0917"})
        suppliers = repository.list_suppliers()
        self.assertEqual(len(suppliers), 1)

        response = self.client.post(
            "/products/new",
            data={
                "barcode": "1234567890",
                "name": "Test Item",
                "category": "Snacks",
                "supplier_id": str(suppliers[0]["id"]),
                "supplier_cost": "10.0",
                "retail_price": "15.0",
                "variance_threshold_pct": "15",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        products = repository.list_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Test Item")

    def test_search_route(self):
        self._login("admin", "admin123")
        response = self.client.get("/search", query_string={"q": "nonexistent"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No matching products", response.data)

    def test_variance_report_route(self):
        self._login("admin", "admin123")
        response = self.client.get("/variance")
        self.assertEqual(response.status_code, 200)

    # ---- Role boundaries ----------------------------------------------------

    def test_store_owner_cannot_add_product(self):
        self._login("owner", "owner123")
        response = self.client.get("/products/new", follow_redirects=True)
        self.assertIn(b"permission to do that", response.data)
        self.assertEqual(len(repository.list_products()), 0)

    def test_supplier_cannot_add_supplier(self):
        self._login("supplier", "supplier123")
        response = self.client.post(
            "/suppliers/new", data={"name": "Sneaky Supplier"}, follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(repository.list_suppliers()), 0)

    def test_supplier_can_only_update_cost_not_price(self):
        product, supplier = self._add_product_as_admin()
        supplier_user = auth.get_user_by_username("supplier")
        auth.set_user_supplier(supplier_user["id"], supplier["id"])

        self._login("supplier", "supplier123")
        self.client.post(
            f"/products/{product['id']}/update-price",
            data={"supplier_cost": "12.0", "retail_price": "99.0"},
        )
        updated = repository.get_product(product["id"])
        self.assertEqual(updated["supplier_cost"], 12.0)
        self.assertEqual(updated["retail_price"], 15.0)  # unchanged -- suppliers can't touch it

    def test_store_owner_can_only_update_price_not_cost(self):
        product, _ = self._add_product_as_admin()
        self._login("owner", "owner123")
        self.client.post(
            f"/products/{product['id']}/update-price",
            data={"supplier_cost": "999.0", "retail_price": "20.0"},
        )
        updated = repository.get_product(product["id"])
        self.assertEqual(updated["retail_price"], 20.0)
        self.assertEqual(updated["supplier_cost"], 10.0)  # unchanged -- store owners can't touch it

    def test_supplier_cannot_update_someone_elses_product(self):
        product, _ = self._add_product_as_admin()
        # "supplier" demo account has no supplier_id linked yet in this test.
        self._login("supplier", "supplier123")
        response = self.client.post(
            f"/products/{product['id']}/update-price",
            data={"supplier_cost": "1.0"},
            follow_redirects=True,
        )
        self.assertIn(b"only update your own products", response.data)
        updated = repository.get_product(product["id"])
        self.assertEqual(updated["supplier_cost"], 10.0)

    def test_only_admin_and_store_owner_can_record_sale(self):
        product, supplier = self._add_product_as_admin()
        supplier_user = auth.get_user_by_username("supplier")
        auth.set_user_supplier(supplier_user["id"], supplier["id"])

        self._login("supplier", "supplier123")
        self.client.post(f"/products/{product['id']}/sell", data={"quantity": "1", "sale_price": "15.0"})
        self.assertEqual(len(repository.list_transactions(product["id"])), 0)

        self.client.post("/logout")
        self._login("owner", "owner123")
        self.client.post(f"/products/{product['id']}/sell", data={"quantity": "1", "sale_price": "15.0"})
        self.assertEqual(len(repository.list_transactions(product["id"])), 1)

    def test_only_admin_can_reach_users_page(self):
        self._login("owner", "owner123")
        response = self.client.get("/users", follow_redirects=True)
        self.assertNotIn(b"Add User", response.data)

        self.client.post("/logout")
        self._login("admin", "admin123")
        response = self.client.get("/users")
        self.assertIn(b"Add User", response.data)

    # ---- Profile --------------------------------------------------------

    def test_update_display_name(self):
        self._login("owner", "owner123")
        response = self.client.post(
            "/profile", data={"action": "update_profile", "display_name": "Owner Renamed"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        user = auth.get_user_by_username("owner")
        self.assertEqual(user["display_name"], "Owner Renamed")

    def test_change_password_requires_correct_current_password(self):
        self._login("owner", "owner123")
        response = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "wrong-password",
                "new_password": "newpass1",
                "confirm_password": "newpass1",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Current password is incorrect", response.data)

    def test_change_password_enforces_complexity(self):
        self._login("owner", "owner123")
        response = self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "owner123",
                "new_password": "short",
                "confirm_password": "short",
            },
            follow_redirects=True,
        )
        self.assertIn(b"at least 8 characters", response.data)

    def test_change_password_succeeds_and_can_log_in_with_new_password(self):
        self._login("owner", "owner123")
        self.client.post(
            "/profile",
            data={
                "action": "change_password",
                "current_password": "owner123",
                "new_password": "newpass1",
                "confirm_password": "newpass1",
            },
        )
        self.client.post("/logout")
        response = self._login("owner", "newpass1")
        self.assertIn(b"Welcome", response.data)

    # ---- Notifications bell ------------------------------------------------

    def test_notification_bell_shows_flagged_count(self):
        product, _ = self._add_product_as_admin()
        # Cost 10, price 15 -> 50% margin, well above the 15% threshold: healthy.
        self._login("admin", "admin123")
        response = self.client.get("/")
        self.assertNotIn(b"bell-badge", response.data)

        # Push the margin under the threshold so it gets flagged.
        self.client.post(f"/products/{product['id']}/update-price", data={"retail_price": "10.5"})
        response = self.client.get("/")
        self.assertIn(b"bell-badge", response.data)

    # ---- Audit trail (who made the change) ---------------------------------

    def test_price_update_records_who_made_it(self):
        product, _ = self._add_product_as_admin()
        self._login("owner", "owner123")
        self.client.post(f"/products/{product['id']}/update-price", data={"retail_price": "20.0"})
        history = repository.get_price_history(product["id"])
        self.assertEqual(history[-1]["updated_by_name"], "Store Owner")

    def test_sale_records_who_recorded_it(self):
        product, _ = self._add_product_as_admin()
        self._login("admin", "admin123")
        self.client.post(f"/products/{product['id']}/sell", data={"quantity": "1", "sale_price": "15.0"})
        transactions = repository.list_transactions(product["id"])
        self.assertEqual(transactions[0]["recorded_by_name"], "System Admin")


if __name__ == "__main__":
    unittest.main()
