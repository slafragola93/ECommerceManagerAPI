"""Stato di storno fattura: calcolato dalle NC collegate, non persistito."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail

STATO_STORNO_NON = "non_stornata"
STATO_STORNO_PARZIALE = "parziale"
STATO_STORNO_TOTALE = "totale"


def resolve_stato_storno(
    *,
    has_credit_notes: bool,
    has_total_credit_note: bool,
    residual_zero: bool,
) -> str:
    """non_stornata | parziale | totale."""
    if not has_credit_notes:
        return STATO_STORNO_NON
    if has_total_credit_note or residual_zero:
        return STATO_STORNO_TOTALE
    return STATO_STORNO_PARZIALE


def residual_stornabile_zero(
    *,
    invoice_includes_shipping: bool,
    shipping_already_refunded: bool,
    invoice_qtys: Dict[int, float],
    refunded_qtys: Dict[int, float],
) -> bool:
    """True se qty residue e spedizione stornabile sono già a zero."""
    lines_remaining = any(
        float(qty or 0) - float(refunded_qtys.get(oid, 0) or 0) > 0
        for oid, qty in invoice_qtys.items()
        if oid
    )
    shipping_remaining = bool(invoice_includes_shipping) and not shipping_already_refunded
    return (not lines_remaining) and (not shipping_remaining)


def load_stato_storno_map(
    db: Session, documents: Iterable[FiscalDocument]
) -> Dict[int, str]:
    """invoice id → stato_storno. Una query NC + due sui dettagli, niente N+1."""
    invoices = [d for d in documents if d.document_type == "invoice"]
    if not invoices:
        return {}

    invoice_ids = [d.id_fiscal_document for d in invoices]
    credit_notes: List[FiscalDocument] = (
        db.query(FiscalDocument)
        .filter(
            FiscalDocument.document_type == "credit_note",
            FiscalDocument.id_fiscal_document_ref.in_(invoice_ids),
        )
        .all()
    )

    cns_by_invoice: Dict[int, List[FiscalDocument]] = {i: [] for i in invoice_ids}
    for cn in credit_notes:
        if cn.id_fiscal_document_ref:
            cns_by_invoice.setdefault(cn.id_fiscal_document_ref, []).append(cn)

    qtys_by_invoice: Dict[int, Dict[int, float]] = defaultdict(dict)
    invoice_details = (
        db.query(
            FiscalDocumentDetail.id_fiscal_document,
            FiscalDocumentDetail.id_order_detail,
            FiscalDocumentDetail.product_qty,
        )
        .filter(FiscalDocumentDetail.id_fiscal_document.in_(invoice_ids))
        .all()
    )
    for id_doc, id_od, qty in invoice_details:
        if not id_od:
            continue
        current = qtys_by_invoice[id_doc].get(id_od, 0.0)
        qtys_by_invoice[id_doc][id_od] = current + float(qty or 0)

    refunded_by_invoice: Dict[int, Dict[int, float]] = defaultdict(dict)
    cn_ids = [cn.id_fiscal_document for cn in credit_notes]
    if cn_ids:
        cn_ref = {cn.id_fiscal_document: cn.id_fiscal_document_ref for cn in credit_notes}
        nc_details = (
            db.query(
                FiscalDocumentDetail.id_fiscal_document,
                FiscalDocumentDetail.id_order_detail,
                FiscalDocumentDetail.product_qty,
            )
            .filter(FiscalDocumentDetail.id_fiscal_document.in_(cn_ids))
            .all()
        )
        for id_cn, id_od, qty in nc_details:
            id_inv = cn_ref.get(id_cn)
            if not id_inv or not id_od:
                continue
            current = refunded_by_invoice[id_inv].get(id_od, 0.0)
            refunded_by_invoice[id_inv][id_od] = current + float(qty or 0)

    result: Dict[int, str] = {}
    for inv in invoices:
        cns = cns_by_invoice.get(inv.id_fiscal_document, [])
        result[inv.id_fiscal_document] = resolve_stato_storno(
            has_credit_notes=bool(cns),
            has_total_credit_note=any(not cn.is_partial for cn in cns),
            residual_zero=residual_stornabile_zero(
                invoice_includes_shipping=bool(inv.includes_shipping),
                shipping_already_refunded=any(cn.includes_shipping for cn in cns),
                invoice_qtys=qtys_by_invoice.get(inv.id_fiscal_document, {}),
                refunded_qtys=refunded_by_invoice.get(inv.id_fiscal_document, {}),
            ),
        )
    return result


def stato_storno_for_invoice(
    db: Session, invoice: FiscalDocument
) -> Optional[str]:
    if invoice.document_type != "invoice":
        return None
    return load_stato_storno_map(db, [invoice]).get(
        invoice.id_fiscal_document, STATO_STORNO_NON
    )
