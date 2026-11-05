import unittest

import dashboard_metrics as dm
from variance import VarianceResult


def _result(name, variance_pct, threshold_pct=15.0):
    flagged = variance_pct < threshold_pct
    if variance_pct < 0:
        tier = "critical"
    elif flagged:
        tier = "review"
    else:
        tier = "healthy"
    return VarianceResult(
        product_id=1, name=name, supplier_cost=10.0, retail_price=10.0,
        variance_pct=variance_pct, threshold_pct=threshold_pct,
        flagged=flagged, risk_tier=tier,
    )


class TestDashboardMetrics(unittest.TestCase):
    def test_month_label(self):
        self.assertEqual(dm.month_label(2026, 11), "November 2026")

    def test_shift_month_wraps_year(self):
        self.assertEqual(dm.shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(dm.shift_month(2026, 1, -1), (2025, 12))

    def test_group_updates_by_date(self):
        rows = [
            {"recorded_at": "2026-11-05T10:00:00+00:00"},
            {"recorded_at": "2026-11-05T11:00:00+00:00"},
            {"recorded_at": "2026-11-01"},
        ]
        grouped = dm.group_updates_by_date(rows)
        self.assertEqual(len(grouped["2026-11-05"]), 2)
        self.assertEqual(len(grouped["2026-11-01"]), 1)

    def test_build_calendar_weeks_marks_in_month_and_counts(self):
        updates = {"2026-11-05": [{}, {}]}
        weeks = dm.build_calendar_weeks(2026, 11, updates)
        flat = [cell for week in weeks for cell in week]
        nov5 = next(c for c in flat if c["iso"] == "2026-11-05")
        self.assertTrue(nov5["in_month"])
        self.assertEqual(nov5["count"], 2)
        # Padding cells from the prior/next month are marked as such.
        self.assertTrue(any(not c["in_month"] for c in flat))

    def test_risk_tier_summary_counts_and_percentages(self):
        results = [_result("A", -5), _result("B", 8), _result("C", 20)]
        summary, total = dm.risk_tier_summary(results)
        self.assertEqual(total, 3)
        by_tier = {s["tier"]: s for s in summary}
        self.assertEqual(by_tier["critical"]["count"], 1)
        self.assertEqual(by_tier["review"]["count"], 1)
        self.assertEqual(by_tier["healthy"]["count"], 1)
        self.assertAlmostEqual(by_tier["healthy"]["pct"], 33.3, places=1)

    def test_risk_tier_summary_empty(self):
        summary, total = dm.risk_tier_summary([])
        self.assertEqual(total, 0)
        self.assertTrue(all(s["pct"] == 0.0 for s in summary))

    def test_donut_gradient_has_a_stop_per_nonzero_tier(self):
        results = [_result("A", -5), _result("B", 20)]
        summary, _ = dm.risk_tier_summary(results)
        gradient = dm.donut_gradient(summary)
        self.assertIn("%", gradient)
        # Only 2 of the 3 tiers are present (healthy, critical) -- review is empty.
        self.assertEqual(gradient.count(","), 1)

    def test_bar_chart_data_scales_within_bounds(self):
        results = [_result("A", -5), _result("B", 8), _result("C", 90)]
        bars = dm.bar_chart_data(results)
        self.assertEqual(len(bars), 3)
        for bar in bars:
            self.assertGreaterEqual(bar["height_pct"], 2)
            self.assertLessEqual(bar["height_pct"], 100)


if __name__ == "__main__":
    unittest.main()
