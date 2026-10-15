import unittest

from variance import compute_variance_pct, evaluate_product


class TestVariance(unittest.TestCase):
    def test_compute_variance_pct_positive_margin(self):
        self.assertAlmostEqual(compute_variance_pct(50.0, 65.0), 30.0)

    def test_compute_variance_pct_zero_margin(self):
        self.assertAlmostEqual(compute_variance_pct(50.0, 50.0), 0.0)

    def test_compute_variance_pct_rejects_zero_cost(self):
        with self.assertRaises(ValueError):
            compute_variance_pct(0.0, 10.0)

    def test_evaluate_product_flags_low_margin(self):
        product = {
            "id": 1,
            "name": "Rice",
            "supplier_cost": 48.0,
            "retail_price": 50.0,
            "variance_threshold_pct": 15.0,
        }
        result = evaluate_product(product)
        self.assertTrue(result.flagged)
        self.assertAlmostEqual(result.variance_pct, 4.17, places=2)

    def test_evaluate_product_does_not_flag_healthy_margin(self):
        product = {
            "id": 2,
            "name": "Coke",
            "supplier_cost": 50.0,
            "retail_price": 65.0,
            "variance_threshold_pct": 15.0,
        }
        result = evaluate_product(product)
        self.assertFalse(result.flagged)


if __name__ == "__main__":
    unittest.main()
