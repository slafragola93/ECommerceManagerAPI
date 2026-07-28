"""Generazione PDF reso (FiscalDocument document_type='return')."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import os

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from src.models.address import Address
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.models.store import Store
from src.models.tax import Tax
from src.services.media.media_utils import get_store_logo_path
from src.services.pdf.discount_display import resolve_line_discount
from src.services.pdf.reso_pdf_layout import ResoPDFLayout
from src.services.ricevute.order_lines import (
    build_shipping_line_dict,
    resolve_shipping_amounts,
)
from src.services.routers.order_document_service import OrderDocumentService


class ResoPDFService:
    """Orchestrazione dati → ResoPDFLayout."""

    @staticmethod
    def _as_float(value, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def build_details(
        self,
        db: Session,
        fiscal_document: FiscalDocument,
        order: Order,
        shipping: Optional[Shipping] = None,
    ) -> List[Dict[str, Any]]:
        details = (
            db.query(FiscalDocumentDetail)
            .filter(
                FiscalDocumentDetail.id_fiscal_document
                == fiscal_document.id_fiscal_document
            )
            .all()
        )

        od_ids = [d.id_order_detail for d in details if d.id_order_detail]
        order_details: Dict[int, OrderDetail] = {}
        if od_ids:
            for od in db.query(OrderDetail).filter(
                OrderDetail.id_order_detail.in_(od_ids)
            ):
                order_details[od.id_order_detail] = od

        tax_ids = {d.id_tax for d in details if d.id_tax}
        if shipping and getattr(shipping, "id_tax", None):
            tax_ids.add(shipping.id_tax)
        tax_map: Dict[int, Tax] = {}
        if tax_ids:
            for tax in db.query(Tax).filter(Tax.id_tax.in_(tax_ids)):
                tax_map[tax.id_tax] = tax

        rows: List[Dict[str, Any]] = []
        for detail in details:
            od = order_details.get(detail.id_order_detail)
            qty = self._as_float(detail.product_qty)
            unit_net = self._as_float(detail.unit_price_net)
            line_net = self._as_float(detail.total_price_net, unit_net * qty)

            reduction_percent = 0.0
            reduction_amount = 0.0
            if od:
                reduction_percent = self._as_float(od.reduction_percent)
                reduction_amount = self._as_float(od.reduction_amount)
                od_qty = self._as_float(od.product_qty)
                # Scalare importo sconto se reso parziale sulla riga
                if (
                    reduction_amount > 0
                    and od_qty > 0
                    and qty > 0
                    and qty + 1e-9 < od_qty
                ):
                    reduction_amount = reduction_amount * (qty / od_qty)

            line_discount, _ = resolve_line_discount(
                qty=qty,
                unit_net=unit_net,
                line_net=line_net,
                reduction_percent=reduction_percent,
                reduction_amount=reduction_amount,
            )

            tax = tax_map.get(detail.id_tax) if detail.id_tax else None
            vat_rate = self._as_float(tax.percentage) if tax else 0.0

            rows.append(
                {
                    "product_qty": qty,
                    "unit_price_net": unit_net,
                    "total_price_net": line_net,
                    "product_name": (od.product_name if od else None) or "N/A",
                    "product_reference": (od.product_reference if od else None) or "N/A",
                    "reduction_percent": reduction_percent,
                    "reduction_amount": reduction_amount,
                    "line_discount": line_discount,
                    "vat_rate": vat_rate,
                    "is_shipping": False,
                }
            )

        if fiscal_document.includes_shipping:
            shipping_line = build_shipping_line_dict(
                order, shipping, product_name="Spedizione", product_reference="SHIPPING"
            )
            if shipping_line:
                ship_tax = (
                    tax_map.get(shipping.id_tax)
                    if shipping and getattr(shipping, "id_tax", None)
                    else None
                )
                rows.append(
                    {
                        "product_qty": 1,
                        "unit_price_net": self._as_float(
                            shipping_line.get("unit_price_net")
                        ),
                        "total_price_net": self._as_float(
                            shipping_line.get("total_price_net")
                        ),
                        "product_name": shipping_line.get("product_name") or "Spedizione",
                        "product_reference": shipping_line.get("product_reference")
                        or "SHIPPING",
                        "reduction_percent": 0.0,
                        "reduction_amount": 0.0,
                        "line_discount": 0.0,
                        "vat_rate": self._as_float(
                            ship_tax.percentage if ship_tax else 0
                        ),
                        "is_shipping": True,
                    }
                )

        return rows

    def _compute_totals(
        self,
        fiscal_document: FiscalDocument,
        order: Order,
        details: List[Dict[str, Any]],
        shipping: Optional[Shipping] = None,
    ) -> Dict[str, float]:
        merchandise_net = sum(
            self._as_float(d.get("total_price_net"))
            for d in details
            if not d.get("is_shipping")
        )
        products_total = getattr(fiscal_document, "products_total_price_net", None)
        if products_total is not None:
            merchandise_net = self._as_float(products_total)

        shipping_net = 0.0
        shipping_incl = 0.0
        if fiscal_document.includes_shipping:
            shipping_net, shipping_incl = resolve_shipping_amounts(order, shipping)
            # Preferisci differenza documento se valorizzata
            doc_net = getattr(fiscal_document, "total_price_net", None)
            if doc_net is not None and products_total is not None:
                derived = max(
                    0.0, self._as_float(doc_net) - self._as_float(products_total)
                )
                if derived > 0:
                    shipping_net = derived
            doc_gross = getattr(fiscal_document, "total_price_with_tax", None)
            products_gross = getattr(
                fiscal_document, "products_total_price_with_tax", None
            )
            if doc_gross is not None and products_gross is not None:
                derived_g = max(
                    0.0, self._as_float(doc_gross) - self._as_float(products_gross)
                )
                if derived_g > 0:
                    shipping_incl = derived_g

        total_gross = self._as_float(fiscal_document.total_price_with_tax)
        if not total_gross:
            total_gross = self._as_float(order.total_price_with_tax)

        total_net = self._as_float(getattr(fiscal_document, "total_price_net", None))
        if not total_net:
            total_net = merchandise_net + shipping_net
        total_vat = max(total_gross - total_net, 0.0)

        total_discount = sum(
            self._as_float(d.get("line_discount"))
            for d in details
            if not d.get("is_shipping")
        )

        return {
            "merchandise_net": merchandise_net,
            "shipping_incl": shipping_incl,
            "shipping_net": shipping_net,
            "total_vat": total_vat,
            "total_gross": total_gross,
            "total_discount": total_discount,
        }

    def generate_reso_pdf(self, db: Session, id_fiscal_document: int) -> Tuple[bytes, str]:
        fiscal_document = (
            db.query(FiscalDocument)
            .filter(FiscalDocument.id_fiscal_document == id_fiscal_document)
            .first()
        )
        if not fiscal_document:
            raise HTTPException(
                status_code=404,
                detail=f"Documento fiscale {id_fiscal_document} non trovato",
            )
        if fiscal_document.document_type != "return":
            raise HTTPException(
                status_code=404,
                detail=f"Il documento {id_fiscal_document} non è un reso",
            )

        order = (
            db.query(Order).filter(Order.id_order == fiscal_document.id_order).first()
        )
        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"Ordine {fiscal_document.id_order} non trovato",
            )

        invoice_address = None
        delivery_address = None
        if order.id_address_invoice:
            invoice_address = (
                db.query(Address)
                .options(joinedload(Address.country))
                .filter(Address.id_address == order.id_address_invoice)
                .first()
            )
        if order.id_address_delivery:
            delivery_address = (
                db.query(Address)
                .options(joinedload(Address.country))
                .filter(Address.id_address == order.id_address_delivery)
                .first()
            )

        shipping = None
        if order.id_shipping:
            shipping = (
                db.query(Shipping)
                .filter(Shipping.id_shipping == order.id_shipping)
                .first()
            )

        details = self.build_details(db, fiscal_document, order, shipping)
        if not details:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Nessuna riga nel reso {id_fiscal_document}. "
                    "Impossibile generare PDF."
                ),
            )

        company_config = OrderDocumentService(db).get_company_info()
        logo_path = company_config.get("company_logo", "media/logos/logo.png")
        if order.id_store:
            store = db.query(Store).filter(Store.id_store == order.id_store).first()
            if store:
                logo_path = get_store_logo_path(store, fallback_path=logo_path)
        if logo_path and not os.path.exists(logo_path):
            logo_path = None

        doc_number = (
            fiscal_document.document_number
            or fiscal_document.internal_number
            or str(id_fiscal_document)
        )
        doc_date = fiscal_document.date_add or datetime.now()
        totals = self._compute_totals(fiscal_document, order, details, shipping)

        pdf = ResoPDFLayout.create_pdf()
        ResoPDFLayout.render(
            pdf,
            doc_number=str(doc_number),
            doc_date=doc_date,
            company_config=company_config,
            logo_path=logo_path,
            invoice_address=invoice_address,
            delivery_address=delivery_address or invoice_address,
            order_reference=order.reference or str(order.id_order),
            order_date=order.date_add or datetime.now(),
            details=details,
            totals=totals,
            note_text=getattr(fiscal_document, "credit_note_reason", None),
        )
        filename = f"reso-{doc_number}.pdf"
        return pdf.output(), filename


def build_reso_pdf_buffer(
    db: Session, id_fiscal_document: int
) -> Tuple[BytesIO, str]:
    """Wrapper StreamingResponse."""
    pdf_bytes, filename = ResoPDFService().generate_reso_pdf(db, id_fiscal_document)
    buf = BytesIO()
    buf.write(pdf_bytes)
    buf.seek(0)
    return buf, filename
