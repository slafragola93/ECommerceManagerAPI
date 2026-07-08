"""Test utility date incasso ricevute."""
from datetime import date, datetime, timezone

import pytest

from src.models.order import Order
from src.services.ricevute.date_utils import resolve_order_payment_date


def test_resolve_payment_date_from_column():
    order = Order(payment_date=date(2026, 3, 15), is_payed=True)
    assert resolve_order_payment_date(order) == date(2026, 3, 15)


def test_resolve_payment_date_fallback_date_add_rome():
    order = Order(
        is_payed=True,
        payment_date=None,
        date_add=datetime(2026, 3, 15, 23, 30, tzinfo=timezone.utc),
    )
    assert resolve_order_payment_date(order) == date(2026, 3, 16)


def test_resolve_payment_date_missing_raises():
    order = Order(is_payed=False, payment_date=None, date_add=None)
    with pytest.raises(ValueError):
        resolve_order_payment_date(order)
