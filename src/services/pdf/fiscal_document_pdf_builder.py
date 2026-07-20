"""Costruzione PDF singolo documento fiscale (fattura / nota di credito)."""
from __future__ import annotations

from io import BytesIO
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.repository.app_configuration_repository import AppConfigurationRepository
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.services.pdf.fiscal_document_pdf_service import FiscalDocumentPDFService


def _build_details_with_products(db: Session, id_fiscal_document: int, details) -> list:
    from src.models.order_detail import OrderDetail
    from src.models.tax import Tax

    details_with_products = []
    for detail in details:
        order_detail = (
            db.query(OrderDetail)
            .filter(OrderDetail.id_order_detail == detail.id_order_detail)
            .first()
        )

        vat_rate = 0
        tax_note = None
        tax_id = detail.id_tax or (order_detail.id_tax if order_detail else None)
        if tax_id:
            tax = db.query(Tax).filter(Tax.id_tax == tax_id).first()
            if tax:
                vat_rate = tax.percentage
                tax_note = (tax.note or "").strip() or None

        unit_price_net = detail.unit_price_net
        if unit_price_net is None and order_detail:
            unit_price_net = getattr(order_detail, "unit_price_net", None) or getattr(
                order_detail, "product_price", None
            )
        total_price_net = detail.total_price_net
        if total_price_net is None and order_detail:
            total_price_net = getattr(order_detail, "total_price_net", None)

        details_with_products.append(
            {
                "id_fiscal_document_detail": detail.id_fiscal_document_detail,
                "id_order_detail": detail.id_order_detail,
                "product_qty": detail.product_qty,
                "unit_price": detail.unit_price_net
                if detail.unit_price_net is not None
                else detail.unit_price,
                "unit_price_net": unit_price_net
                if unit_price_net is not None
                else detail.unit_price,
                "total_price_with_tax": detail.total_price_with_tax,
                "total_price_net": total_price_net
                if total_price_net is not None
                else detail.total_price_with_tax,
                "product_name": order_detail.product_name if order_detail else "N/A",
                "product_reference": order_detail.product_reference
                if order_detail
                else "N/A",
                "reduction_percent": order_detail.reduction_percent
                if order_detail
                else 0.0,
                "vat_rate": vat_rate,
                "tax_note": tax_note,
                "id_tax": tax_id,
            }
        )
    return details_with_products


def _load_company_configs(db: Session) -> tuple[dict, dict]:
    app_config_repo = AppConfigurationRepository(db)
    company_config = {}
    for config in app_config_repo.get_by_category("company_info"):
        company_config[config.name] = config.value or ""

    if not company_config:
        company_config = {
            "company_name": "Azienda",
            "company_vat": "P.IVA",
            "company_address": "Indirizzo",
            "company_city": "Città",
            "company_pec": "PEC",
            "company_sdi": "SDI",
        }

    invoice_pdf_config = {}
    for config in app_config_repo.get_by_category("invoice_pdf"):
        invoice_pdf_config[config.name] = config.value or ""

    return company_config, invoice_pdf_config


def build_fiscal_document_pdf(
    db: Session,
    id_fiscal_document: int,
    *,
    raise_http: bool = True,
) -> Tuple[bytes, str]:
    """
    Genera bytes PDF e nome file per un documento fiscale.

    Args:
        db: Sessione SQLAlchemy
        id_fiscal_document: ID documento
        raise_http: Se True solleva HTTPException; altrimenti ValueError

    Returns:
        (pdf_bytes, filename)
    """
    from src.models.address import Address
    from src.models.fiscal_document_detail import FiscalDocumentDetail
    from src.models.order import Order
    from src.models.payment import Payment

    def _fail(status_code: int, detail: str):
        if raise_http:
            raise HTTPException(status_code=status_code, detail=detail)
        raise ValueError(detail)

    fiscal_repo = FiscalDocumentRepository(db)
    fiscal_document = fiscal_repo.get_fiscal_document_by_id(id_fiscal_document)

    if not fiscal_document:
        _fail(404, f"Documento fiscale {id_fiscal_document} non trovato")

    if (
        fiscal_document.document_type == "credit_note"
        and not fiscal_document.id_fiscal_document_ref
    ):
        _fail(
            400,
            "Nota di credito senza riferimento a fattura. Impossibile generare PDF.",
        )

    order = db.query(Order).filter(Order.id_order == fiscal_document.id_order).first()
    if not order:
        _fail(404, f"Ordine {fiscal_document.id_order} non trovato")

    invoice_address = (
        db.query(Address).filter(Address.id_address == order.id_address_invoice).first()
    )
    delivery_address = (
        db.query(Address).filter(Address.id_address == order.id_address_delivery).first()
    )

    details = (
        db.query(FiscalDocumentDetail)
        .filter(FiscalDocumentDetail.id_fiscal_document == id_fiscal_document)
        .all()
    )
    if not details:
        _fail(
            404,
            f"Nessun articolo trovato nel documento {id_fiscal_document}. "
            "Impossibile generare PDF.",
        )

    details_with_products = _build_details_with_products(db, id_fiscal_document, details)

    payment_name = None
    if order.id_payment:
        payment = db.query(Payment).filter(Payment.id_payment == order.id_payment).first()
        if payment:
            payment_name = payment.name

    company_config, invoice_pdf_config = _load_company_configs(db)

    referenced_invoice = None
    if (
        fiscal_document.document_type == "credit_note"
        and fiscal_document.id_fiscal_document_ref
    ):
        referenced_invoice = fiscal_repo.get_fiscal_document_by_id(
            fiscal_document.id_fiscal_document_ref
        )

    pdf_service = FiscalDocumentPDFService()
    pdf_bytes = pdf_service.generate_pdf(
        fiscal_document=fiscal_document,
        order=order,
        invoice_address=invoice_address,
        delivery_address=delivery_address,
        details_with_products=details_with_products,
        payment_name=payment_name,
        company_config=company_config,
        referenced_invoice=referenced_invoice,
        db=db,
        invoice_pdf_config=invoice_pdf_config,
    )

    doc_type = (
        "nota-credito" if fiscal_document.document_type == "credit_note" else "fattura"
    )
    doc_number = (
        fiscal_document.document_number
        or fiscal_document.internal_number
        or str(id_fiscal_document)
    )
    filename = f"{doc_type}-{doc_number}.pdf"
    return pdf_bytes, filename


def build_fiscal_document_pdf_buffer(
    db: Session,
    id_fiscal_document: int,
) -> Tuple[BytesIO, str]:
    """Wrapper che restituisce BytesIO per StreamingResponse."""
    pdf_bytes, filename = build_fiscal_document_pdf(db, id_fiscal_document)
    pdf_buffer = BytesIO()
    pdf_buffer.write(pdf_bytes)
    pdf_buffer.seek(0)
    return pdf_buffer, filename
