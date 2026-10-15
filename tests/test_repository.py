import os
import tempfile
import unittest

from database import init_db
import repository
import search


class TestRepository(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_add_and_list_products(self):
        supplier_id = repository.add_supplier("Test Supplier", db_path=self.db_path)
        product_id = repository.add_product(
            "1234567890", "Test Item", "Snacks", supplier_id,
            10.0, 15.0, db_path=self.db_path,
        )
        products = repository.list_products(db_path=self.db_path)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["id"], product_id)
        self.assertEqual(products[0]["supplier_name"], "Test Supplier")

    def test_update_prices_logs_history(self):
        supplier_id = repository.add_supplier("Test Supplier", db_path=self.db_path)
        product_id = repository.add_product(
            "1234567890", "Test Item", "Snacks", supplier_id,
            10.0, 15.0, db_path=self.db_path,
        )
        repository.update_prices(product_id, supplier_cost=12.0, db_path=self.db_path)
        history = repository.get_price_history(product_id, db_path=self.db_path)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["supplier_cost"], 12.0)
        self.assertEqual(history[-1]["retail_price"], 15.0)

    def test_search_by_barcode_and_text(self):
        supplier_id = repository.add_supplier("Test Supplier", db_path=self.db_path)
        repository.add_product(
            "9999999999", "Bear Brand Milk", "Dairy", supplier_id,
            40.0, 48.0, db_path=self.db_path,
        )
        exact = search.search("9999999999", db_path=self.db_path)
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0]["name"], "Bear Brand Milk")

        text_match = search.search("milk", db_path=self.db_path)
        self.assertEqual(len(text_match), 1)

        no_match = search.search("nonexistent", db_path=self.db_path)
        self.assertEqual(no_match, [])


if __name__ == "__main__":
    unittest.main()
