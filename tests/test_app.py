import os
import unittest

from database import DEFAULT_DB_PATH
import repository
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

    def test_dashboard_loads_empty(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TINDA-PRICE", response.data)

    def test_add_supplier_and_product_flow(self):
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
        response = self.client.get("/search", query_string={"q": "nonexistent"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No matching products", response.data)

    def test_variance_report_route(self):
        response = self.client.get("/variance")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
