import os
import tempfile
import unittest

from database import init_db
import repository
import real_data


class TestRealData(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_load_creates_products_with_history(self):
        real_data.load(db_path=self.db_path)
        products = repository.list_products(db_path=self.db_path)
        self.assertEqual(len(products), len(real_data.ITEM_LABELS))

        rice = next(p for p in products if "Rice" in p["name"])
        history = repository.get_price_history(rice["id"], db_path=self.db_path)
        self.assertEqual(len(history), 12)
        # Real series is a published downward price trend for this window.
        self.assertGreater(history[0]["retail_price"], history[-1]["retail_price"])
        # Supplier cost is locked at the earliest observed price.
        self.assertTrue(all(h["supplier_cost"] == history[0]["supplier_cost"] for h in history))

    def test_load_is_idempotent(self):
        real_data.load(db_path=self.db_path)
        real_data.load(db_path=self.db_path)
        products = repository.list_products(db_path=self.db_path)
        self.assertEqual(len(products), len(real_data.ITEM_LABELS))


if __name__ == "__main__":
    unittest.main()
