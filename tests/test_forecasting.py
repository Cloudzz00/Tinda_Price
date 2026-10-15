import unittest

from forecasting import (
    moving_average_forecast,
    linear_regression_forecast,
    forecast_prices,
)


class TestForecasting(unittest.TestCase):
    def test_moving_average_empty(self):
        self.assertIsNone(moving_average_forecast([]))

    def test_moving_average_basic(self):
        self.assertEqual(moving_average_forecast([10, 20, 30], window=3), 20.0)

    def test_moving_average_window_larger_than_series(self):
        self.assertEqual(moving_average_forecast([10, 20], window=5), 15.0)

    def test_linear_regression_requires_two_points(self):
        self.assertIsNone(linear_regression_forecast([]))
        self.assertIsNone(linear_regression_forecast([10]))

    def test_linear_regression_upward_trend(self):
        # prices rise by 2 each period -> next should continue the trend
        forecast = linear_regression_forecast([48, 50, 52, 54])
        self.assertAlmostEqual(forecast, 56.0, places=1)

    def test_linear_regression_flat_series(self):
        forecast = linear_regression_forecast([50, 50, 50])
        self.assertAlmostEqual(forecast, 50.0, places=1)

    def test_forecast_prices_bundles_both_methods(self):
        result = forecast_prices([48, 50, 52, 54], window=2)
        self.assertEqual(result.periods_used, 4)
        self.assertEqual(result.moving_average, 53.0)
        self.assertAlmostEqual(result.linear_regression, 56.0, places=1)


if __name__ == "__main__":
    unittest.main()
