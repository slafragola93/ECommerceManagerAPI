"""Serializzazione lista/generica fiscal_documents con stati rapidi."""
from __future__ import annotations

from typing import Dict, Iterable, List

from sqlalchemy.orm import Session

from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.schemas.fiscal_document_schema import FiscalDocumentResponseSchema
from src.services.documents.quick_status import fiscal_quick_status_from_doc


def _batch_is_payed(db: Session, order_ids: Iterable[int]) -> Dict[int, bool]:
    ids = list({oid for oid in order_ids if oid})
    if not ids:
        return {}
    rows = (
        db.query(Order.id_order, Order.is_payed)
        .filter(Order.id_order.in_(ids))
        .all()
    )
    return {row.id_order: bool(row.is_payed) for row in rows}


def serialize_fiscal_document(
    doc: FiscalDocument,
    *,
    is_payed: bool = False,
) -> FiscalDocumentResponseSchema:
    qs = fiscal_quick_status_from_doc(doc)
    return FiscalDocumentResponseSchema(
        id_fiscal_document=doc.id_fiscal_document,
        document_type=doc.document_type,
        tipo_documento_fe=doc.tipo_documento_fe,
        id_order=doc.id_order,
        id_fiscal_document_ref=doc.id_fiscal_document_ref,
        document_number=doc.document_number,
        internal_number=doc.internal_number,
        filename=doc.filename,
        xml_content=doc.xml_content,
        status=doc.status,
        is_electronic=bool(doc.is_electronic),
        upload_result=doc.upload_result,
        credit_note_reason=doc.credit_note_reason,
        is_partial=bool(doc.is_partial) if doc.is_partial is not None else False,
        total_price_with_tax=doc.total_price_with_tax,
        total_price_net=doc.total_price_net,
        products_total_price_net=doc.products_total_price_net,
        products_total_price_with_tax=doc.products_total_price_with_tax,
        date_add=doc.date_add,
        date_upd=doc.date_upd,
        is_payed=is_payed,
        **qs,
    )


def serialize_fiscal_documents(
    db: Session, documents: List[FiscalDocument]
) -> List[FiscalDocumentResponseSchema]:
    payed_map = _batch_is_payed(db, (d.id_order for d in documents))
    return [
        serialize_fiscal_document(
            doc, is_payed=payed_map.get(doc.id_order, False)
        )
        for doc in documents
    ]
