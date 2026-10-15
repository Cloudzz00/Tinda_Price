"""Trend-Analysis Forecasting Module.

Projects short-term retail-price movement from historical price records
using a simple moving average and a linear regression (least squares)
trend line, following the general approach of Banatao et al. (2024) for
retail price forecasting. These are analytical guidance only, not
guaranteed future prices.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ForecastResult:
    moving_average: Optional[float]
    linear_regression: Optional[float]
    periods_used: int


def moving_average_forecast(prices: List[float], window: int = 3) -> Optional[float]:
    """Forecast the next price as the average of the last `window` prices."""
    if not prices:
        return None
    window = min(window, len(prices))
    recent = prices[-window:]
    return round(sum(recent) / len(recent), 2)


def linear_regression_forecast(prices: List[float]) -> Optional[float]:
    """Fit y = a + b*x over the price series (x = 0..n-1) with ordinary
    least squares and project the next period (x = n)."""
    n = len(prices)
    if n < 2:
        return None

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(prices) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, prices))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return round(mean_y, 2)

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    next_x = n
    forecast = intercept + slope * next_x
    return round(max(forecast, 0.0), 2)


def forecast_prices(prices: List[float], window: int = 3) -> ForecastResult:
    return ForecastResult(
        moving_average=moving_average_forecast(prices, window=window),
        linear_regression=linear_regression_forecast(prices),
        periods_used=len(prices),
    )


def forecast_for_product(price_history_rows, window: int = 3) -> ForecastResult:
    """price_history_rows: ordered (oldest-first) iterable of rows with a
    'retail_price' field, as returned by repository.get_price_history()."""
    prices = [row["retail_price"] for row in price_history_rows]
    return forecast_prices(prices, window=window)
