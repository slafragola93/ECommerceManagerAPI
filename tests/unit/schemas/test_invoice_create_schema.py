"""Validazione InvoiceCreateSchema: is_partial richiede items; extra ignorati."""
import pytest
from pydantic import ValidationError

from src.schemas.fiscal_document_schema import InvoiceCreateSchema


class TestInvoiceCreateSchemaPartialItems:
    def test_partial_without_items_fails(self):
        with pytest.raises(ValidationError) as exc:
            InvoiceCreateSchema(
                id_order=1,
                is_partial=True,
            )
        msg = str(exc.value).lower()
        assert "items" in msg
        assert "is_partial" in msg or "parziale" in msg

    def test_partial_with_empty_items_fails(self):
        with pytest.raises(ValidationError) as exc:
            InvoiceCreateSchema(
                id_order=1,
                is_partial=True,
                items=[],
            )
        assert "items" in str(exc.value).lower()

    def test_partial_with_items_ok(self):
        schema = InvoiceCreateSchema(
            id_order=1,
            is_partial=True,
            items=[{"id_order_detail": 10, "quantity": 1.0}],
        )
        assert schema.is_partial is True
        assert len(schema.items) == 1
        assert schema.include_shipping is False

    def test_residual_without_items_ok(self):
        schema = InvoiceCreateSchema(id_order=1)
        assert schema.is_partial is False
        assert schema.items is None
        assert schema.include_shipping is True

    def test_residual_with_empty_items_ok(self):
        schema = InvoiceCreateSchema(id_order=1, is_partial=False, items=[])
        assert schema.is_partial is False
        assert schema.items == []
        assert schema.include_shipping is True

    def test_reemission_items_without_partial_ok(self):
        schema = InvoiceCreateSchema(
            id_order=1,
            items=[{"id_order_detail": 10, "quantity": 2.0}],
        )
        assert schema.is_partial is False
        assert len(schema.items) == 1
        assert schema.include_shipping is True

    def test_include_shipping_explicit_override(self):
        schema = InvoiceCreateSchema(
            id_order=1,
            is_partial=True,
            include_shipping=True,
            items=[{"id_order_detail": 10, "quantity": 1.0}],
        )
        assert schema.include_shipping is True

    def test_extra_fields_ignored(self):
        schema = InvoiceCreateSchema(
            id_order=1,
            is_electronic=True,
            emitter_country_iso="IT",
            invoice_flow="standard",
        )
        assert schema.id_order == 1
        data = schema.model_dump()
        assert "is_electronic" not in data
        assert "emitter_country_iso" not in data
        assert "invoice_flow" not in data
