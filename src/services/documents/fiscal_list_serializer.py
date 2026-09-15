"""Serializzazione lista/generica fiscal_documents con stati rapidi.

Pagamento principale: `orders.id_payment` → `payments.name` (stesso criterio
PDF / dettaglio ordine). Se manca, ultimo incasso `order_payments.is_paid=true`
ordinato per `payment_date` / `date_add` / `id_order_payment` desc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from src.models.address import Address
from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.models.order_payment import OrderPayment
from src.models.payment import Payment
from src.models.app_configuration import AppConfiguration
from src.schemas.fiscal_document_schema import FiscalDocumentResponseSchema
from src.services.documents.quick_status import (
    fiscal_lifecycle_from_doc,
    fiscal_quick_status_from_doc,
)
from src.services.documents.stato_storno import load_stato_storno_map
from src.services.external.fatturapa_filename import compute_fatturapa_response_filename


@dataclass(frozen=True)
class _OrderListContext:
    is_payed: bool
    id_order_payment: Optional[int]
    order_payment_name: Optional[str]
    id_customer: Optional[int]
    customer_name: Optional[str]
    order_shipped: bool


def _display_customer_name(
    company: Optional[str],
    firstname: Optional[str],
    lastname: Optional[str],
) -> Optional[str]:
    company_s = (company or "").strip()
    if company_s:
        return company_s
    last = (lastname or "").strip()
    first = (firstname or "").strip()
    if last and first:
        return f"{last} {first}"
    return last or first or None


def _batch_order_list_context(
    db: Session, order_ids: Iterable[int]
) -> Dict[int, _OrderListContext]:
    ids = list({oid for oid in order_ids if oid})
    if not ids:
        return {}

    rows = (
        db.query(
            Order.id_order,
            Order.id_payment,
            Order.is_payed,
            Order.id_customer,
            Order.id_shipping,
            Payment.name,
            Customer.firstname,
            Customer.lastname,
            Address.company,
        )
        .outerjoin(Payment, Payment.id_payment == Order.id_payment)
        .outerjoin(Customer, Customer.id_customer == Order.id_customer)
        .outerjoin(Address, Address.id_address == Order.id_address_invoice)
        .filter(Order.id_order.in_(ids))
        .all()
    )

    ctx: Dict[int, _OrderListContext] = {}
    missing_payment: List[int] = []
    for (
        id_order,
        id_payment,
        is_payed,
        id_customer,
        id_shipping,
        payment_name,
        firstname,
        lastname,
        company,
    ) in rows:
        name = (payment_name or "").strip() or None
        ctx[id_order] = _OrderListContext(
            is_payed=bool(is_payed),
            id_order_payment=id_payment if id_payment else None,
            order_payment_name=name,
            id_customer=id_customer,
            customer_name=_display_customer_name(company, firstname, lastname),
            order_shipped=bool(id_shipping),
        )
        if not id_payment:
            missing_payment.append(id_order)

    if missing_payment:
        fallbacks = (
            db.query(
                OrderPayment.id_order,
                OrderPayment.id_payment,
                OrderPayment.payment_date,
                OrderPayment.date_add,
                OrderPayment.id_order_payment,
                Payment.name,
            )
            .join(Payment, Payment.id_payment == OrderPayment.id_payment)
            .filter(
                OrderPayment.id_order.in_(missing_payment),
                OrderPayment.is_paid.is_(True),
            )
            .all()
        )
        best: Dict[int, tuple] = {}
        for row in fallbacks:
            key = (
                row.payment_date or row.date_add,
                row.date_add,
                row.id_order_payment,
            )
            prev = best.get(row.id_order)
            if prev is None or key > prev[0]:
                best[row.id_order] = (key, row.id_payment, (row.name or "").strip() or None)
        for oid, (_, id_payment, name) in best.items():
            current = ctx.get(oid)
            if not current:
                continue
            ctx[oid] = _OrderListContext(
                is_payed=current.is_payed,
                id_order_payment=id_payment,
                order_payment_name=name,
                id_customer=current.id_customer,
                customer_name=current.customer_name,
                order_shipped=current.order_shipped,
            )

    return ctx


def load_company_vat_number(db: Session) -> Optional[str]:
    row = (
        db.query(AppConfiguration.value)
        .filter(
            AppConfiguration.category == "company_info",
            AppConfiguration.name == "vat_number",
        )
        .first()
    )
    return (row[0] or "").strip() or None if row else None


def serialize_fiscal_document(
    doc: FiscalDocument,
    *,
    is_payed: bool = False,
    order_payment_name: Optional[str] = None,
    id_order_payment: Optional[int] = None,
    id_customer: Optional[int] = None,
    customer_name: Optional[str] = None,
    order_shipped: bool = False,
    include_xml: bool = False,
    vat_number: Optional[str] = None,
    stato_storno: Optional[str] = None,
) -> FiscalDocumentResponseSchema:
    qs = fiscal_quick_status_from_doc(doc)
    electronic = bool(doc.is_electronic)
    is_invoice = doc.document_type == "invoice"
    is_credit_note = doc.document_type == "credit_note"
    if not electronic:
        qs["identificativo_sdi"] = None
    return FiscalDocumentResponseSchema(
        id_fiscal_document=doc.id_fiscal_document,
        document_type=doc.document_type,
        tipo_documento_fe=doc.tipo_documento_fe,
        id_order=doc.id_order,
        id_fiscal_document_ref=doc.id_fiscal_document_ref if is_credit_note else None,
        document_number=doc.document_number,
        progressivo_invio=getattr(doc, "progressivo_invio", None),
        internal_number=doc.internal_number,
        filename=compute_fatturapa_response_filename(
            progressivo_invio=getattr(doc, "progressivo_invio", None),
            vat_number=vat_number,
            stored_filename=doc.filename,
        ),
        xml_content=doc.xml_content if include_xml else None,
        status=doc.status,
        is_electronic=electronic,
        credit_note_reason=doc.credit_note_reason if not is_invoice else None,
        is_partial=bool(doc.is_partial) if not is_invoice else None,
        includes_shipping=bool(doc.includes_shipping),
        stato_storno=stato_storno if is_invoice else None,
        total_price_with_tax=doc.total_price_with_tax,
        total_price_net=doc.total_price_net,
        products_total_price_net=doc.products_total_price_net,
        products_total_price_with_tax=doc.products_total_price_with_tax,
        date_add=doc.date_add,
        date_upd=doc.date_upd,
        is_payed=is_payed,
        sdi_status=getattr(doc, "sdi_status", None) if electronic else None,
        order_payment_name=order_payment_name,
        id_order_payment=id_order_payment,
        id_customer=id_customer,
        customer_name=customer_name,
        order_shipped=order_shipped,
        lifecycle=fiscal_lifecycle_from_doc(doc, qs),
        **qs,
    )


def serialize_fiscal_documents(
    db: Session,
    documents: List[FiscalDocument],
    *,
    include_xml: bool = False,
) -> List[FiscalDocumentResponseSchema]:
    ctx_map = _batch_order_list_context(db, (d.id_order for d in documents))
    stato_map = load_stato_storno_map(db, documents)
    vat_number = load_company_vat_number(db)
    empty = _OrderListContext(
        is_payed=False,
        id_order_payment=None,
        order_payment_name=None,
        id_customer=None,
        customer_name=None,
        order_shipped=False,
    )
    return [
        serialize_fiscal_document(
            doc,
            is_payed=ctx_map.get(doc.id_order, empty).is_payed,
            order_payment_name=ctx_map.get(doc.id_order, empty).order_payment_name,
            id_order_payment=ctx_map.get(doc.id_order, empty).id_order_payment,
            id_customer=ctx_map.get(doc.id_order, empty).id_customer,
            customer_name=ctx_map.get(doc.id_order, empty).customer_name,
            order_shipped=ctx_map.get(doc.id_order, empty).order_shipped,
            include_xml=include_xml,
            vat_number=vat_number,
            stato_storno=stato_map.get(doc.id_fiscal_document),
        )
        for doc in documents
    ]
