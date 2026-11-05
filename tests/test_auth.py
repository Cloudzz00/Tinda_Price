import os
import tempfile
import unittest

from database import init_db
import auth


class TestAuth(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_create_and_fetch_user(self):
        auth.create_user("alice", "hunter2", "admin", "Alice", db_path=self.db_path)
        user = auth.get_user_by_username("alice", db_path=self.db_path)
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "admin")
        self.assertEqual(user["display_name"], "Alice")

    def test_password_is_hashed_not_stored_in_plaintext(self):
        auth.create_user("bob", "hunter2", "store_owner", db_path=self.db_path)
        user = auth.get_user_by_username("bob", db_path=self.db_path)
        self.assertNotEqual(user["password_hash"], "hunter2")

    def test_verify_password_accepts_correct_and_rejects_wrong(self):
        auth.create_user("carol", "correct-horse", "supplier", db_path=self.db_path)
        user = auth.get_user_by_username("carol", db_path=self.db_path)
        self.assertTrue(auth.verify_password(user, "correct-horse"))
        self.assertFalse(auth.verify_password(user, "wrong-password"))

    def test_create_user_rejects_unknown_role(self):
        with self.assertRaises(ValueError):
            auth.create_user("dave", "pw", "superadmin", db_path=self.db_path)

    def test_set_user_supplier_links_account(self):
        from database import get_connection
        with get_connection(self.db_path) as conn:
            conn.execute("INSERT INTO suppliers (name) VALUES ('Erin Supply Co')")
            supplier_id = conn.execute(
                "SELECT id FROM suppliers WHERE name = 'Erin Supply Co'"
            ).fetchone()["id"]

        user_id = auth.create_user("erin", "pw", "supplier", db_path=self.db_path)
        auth.set_user_supplier(user_id, supplier_id, db_path=self.db_path)
        user = auth.get_user_by_id(user_id, db_path=self.db_path)
        self.assertEqual(user["supplier_id"], supplier_id)

    def test_list_users_includes_supplier_name(self):
        from database import get_connection
        with get_connection(self.db_path) as conn:
            conn.execute("INSERT INTO suppliers (name) VALUES ('Acme Co')")
            supplier_id = conn.execute("SELECT id FROM suppliers WHERE name = 'Acme Co'").fetchone()["id"]
        user_id = auth.create_user("frank", "pw", "supplier", supplier_id=supplier_id, db_path=self.db_path)
        users = auth.list_users(db_path=self.db_path)
        frank = next(u for u in users if u["id"] == user_id)
        self.assertEqual(frank["supplier_name"], "Acme Co")


if __name__ == "__main__":
    unittest.main()
