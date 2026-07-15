"""Unit test — scadenza pagamento FatturaPA (payment_due_date vs fallback +30)."""
from datetime import date, datetime, timedelta

import pytest

from src.services.external.fatturapa_service import resolve_payment_due_date


class TestResolvePaymentDueDate:
    def test_uses_payment_due_date_when_set(self):
        order_data = {
            "payment_due_date": date(2026, 8, 14),
            "date_add": datetime(2026, 7, 15, 10, 0, 0),
        }
        assert resolve_payment_due_date(order_data) == date(2026, 8, 14)

    def test_uses_payment_due_date_from_string(self):
        order_data = {
            "payment_due_date": "2026-10-01",
            "date_add": datetime(2026, 7, 15, 10, 0, 0),
        }
        assert resolve_payment_due_date(order_data) == date(2026, 10, 1)

    def test_fallback_plus_30_days_from_date_add(self):
        order_date = datetime(2026, 7, 15, 10, 0, 0)
        order_data = {"date_add": order_date}
        expected = (order_date + timedelta(days=30)).date()
        assert resolve_payment_due_date(order_data) == expected

    def test_fallback_plus_30_days_from_string_date_add(self):
        order_data = {"date_add": "2026-01-10 14:30:00"}
        assert resolve_payment_due_date(order_data) == date(2026, 2, 9)

    @pytest.mark.parametrize("payment_due", [None, ""])
    def test_empty_or_falsy_uses_fallback(self, payment_due):
        order_date = datetime(2026, 3, 1, 12, 0, 0)
        order_data = {
            "payment_due_date": payment_due,
            "date_add": order_date,
        }
        expected = (order_date + timedelta(days=30)).date()
        assert resolve_payment_due_date(order_data) == expected
