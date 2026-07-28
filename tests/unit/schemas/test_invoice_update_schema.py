"""Validazione InvoiceUpdateSchema: flatten header, qty/sconti."""
from datetime import date

import pytest
from pydantic import ValidationError

from src.schemas.fiscal_document_schema import InvoiceUpdateSchema


class TestInvoiceUpdateSchema:
    def test_flatten_header_into_root(self):
        schema = InvoiceUpdateSchema.model_validate(
            {
                "sync_order": True,
                "header": {
                    "note": "Nota da header",
                    "id_payment": 3,
                    "payment_due_date": "2026-08-15",
                },
                "order_details": [
                    {
                        "id_order_detail": 10,
                        "product_qty": 2,
                        "unit_price_net": 100.0,
                        "unit_price_with_tax": 122.0,
                        "total_price_net": 200.0,
                        "total_price_with_tax": 244.0,
                        "id_tax": 7,
                    }
                ],
            }
        )
        assert schema.note == "Nota da header"
        assert schema.id_payment == 3
        assert schema.payment_due_date == date(2026, 8, 15)
        assert schema.sync_order is True
        assert len(schema.order_details) == 1

    def test_root_overrides_header(self):
        schema = InvoiceUpdateSchema.model_validate(
            {
                "note": "Root wins",
                "header": {"note": "Header"},
            }
        )
        assert schema.note == "Root wins"

    def test_sync_order_default_false(self):
        schema = InvoiceUpdateSchema()
        assert schema.sync_order is False
        assert schema.order_details is None

    def test_product_qty_must_be_positive(self):
        with pytest.raises(ValidationError):
            InvoiceUpdateSchema.model_validate(
                {
                    "order_details": [
                        {"id_order_detail": 1, "product_qty": 0},
                    ]
                }
            )

    def test_reduction_percent_max_100(self):
        with pytest.raises(ValidationError):
            InvoiceUpdateSchema.model_validate(
                {
                    "order_details": [
                        {
                            "id_order_detail": 1,
                            "reduction_percent": 101,
                        }
                    ]
                }
            )
