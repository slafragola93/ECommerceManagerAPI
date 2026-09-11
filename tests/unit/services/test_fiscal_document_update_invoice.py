"""Test PATCH update_invoice + sync_order atomico."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.core.container_config import get_configured_container
from src.core.exceptions import BusinessRuleException, NotFoundException, ValidationException
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.payment import Payment
from src.models.shipping import Shipping
from src.schemas.fiscal_document_schema import InvoiceUpdateSchema
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from tests.helpers.fiscal_test_helpers import seed_paid_order, seed_tax


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def fiscal_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IFiscalDocumentService, db_session)


def _seed_pending_invoice(db_session, tax, *, with_shipping=True, status="pending"):
    payment = Payment(name="Bonifico")
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    order, detail = seed_paid_order(
        db_session,
        tax,
        reference="UPD-INV",
        order_date=datetime(2026, 7, 16, 10, 0, 0),
        with_shipping=with_shipping,
        country_iso="IT",
    )
    order.id_payment = payment.id_payment
    order.general_note = "nota iniziale"
    db_session.commit()

    invoice = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01",
        id_order=order.id_order,
        status=status,
        is_electronic=True,
        includes_shipping=with_shipping,
        document_number="99",
        products_total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("110.00") if with_shipping else Decimal("100.00"),
        total_price_with_tax=Decimal("134.20") if with_shipping else Decimal("122.00"),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)

    fd_detail = FiscalDocumentDetail(
        id_fiscal_document=invoice.id_fiscal_document,
        id_order_detail=detail.id_order_detail,
        product_qty=1,
        id_tax=tax.id_tax,
        unit_price_net=Decimal("100.00"),
        unit_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
    )
    db_session.add(fd_detail)
    db_session.commit()
    db_session.refresh(fd_detail)

    return order, detail, invoice, fd_detail, payment


class TestUpdateInvoice:
    @pytest.mark.asyncio
    async def test_header_only_updates_order(self, db_session, fiscal_service, tax):
        order, detail, invoice, fd_detail, payment = _seed_pending_invoice(
            db_session, tax
        )
        other_payment = Payment(name="Carta")
        db_session.add(other_payment)
        db_session.commit()
        db_session.refresh(other_payment)

        result = await fiscal_service.update_invoice(
            invoice.id_fiscal_document,
            InvoiceUpdateSchema(
                note="Nuova nota",
                id_payment=other_payment.id_payment,
                shipping_total_price_net=20.0,
                shipping_total_price_with_tax=24.4,
            ),
        )

        db_session.refresh(order)
        shipping = (
            db_session.query(Shipping)
            .filter(Shipping.id_shipping == order.id_shipping)
            .first()
        )
        assert order.general_note == "Nuova nota"
        assert order.id_payment == other_payment.id_payment
        assert float(shipping.price_tax_excl) == 20.0
        assert float(shipping.price_tax_incl) == 24.4
        assert result.sync_order_result.status == "skipped"
        assert result.sync_order_result.enabled is False

        db_session.refresh(fd_detail)
        assert float(fd_detail.total_price_net) == 100.0

    @pytest.mark.asyncio
    async def test_lines_sync_order_true(self, db_session, fiscal_service, tax):
        order, detail, invoice, fd_detail, _ = _seed_pending_invoice(db_session, tax)

        result = await fiscal_service.update_invoice(
            invoice.id_fiscal_document,
            InvoiceUpdateSchema.model_validate(
                {
                    "sync_order": True,
                    "order_details": [
                        {
                            "id_order_detail": detail.id_order_detail,
                            "product_name": "Prodotto aggiornato",
                            "product_qty": 2,
                            "id_tax": tax.id_tax,
                            "unit_price_net": 90.0,
                            "unit_price_with_tax": 109.8,
                            "total_price_net": 180.0,
                            "total_price_with_tax": 219.6,
                            "reduction_percent": 0,
                            "reduction_amount": 0,
                        }
                    ],
                }
            ),
        )

        db_session.refresh(fd_detail)
        db_session.refresh(detail)
        db_session.refresh(order)
        db_session.refresh(invoice)

        assert int(fd_detail.product_qty) == 2
        assert float(fd_detail.total_price_net) == 180.0
        assert int(detail.product_qty) == 2
        assert detail.product_name == "Prodotto aggiornato"
        assert float(detail.total_price_net) == 180.0
        assert float(invoice.products_total_price_net) == 180.0
        assert result.sync_order_result.enabled is True
        assert result.sync_order_result.updated_lines == 1
        assert result.sync_order_result.status == "success"
        assert result.sync_order_result.order_id == order.id_order

    @pytest.mark.asyncio
    async def test_lines_without_sync_leaves_order_detail(self, db_session, fiscal_service, tax):
        order, detail, invoice, fd_detail, _ = _seed_pending_invoice(db_session, tax)
        original_name = detail.product_name
        original_qty = detail.product_qty

        await fiscal_service.update_invoice(
            invoice.id_fiscal_document,
            InvoiceUpdateSchema.model_validate(
                {
                    "sync_order": False,
                    "order_details": [
                        {
                            "id_order_detail": detail.id_order_detail,
                            "product_name": "Ignorato su ordine",
                            "product_qty": 3,
                            "id_tax": tax.id_tax,
                            "unit_price_net": 50.0,
                            "unit_price_with_tax": 61.0,
                            "total_price_net": 150.0,
                            "total_price_with_tax": 183.0,
                        }
                    ],
                }
            ),
        )

        db_session.refresh(fd_detail)
        db_session.refresh(detail)
        assert int(fd_detail.product_qty) == 3
        assert float(fd_detail.total_price_net) == 150.0
        assert detail.product_qty == original_qty
        assert detail.product_name == original_name

    @pytest.mark.asyncio
    async def test_generated_without_sdi_is_editable_and_clears_xml(
        self, db_session, fiscal_service, tax
    ):
        _, _, invoice, _, _ = _seed_pending_invoice(db_session, tax, status="generated")
        invoice.xml_content = "<xml/>"
        invoice.filename = "IT02046570426_000001.xml"
        db_session.commit()

        result = await fiscal_service.update_invoice(
            invoice.id_fiscal_document,
            InvoiceUpdateSchema(note="x"),
        )
        db_session.refresh(invoice)
        assert invoice.status == "pending"
        assert invoice.xml_content is None
        assert invoice.filename is None
        assert result is not None

    @pytest.mark.asyncio
    async def test_consegnata_status_conflict(self, db_session, fiscal_service, tax):
        _, _, invoice, _, _ = _seed_pending_invoice(db_session, tax, status="generated")
        invoice.sdi_status = "consegnata"
        db_session.commit()

        with pytest.raises(BusinessRuleException) as exc:
            await fiscal_service.update_invoice(
                invoice.id_fiscal_document,
                InvoiceUpdateSchema(note="x"),
            )
        assert exc.value.status_code == 409
        assert "evaso" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_credit_note_linked_conflict(self, db_session, fiscal_service, tax):
        order, detail, invoice, _, _ = _seed_pending_invoice(db_session, tax)
        cn = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=order.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="pending",
            is_electronic=True,
            includes_shipping=False,
            credit_note_reason="storno",
        )
        db_session.add(cn)
        db_session.commit()

        with pytest.raises(BusinessRuleException) as exc:
            await fiscal_service.update_invoice(
                invoice.id_fiscal_document,
                InvoiceUpdateSchema(note="x"),
            )
        assert exc.value.status_code == 409
        assert "note di credito" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_unknown_order_detail_not_found(self, db_session, fiscal_service, tax):
        _, _, invoice, _, _ = _seed_pending_invoice(db_session, tax)

        with pytest.raises(NotFoundException):
            await fiscal_service.update_invoice(
                invoice.id_fiscal_document,
                InvoiceUpdateSchema.model_validate(
                    {
                        "order_details": [
                            {
                                "id_order_detail": 999999,
                                "product_qty": 1,
                                "id_tax": tax.id_tax,
                                "unit_price_net": 10.0,
                                "unit_price_with_tax": 12.2,
                                "total_price_net": 10.0,
                                "total_price_with_tax": 12.2,
                            }
                        ]
                    }
                ),
            )

    @pytest.mark.asyncio
    async def test_reduction_amount_exceeds_line_net(self, db_session, fiscal_service, tax):
        _, detail, invoice, _, _ = _seed_pending_invoice(db_session, tax)

        with pytest.raises(ValidationException) as exc:
            await fiscal_service.update_invoice(
                invoice.id_fiscal_document,
                InvoiceUpdateSchema.model_validate(
                    {
                        "order_details": [
                            {
                                "id_order_detail": detail.id_order_detail,
                                "product_qty": 1,
                                "id_tax": tax.id_tax,
                                "unit_price_net": 100.0,
                                "unit_price_with_tax": 122.0,
                                "total_price_net": 100.0,
                                "total_price_with_tax": 122.0,
                                "reduction_amount": 999.0,
                            }
                        ]
                    }
                ),
            )
        assert "reduction_amount" in exc.value.message.lower() or "imponibile" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_rollback_on_sync_failure(self, db_session, fiscal_service, tax):
        order, detail, invoice, fd_detail, _ = _seed_pending_invoice(db_session, tax)
        original_fd_qty = int(fd_detail.product_qty)
        original_note = order.general_note

        with patch.object(
            fiscal_service,
            "_sync_order_detail_from_invoice_line",
            side_effect=RuntimeError("sync boom"),
        ):
            with pytest.raises(RuntimeError, match="sync boom"):
                await fiscal_service.update_invoice(
                    invoice.id_fiscal_document,
                    InvoiceUpdateSchema.model_validate(
                        {
                            "note": "non deve restare",
                            "sync_order": True,
                            "order_details": [
                                {
                                    "id_order_detail": detail.id_order_detail,
                                    "product_qty": 5,
                                    "id_tax": tax.id_tax,
                                    "unit_price_net": 100.0,
                                    "unit_price_with_tax": 122.0,
                                    "total_price_net": 500.0,
                                    "total_price_with_tax": 610.0,
                                }
                            ],
                        }
                    ),
                )

        db_session.expire_all()
        db_session.refresh(fd_detail)
        db_session.refresh(order)
        assert int(fd_detail.product_qty) == original_fd_qty
        assert order.general_note == original_note

    @pytest.mark.asyncio
    async def test_credit_note_document_type_rejected(self, db_session, fiscal_service, tax):
        order, detail, invoice, _, _ = _seed_pending_invoice(db_session, tax)
        cn = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=order.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="pending",
            is_electronic=True,
            includes_shipping=False,
            credit_note_reason="storno",
        )
        db_session.add(cn)
        db_session.commit()
        db_session.refresh(cn)

        with pytest.raises(BusinessRuleException) as exc:
            await fiscal_service.update_invoice(
                cn.id_fiscal_document,
                InvoiceUpdateSchema(note="x"),
            )
        assert exc.value.status_code == 409
