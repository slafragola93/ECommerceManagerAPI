"""Test GET credit note eligible lines (repository)."""
from datetime import datetime
from decimal import Decimal

import pytest

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from tests.helpers.fiscal_test_helpers import seed_paid_order, seed_tax


@pytest.fixture
def repo(db_session):
    return FiscalDocumentRepository(db_session)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


def _seed_invoice_with_detail(db_session, tax, *, product_qty: int = 5):
    order, detail = seed_paid_order(
        db_session,
        tax,
        reference="NC-ELIG",
        order_date=datetime(2026, 7, 22, 10, 0, 0),
        with_shipping=True,
        product_qty=product_qty,
    )
    invoice = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01",
        id_order=order.id_order,
        status="generated",
        is_electronic=True,
        includes_shipping=True,
        document_number="100",
        products_total_price_net=Decimal("500.00"),
        products_total_price_with_tax=Decimal("610.00"),
        total_price_net=Decimal("510.00"),
        total_price_with_tax=Decimal("622.20"),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)

    db_session.add(
        FiscalDocumentDetail(
            id_fiscal_document=invoice.id_fiscal_document,
            id_order_detail=detail.id_order_detail,
            product_qty=product_qty,
            id_tax=tax.id_tax,
            unit_price_net=Decimal("100.00"),
            unit_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal(str(100 * product_qty)),
            total_price_with_tax=Decimal(str(122 * product_qty)),
        )
    )
    db_session.commit()
    return invoice, detail, order


class TestCreditNoteEligibleLines:
    def test_no_prior_credit_notes(self, db_session, repo, tax):
        invoice, detail, _order = _seed_invoice_with_detail(db_session, tax, product_qty=5)

        result = repo.get_credit_note_eligible_lines(invoice.id_fiscal_document)

        assert result["can_create_credit_note"] is True
        assert result["has_total_credit_note"] is False
        assert result["shipping_already_refunded"] is False
        assert result["shipping_eligible"] is True
        assert result["shipping"]["unit_price_net"] == 10.0
        assert len(result["details"]) == 1
        line = result["details"][0]
        assert line["id_order_detail"] == detail.id_order_detail
        assert line["product_qty"] == 5.0
        assert line["refunded_qty"] == 0.0
        assert line["remaining_qty"] == 5.0
        assert line["is_fully_refunded"] is False
        assert line["product_name"] == "Prodotto NC-ELIG"

    def test_partial_credit_note_reduces_remaining_qty(self, db_session, repo, tax):
        invoice, detail, order = _seed_invoice_with_detail(db_session, tax, product_qty=5)

        partial_cn = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=order.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="generated",
            is_electronic=True,
            is_partial=True,
            includes_shipping=False,
            document_number="1",
            credit_note_reason="Reso parziale",
        )
        db_session.add(partial_cn)
        db_session.commit()
        db_session.refresh(partial_cn)

        db_session.add(
            FiscalDocumentDetail(
                id_fiscal_document=partial_cn.id_fiscal_document,
                id_order_detail=detail.id_order_detail,
                product_qty=2,
                id_tax=tax.id_tax,
                unit_price_net=Decimal("100.00"),
                unit_price_with_tax=Decimal("122.00"),
                total_price_net=Decimal("200.00"),
                total_price_with_tax=Decimal("244.00"),
            )
        )
        db_session.commit()

        result = repo.get_credit_note_eligible_lines(invoice.id_fiscal_document)
        line = result["details"][0]

        assert line["refunded_qty"] == 2.0
        assert line["remaining_qty"] == 3.0
        assert line["is_fully_refunded"] is False

    def test_shipping_already_refunded(self, db_session, repo, tax):
        invoice, _detail, order = _seed_invoice_with_detail(db_session, tax)

        shipping_cn = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=order.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="generated",
            is_electronic=True,
            is_partial=True,
            includes_shipping=True,
            document_number="2",
            credit_note_reason="Storno spedizione",
        )
        db_session.add(shipping_cn)
        db_session.commit()

        result = repo.get_credit_note_eligible_lines(invoice.id_fiscal_document)

        assert result["shipping_already_refunded"] is True
        assert result["shipping_eligible"] is False
        assert result["shipping"] is None

    def test_total_credit_note_blocks_new_nc(self, db_session, repo, tax):
        invoice, _detail, order = _seed_invoice_with_detail(db_session, tax)

        total_cn = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=order.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="generated",
            is_electronic=True,
            is_partial=False,
            includes_shipping=True,
            document_number="3",
            credit_note_reason="Storno totale",
        )
        db_session.add(total_cn)
        db_session.commit()

        result = repo.get_credit_note_eligible_lines(invoice.id_fiscal_document)

        assert result["has_total_credit_note"] is True
        assert result["can_create_credit_note"] is False

    def test_invoice_not_found_raises(self, repo):
        with pytest.raises(ValueError, match="Fattura 99999 non trovata"):
            repo.get_credit_note_eligible_lines(99999)
