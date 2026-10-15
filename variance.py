"""Automated Variance-Flagging Module.

Computes the percentage difference (profit margin) between a product's
latest supplier cost and its current retail price, and flags products
whose margin has fallen below the store's configured minimum threshold
-- e.g. because a supplier raised their cost but the shelf price was
never adjusted. This supports profit-margin control and gives an
instant, logic-based price-adjustment alert.
"""
from dataclasses import dataclass


@dataclass
class VarianceResult:
    product_id: int
    name: str
    supplier_cost: float
    retail_price: float
    variance_pct: float
    threshold_pct: float
    flagged: bool


def compute_variance_pct(supplier_cost, retail_price):
    """Margin as a percentage of supplier cost:
    ((retail_price - supplier_cost) / supplier_cost) * 100
    """
    if supplier_cost == 0:
        raise ValueError("supplier_cost must be non-zero")
    return (retail_price - supplier_cost) / supplier_cost * 100


def evaluate_product(product) -> VarianceResult:
    """product must expose: id, name, supplier_cost, retail_price,
    variance_threshold_pct (a sqlite3.Row or any mapping-like object)."""
    variance_pct = compute_variance_pct(product["supplier_cost"], product["retail_price"])
    threshold_pct = product["variance_threshold_pct"]
    flagged = variance_pct < threshold_pct
    return VarianceResult(
        product_id=product["id"],
        name=product["name"],
        supplier_cost=product["supplier_cost"],
        retail_price=product["retail_price"],
        variance_pct=round(variance_pct, 2),
        threshold_pct=threshold_pct,
        flagged=flagged,
    )


def flagged_products(products):
    """Given an iterable of product rows, return VarianceResults that
    need review (current margin below the minimum acceptable threshold)."""
    return [r for r in (evaluate_product(p) for p in products) if r.flagged]
