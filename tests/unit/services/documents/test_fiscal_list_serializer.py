"""Lista fiscal_documents: pagamento ordine + sdi_status senza N+1."""
from datetime import date, datetime
from decimal import Decimal

from src.models.app_configuration import AppConfiguration
from src.models.fiscal_document import FiscalDocument
from src.models.order_payment import OrderPayment
from src.models.payment import Payment
from src.services.documents.fiscal_list_serializer import serialize_fiscal_documents
from tests.helpers.fiscal_test_helpers import seed_paid_order, seed_tax


def _invoice(
    db_session,
    order,
    *,
    status="sent",
    sdi_status=None,
    is_electronic=True,
    upload_result=None,
):
    doc = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01" if is_electronic else None,
        id_order=order.id_order,
        status=status,
        is_electronic=is_electronic,
        includes_shipping=False,
        document_number="1",
        sdi_status=sdi_status,
        identificativo_sdi="111" if sdi_status == "scartata" else None,
        upload_result=upload_result,
        products_total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_list_uses_order_catalog_payment_not_missing(db_session):
    tax = seed_tax(db_session)
    bonifico = Payment(name="Bonifico")
    paypal = Payment(name="PayPal")
    db_session.add_all([bonifico, paypal])
    db_session.commit()
    db_session.refresh(bonifico)
    db_session.refresh(paypal)

    order_b, _ = seed_paid_order(
        db_session, tax, reference="PAY-BON", order_date=datetime(2026, 9, 1)
    )
    order_b.id_payment = bonifico.id_payment
    order_p, _ = seed_paid_order(
        db_session, tax, reference="PAY-PP", order_date=datetime(2026, 9, 2)
    )
    order_p.id_payment = paypal.id_payment
    db_session.commit()

    docs = [
        _invoice(db_session, order_b, status="sent", sdi_status=None),
        _invoice(db_session, order_p, status="generated", sdi_status="scartata"),
    ]
    rows = serialize_fiscal_documents(db_session, docs)
    by_order = {r.id_order: r for r in rows}

    waiting = by_order[order_b.id_order]
    assert waiting.order_payment_name == "Bonifico"
    assert waiting.id_order_payment == bonifico.id_payment
    assert waiting.sdi_status is None
    assert waiting.status == "sent"
    assert waiting.customer_name == "Rossi Mario"
    assert waiting.id_customer == order_b.id_customer
    assert waiting.is_payed is True

    scartata = by_order[order_p.id_order]
    assert scartata.order_payment_name == "PayPal"
    assert scartata.id_order_payment == paypal.id_payment
    assert scartata.sdi_status == "scartata"
    assert scartata.identificativo_sdi == "111"
    assert scartata.fatturapa_status == "error"


def test_list_fallback_last_paid_order_payment(db_session):
    tax = seed_tax(db_session)
    carta = Payment(name="Carta")
    db_session.add(carta)
    db_session.commit()
    db_session.refresh(carta)

    order, _ = seed_paid_order(
        db_session, tax, reference="PAY-FALL", order_date=datetime(2026, 9, 3)
    )
    order.id_payment = None
    db_session.commit()

    older = OrderPayment(
        id_order=order.id_order,
        id_payment=carta.id_payment,
        amount=Decimal("10.00"),
        is_paid=True,
        payment_date=date(2026, 8, 1),
    )
    newer = OrderPayment(
        id_order=order.id_order,
        id_payment=carta.id_payment,
        amount=Decimal("20.00"),
        is_paid=True,
        payment_date=date(2026, 9, 1),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    doc = _invoice(db_session, order)
    row = serialize_fiscal_documents(db_session, [doc])[0]
    assert row.order_payment_name == "Carta"
    assert row.id_order_payment == carta.id_payment


def test_non_electronic_sdi_fields_null(db_session):
    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session, tax, reference="NO-FE", order_date=datetime(2026, 9, 4)
    )
    doc = _invoice(
        db_session,
        order,
        status="issued",
        sdi_status="consegnata",
        is_electronic=False,
    )
    doc.identificativo_sdi = "999"
    db_session.commit()
    row = serialize_fiscal_documents(db_session, [doc])[0]
    assert row.sdi_status is None
    assert row.identificativo_sdi is None


def test_order_shipped_from_id_shipping(db_session):
    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session,
        tax,
        reference="SHIP",
        order_date=datetime(2026, 9, 5),
        with_shipping=True,
    )
    doc = _invoice(db_session, order, status="pending")
    row = serialize_fiscal_documents(db_session, [doc])[0]
    assert row.order_shipped is True
    assert row.sdi_status is None
    assert row.mail_status is None


def test_list_omits_xml_content_by_default(db_session):
    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session, tax, reference="NO-XML", order_date=datetime(2026, 9, 6)
    )
    doc = _invoice(db_session, order)
    doc.xml_content = "<FatturaElettronica/>"
    db_session.commit()

    row = serialize_fiscal_documents(db_session, [doc])[0]
    dumped = row.model_dump()
    assert "xml_content" not in dumped

    included = serialize_fiscal_documents(db_session, [doc], include_xml=True)[0]
    assert included.xml_content == "<FatturaElettronica/>"


def test_list_filename_computed_from_vat_and_progressivo(db_session):
    tax = seed_tax(db_session)
    db_session.add(
        AppConfiguration(
            category="company_info", name="vat_number", value="IT08632861210"
        )
    )
    db_session.commit()
    order, _ = seed_paid_order(
        db_session, tax, reference="FN-CALC", order_date=datetime(2026, 9, 7)
    )
    doc = _invoice(db_session, order, status="generated")
    doc.progressivo_invio = "101164"
    doc.filename = "legacy-stored.xml"
    db_session.commit()

    row = serialize_fiscal_documents(db_session, [doc])[0]
    assert row.filename == "IT08632861210_101164.xml"


def test_list_filename_falls_back_to_stored_column(db_session):
    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session, tax, reference="FN-FB", order_date=datetime(2026, 9, 8)
    )
    doc = _invoice(db_session, order, status="generated")
    doc.filename = "IT01558670780_OLD.xml"
    db_session.commit()

    row = serialize_fiscal_documents(db_session, [doc])[0]
    assert row.filename == "IT01558670780_OLD.xml"


def test_list_omits_upload_result_and_keeps_error_message(db_session):
    import json

    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session, tax, reference="UR-ERR", order_date=datetime(2026, 9, 9)
    )
    payload = json.dumps({"status": "error", "message": "CAP non valido"})
    doc = _invoice(
        db_session, order, status="error", upload_result=payload
    )
    row = serialize_fiscal_documents(db_session, [doc])[0]
    dumped = row.model_dump()
    assert "upload_result" not in dumped
    assert row.fatturapa_status == "error"
    assert "CAP" in (row.fatturapa_error_message or "")
    assert row.lifecycle is not None
    assert row.lifecycle.status == "error"
    assert row.lifecycle.fatturapa.status == "error"
    assert row.lifecycle.fatturapa.error_message == row.fatturapa_error_message


_NC_ONLY_KEYS = ("credit_note_reason", "is_partial", "id_fiscal_document_ref")


def test_list_invoice_omits_nc_only_fields(db_session):
    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session, tax, reference="INV-NO-NC", order_date=datetime(2026, 9, 10)
    )
    doc = _invoice(db_session, order)
    doc.credit_note_reason = "should not leak"
    doc.is_partial = True
    db_session.commit()

    dumped = serialize_fiscal_documents(db_session, [doc])[0].model_dump()
    for key in _NC_ONLY_KEYS:
        assert key not in dumped


def test_list_credit_note_keeps_nc_only_fields(db_session):
    tax = seed_tax(db_session)
    order, _ = seed_paid_order(
        db_session, tax, reference="CN-KEEP", order_date=datetime(2026, 9, 11)
    )
    invoice = _invoice(db_session, order)
    credit_note = FiscalDocument(
        document_type="credit_note",
        tipo_documento_fe="TD04",
        id_order=order.id_order,
        id_fiscal_document_ref=invoice.id_fiscal_document,
        status="pending",
        is_electronic=True,
        includes_shipping=False,
        is_partial=True,
        credit_note_reason="Reso parziale",
        document_number="1",
        products_total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
    )
    db_session.add(credit_note)
    db_session.commit()
    db_session.refresh(credit_note)

    dumped = serialize_fiscal_documents(db_session, [credit_note])[0].model_dump()
    assert dumped["id_fiscal_document_ref"] == invoice.id_fiscal_document
    assert dumped["credit_note_reason"] == "Reso parziale"
    assert dumped["is_partial"] is True
