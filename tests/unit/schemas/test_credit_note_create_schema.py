"""Validazione CreditNoteCreateSchema: is_partial richiede items o solo spedizione."""
import pytest
from pydantic import ValidationError

from src.schemas.fiscal_document_schema import CreditNoteCreateSchema


class TestCreditNoteCreateSchemaPartialItems:
    def test_partial_without_items_and_without_shipping_fails(self):
        with pytest.raises(ValidationError) as exc:
            CreditNoteCreateSchema(
                id_invoice=1,
                reason="Reso parziale",
                is_partial=True,
                include_shipping=False,
            )
        assert "items" in str(exc.value).lower() or "spedizione" in str(exc.value).lower()

    def test_partial_with_empty_items_and_without_shipping_fails(self):
        with pytest.raises(ValidationError):
            CreditNoteCreateSchema(
                id_invoice=1,
                reason="Reso parziale",
                is_partial=True,
                include_shipping=False,
                items=[],
            )

    def test_partial_shipping_only_without_items_ok(self):
        schema = CreditNoteCreateSchema(
            id_invoice=1,
            reason="Rimborso spedizione",
            is_partial=True,
            include_shipping=True,
            items=[],
        )
        assert schema.is_partial is True
        assert schema.include_shipping is True
        assert schema.items == []

    def test_partial_shipping_only_items_omitted_ok(self):
        schema = CreditNoteCreateSchema(
            id_invoice=1,
            reason="Rimborso spedizione",
            is_partial=True,
            include_shipping=True,
        )
        assert schema.items is None

    def test_partial_with_items_ok(self):
        schema = CreditNoteCreateSchema(
            id_invoice=1,
            reason="Reso parziale",
            is_partial=True,
            include_shipping=False,
            items=[{"id_order_detail": 10, "quantity": 1.0}],
        )
        assert schema.is_partial is True
        assert len(schema.items) == 1

    def test_total_without_items_ok(self):
        schema = CreditNoteCreateSchema(
            id_invoice=1,
            reason="Reso totale",
            is_partial=False,
        )
        assert schema.items is None
