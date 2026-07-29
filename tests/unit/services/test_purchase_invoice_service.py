from pathlib import Path

import pytest

from src.core.exceptions import NotFoundException, ValidationException
from src.models.payment import Payment
from src.models.purchase_invoice_sync import PurchaseInvoiceSync
from src.repository.purchase_invoice_sync_repository import PurchaseInvoiceSyncRepository
from src.schemas.purchase_invoice_schema import PurchaseInvoicePaymentUpdateSchema
from src.services.external.fatturapa_inbound_parser import parse_fatturapa_inbound
from src.services.routers.purchase_invoice_service import PurchaseInvoiceService

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fatturapa_inbound"


@pytest.fixture
def payment(db_session):
    p = Payment(name="Bonifico")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _seed_invoice(db_session, xml_name: str = "td01_sample.xml") -> PurchaseInvoiceSync:
    xml = (FIXTURES / xml_name).read_text(encoding="utf-8")
    parsed = parse_fatturapa_inbound(xml)
    details = parsed.pop("details")
    repo = PurchaseInvoiceSyncRepository(db_session)
    invoice = repo.create(
        {
            "identificativo_sdi": f"SDI-{xml_name}",
            "nome_file": xml_name,
            "direzione": "Acquisto",
            "tipo": "Ricezione",
            "xml_content": xml,
            "tipo_documento": parsed["tipo_documento"],
            "numero_documento": parsed["numero_documento"],
            "data_documento": parsed["data_documento"],
            "fornitore_denominazione": parsed["fornitore_denominazione"],
            "fornitore_piva": parsed["fornitore_piva"],
            "importo_totale": parsed["importo_totale"],
            "fattura_collegata_numero": parsed["fattura_collegata_numero"],
            "fattura_collegata_data": parsed["fattura_collegata_data"],
            "is_paid": False,
        },
        details=details,
    )
    assert invoice is not None
    return invoice


@pytest.mark.asyncio
async def test_list_without_details(db_session):
    _seed_invoice(db_session)
    service = PurchaseInvoiceService(db_session)
    items, total = await service.list_invoices(page=1, limit=20)
    assert total == 1
    assert items[0].numero_documento == "123/2026"
    assert not hasattr(items[0], "details") or "details" not in items[0].model_dump()


@pytest.mark.asyncio
async def test_detail_includes_lines(db_session):
    invoice = _seed_invoice(db_session)
    service = PurchaseInvoiceService(db_session)
    detail = await service.get_invoice(invoice.id)
    assert detail.fornitore_denominazione == "Fornitore Test SpA"
    assert len(detail.details) == 2
    assert detail.details[0].descrizione == "Abbonamento hosting annuale"
    assert detail.details[1].codice_articolo == "SKU-001"


@pytest.mark.asyncio
async def test_update_payment_requires_id_when_paid(db_session):
    invoice = _seed_invoice(db_session)
    service = PurchaseInvoiceService(db_session)
    with pytest.raises(ValidationException):
        await service.update_payment(
            invoice.id, PurchaseInvoicePaymentUpdateSchema(is_paid=True)
        )


@pytest.mark.asyncio
async def test_update_payment_paid_and_unpaid(db_session, payment):
    invoice = _seed_invoice(db_session)
    service = PurchaseInvoiceService(db_session)

    paid = await service.update_payment(
        invoice.id,
        PurchaseInvoicePaymentUpdateSchema(
            is_paid=True, id_payment=payment.id_payment
        ),
    )
    assert paid.is_paid is True
    assert paid.id_payment == payment.id_payment
    assert paid.payment_name == "Bonifico"
    assert paid.paid_at is not None

    unpaid = await service.update_payment(
        invoice.id, PurchaseInvoicePaymentUpdateSchema(is_paid=False)
    )
    assert unpaid.is_paid is False
    assert unpaid.id_payment is None
    assert unpaid.paid_at is None


@pytest.mark.asyncio
async def test_filter_tipo_documento_td04(db_session):
    _seed_invoice(db_session, "td01_sample.xml")
    _seed_invoice(db_session, "td04_sample.xml")
    service = PurchaseInvoiceService(db_session)
    items, total = await service.list_invoices(tipo_documento="TD04")
    assert total == 1
    assert items[0].tipo_documento == "TD04"
    assert items[0].fattura_collegata_numero == "123/2026"


@pytest.mark.asyncio
async def test_get_missing_raises(db_session):
    service = PurchaseInvoiceService(db_session)
    with pytest.raises(NotFoundException):
        await service.get_invoice(99999)
