import os
import tempfile
import unittest

from database import init_db
import auth
import accounts
import real_data
import repository


class TestAccounts(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_creates_one_account_per_role(self):
        accounts.ensure_default_accounts(db_path=self.db_path)
        users = auth.list_users(db_path=self.db_path)
        roles = {u["role"] for u in users}
        self.assertEqual(roles, {"admin", "supplier", "store_owner"})
        self.assertEqual(len(users), 3)

    def test_idempotent(self):
        accounts.ensure_default_accounts(db_path=self.db_path)
        accounts.ensure_default_accounts(db_path=self.db_path)
        self.assertEqual(len(auth.list_users(db_path=self.db_path)), 3)

    def test_supplier_account_starts_unlinked(self):
        accounts.ensure_default_accounts(db_path=self.db_path)
        supplier_user = auth.get_user_by_username("supplier", db_path=self.db_path)
        self.assertIsNone(supplier_user["supplier_id"])

    def test_supplier_account_links_once_real_data_is_loaded(self):
        accounts.ensure_default_accounts(db_path=self.db_path)
        real_data.load(db_path=self.db_path)
        accounts.ensure_default_accounts(db_path=self.db_path)  # re-run links it

        supplier_user = auth.get_user_by_username("supplier", db_path=self.db_path)
        self.assertIsNotNone(supplier_user["supplier_id"])

        supplier = next(
            s for s in repository.list_suppliers(db_path=self.db_path)
            if s["name"] == real_data.SUPPLIER_NAME
        )
        self.assertEqual(supplier_user["supplier_id"], supplier["id"])


if __name__ == "__main__":
    unittest.main()
