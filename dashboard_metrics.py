"""View-model helpers for the dashboard page: the price-update calendar,
the margin-by-product bar chart, and the price-health donut chart. Kept
separate from app.py so the route handlers stay thin, and separate from
variance.py/repository.py since this is presentation shaping, not
business logic.
"""
import calendar
from datetime import date

_CALENDAR = calendar.Calendar(firstweekday=6)  # weeks start on Sunday, like the UI

RISK_TIER_LABELS = {
    "healthy": "Healthy Margin",
    "review": "Needs Review",
    "critical": "Selling at a Loss",
}
RISK_TIER_ORDER = ["healthy", "review", "critical"]


def month_label(year, month):
    return date(year, month, 1).strftime("%B %Y")


def shift_month(year, month, delta):
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def group_updates_by_date(history_rows):
    """history_rows: rows from repository.list_all_price_history().
    Returns {iso_date_str: [row, ...]}."""
    grouped = {}
    for row in history_rows:
        day = row["recorded_at"][:10]
        grouped.setdefault(day, []).append(row)
    return grouped


def build_calendar_weeks(year, month, updates_by_date):
    """Returns a list of weeks; each week is a list of 7 cell dicts:
    {day, iso, count, in_month}. `day` is None for padding cells."""
    weeks = []
    for week in _CALENDAR.monthdatescalendar(year, month):
        cells = []
        for day_date in week:
            iso = day_date.isoformat()
            cells.append({
                "day": day_date.day,
                "iso": iso,
                "count": len(updates_by_date.get(iso, [])),
                "in_month": day_date.month == month,
            })
        weeks.append(cells)
    return weeks


def risk_tier_summary(results):
    """results: list of variance.VarianceResult. Returns an ordered list
    of {tier, label, count, pct} plus the total."""
    total = len(results)
    counts = {tier: 0 for tier in RISK_TIER_ORDER}
    for r in results:
        counts[r.risk_tier] += 1
    summary = []
    for tier in RISK_TIER_ORDER:
        count = counts[tier]
        pct = round(count / total * 100, 1) if total else 0.0
        summary.append({"tier": tier, "label": RISK_TIER_LABELS[tier], "count": count, "pct": pct})
    return summary, total


def donut_gradient(summary):
    """CSS conic-gradient stops for the donut, in the same order as
    `summary`. Uses fixed colors per tier so it matches the legend."""
    colors = {"healthy": "#2C5F2D", "review": "#D08A1E", "critical": "#B85042"}
    stops = []
    cursor = 0.0
    for entry in summary:
        start = cursor
        cursor += entry["pct"]
        if entry["count"] == 0:
            continue
        stops.append(f"{colors[entry['tier']]} {start:.2f}% {cursor:.2f}%")
    if not stops:
        return "#E1E6F0 0% 100%"
    return ", ".join(stops)


def bar_chart_data(results):
    """Margin-by-product bars, scaled against the widest margin in the
    set (with a sensible floor) so one outlier doesn't flatten the rest."""
    if not results:
        return []
    scale_ceiling = max([r.threshold_pct * 2 for r in results] + [r.variance_pct for r in results] + [1])
    bars = []
    for r in results:
        height_pct = max(2, min(100, (r.variance_pct / scale_ceiling) * 100))
        bars.append({
            "name": r.name,
            "variance_pct": r.variance_pct,
            "risk_tier": r.risk_tier,
            "height_pct": round(height_pct, 1),
        })
    return bars
