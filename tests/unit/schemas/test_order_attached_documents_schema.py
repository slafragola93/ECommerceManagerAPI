"""Envelope nested ordine: fatture solo ``invoices``, resi/ricevute tengono ``items``."""
from src.schemas.order_attached_documents_schema import (
    OrderInvoicesListResponseSchema,
    OrderReturnsListResponseSchema,
    OrderRicevuteListResponseSchema,
)


def test_invoices_envelope_has_no_items_key():
    payload = OrderInvoicesListResponseSchema(invoices=[], total=0, page=1, limit=10)
    data = payload.model_dump()
    assert "items" not in data
    assert data["invoices"] == []
    assert data["total"] == 0


def test_returns_and_ricevute_keep_items_alias():
    returns_data = OrderReturnsListResponseSchema(
        items=[], returns=[], total=0, page=1, limit=10
    ).model_dump()
    assert "items" in returns_data
    assert "returns" in returns_data

    ricevute_data = OrderRicevuteListResponseSchema(
        items=[], ricevute=[], total=0, page=1, limit=10
    ).model_dump()
    assert "items" in ricevute_data
    assert "ricevute" in ricevute_data
