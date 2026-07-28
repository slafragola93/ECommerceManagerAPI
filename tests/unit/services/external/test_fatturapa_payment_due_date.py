"""Unit test — scadenza pagamento e data documento FatturaPA."""
from datetime import date, datetime, timedelta

import pytest

from src.services.external.fatturapa_service import (
    compute_arrotondamento,
    resolve_document_date,
    resolve_payment_due_date,
)


class TestResolvePaymentDueDate:
    def test_uses_payment_due_date_when_ge_document_date(self):
        order_data = {
            "payment_due_date": date(2026, 8, 14),
            "document_date": date(2026, 7, 15),
            "date_add": datetime(2020, 1, 1, 10, 0, 0),
        }
        assert resolve_payment_due_date(order_data) == date(2026, 8, 14)

    def test_uses_payment_due_date_from_string(self):
        order_data = {
            "payment_due_date": "2026-10-01",
            "document_date": "2026-07-15",
            "date_add": datetime(2020, 1, 1, 10, 0, 0),
        }
        assert resolve_payment_due_date(order_data) == date(2026, 10, 1)

    def test_ignores_payment_due_before_document_date(self):
        """Caso NC 000003: scadenza ordine < Data NC → ricalcola da document_date."""
        order_data = {
            "payment_due_date": date(2026, 5, 17),
            "document_date": date(2026, 7, 22),
            "date_add": datetime(2026, 4, 17, 10, 0, 0),
            "linked_invoice_date": date(2026, 4, 17),
        }
        assert resolve_payment_due_date(order_data) == date(2026, 8, 21)

    def test_fallback_plus_30_days_from_document_date(self):
        order_data = {"document_date": datetime(2026, 7, 15, 10, 0, 0)}
        assert resolve_payment_due_date(order_data) == date(2026, 8, 14)

    def test_fallback_custom_term_days(self):
        order_data = {"document_date": "2026-01-10"}
        assert resolve_payment_due_date(order_data, payment_term_days=60) == date(
            2026, 3, 11
        )

    def test_never_uses_linked_invoice_date_as_base(self):
        order_data = {
            "document_date": date(2026, 7, 22),
            "linked_invoice_date": date(2026, 4, 17),
            "date_add": datetime(2026, 4, 1, 10, 0, 0),
        }
        assert resolve_payment_due_date(order_data) == date(2026, 8, 21)

    def test_fallback_plus_30_days_from_string_document_date(self):
        order_data = {"document_date": "2026-01-10 14:30:00"}
        assert resolve_payment_due_date(order_data) == date(2026, 2, 9)

    @pytest.mark.parametrize("payment_due", [None, ""])
    def test_empty_or_falsy_uses_document_date_fallback(self, payment_due):
        order_data = {
            "payment_due_date": payment_due,
            "document_date": datetime(2026, 3, 1, 12, 0, 0),
            "date_add": datetime(2020, 1, 1),
        }
        expected = date(2026, 3, 1) + timedelta(days=30)
        assert resolve_payment_due_date(order_data) == expected


class TestResolveDocumentDate:
    def test_uses_document_date_datetime(self):
        order_data = {"document_date": datetime(2026, 7, 10, 15, 30, 0)}
        assert resolve_document_date(order_data) == date(2026, 7, 10)

    def test_uses_document_date_string(self):
        order_data = {"document_date": "2026-06-01 09:00:00"}
        assert resolve_document_date(order_data) == date(2026, 6, 1)

    def test_uses_fiscal_document_date_alias(self):
        order_data = {"fiscal_document_date": date(2026, 5, 20)}
        assert resolve_document_date(order_data) == date(2026, 5, 20)

    def test_fallback_today_when_missing(self):
        assert resolve_document_date({}) == date.today()


class TestComputeArrotondamento:
    def test_zero_when_totals_match(self):
        groups = [{"ImponibileImporto": 100.0, "Imposta": 22.0}]
        assert compute_arrotondamento(122.0, groups) == 0

    def test_difference_quantized(self):
        groups = [{"ImponibileImporto": 100.0, "Imposta": 22.0}]
        assert float(compute_arrotondamento(122.01, groups)) == 0.01
