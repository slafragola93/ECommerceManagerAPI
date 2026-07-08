"""Generazione PDF ricevute — layout elettronew dedicato (no SDI)."""
from datetime import datetime
from typing import Any, Dict, List

import os

from sqlalchemy.orm import Session, joinedload

from src.models.address import Address
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.payment import Payment
from src.models.ricevuta import Ricevuta
from src.models.tax import Tax
from src.services.media.media_utils import get_store_logo_path
from src.services.pdf.base_pdf_service import BasePDFService
from src.services.pdf.ricevuta_pdf_layout import (
    RicevutaPDFLayout,
    _resolve_iso_code,
)
from src.services.routers.order_document_service import OrderDocumentService


class RicevutaPDFService(BasePDFService):
    def build_details_with_products(
        self, db: Session, id_order: int, locale_iso: str | None = None
    ) -> List[Dict[str, Any]]:
        details = db.query(OrderDetail).filter(OrderDetail.id_order == id_order).all()
        rows: List[Dict[str, Any]] = []
        tax_ids = {d.id_tax for d in details if d.id_tax}
        tax_map: Dict[int, Tax] = {}
        if tax_ids:
            for tax in (
                db.query(Tax)
                .options(joinedload(Tax.country))
                .filter(Tax.id_tax.in_(tax_ids))
                .all()
            ):
                tax_map[tax.id_tax] = tax

        for detail in details:
            if detail.id_order_document:
                continue
            tax = tax_map.get(detail.id_tax) if detail.id_tax else None
            vat_rate = float(tax.percentage or 0) if tax else 0.0
            tax_code = tax.code if tax and tax.code else None
            if not locale_iso and tax and tax.country and tax.country.iso_code:
                locale_iso = str(tax.country.iso_code).upper()

            qty = float(detail.product_qty or 0)
            unit_net = float(detail.unit_price_net or 0)
            line_net = float(detail.total_price_net or (unit_net * qty))

            rows.append(
                {
                    "product_qty": detail.product_qty or 0,
                    "unit_price": unit_net,
                    "total_price_net": line_net,
                    "product_name": detail.product_name or "N/A",
                    "product_reference": detail.product_reference or "N/A",
                    "reduction_percent": float(detail.reduction_percent or 0),
                    "vat_rate": vat_rate,
                    "tax_code": tax_code,
                }
            )
        return rows

    @staticmethod
    def _compute_totals(order: Order, details: List[Dict[str, Any]]) -> Dict[str, float]:
        merchandise_net = float(order.products_total_price_net or 0)
        if merchandise_net <= 0 and details:
            merchandise_net = sum(float(d.get("total_price_net") or 0) for d in details)

        shipping_incl = 0.0
        shipping_net = 0.0
        if hasattr(order, "shipments") and order.shipments:
            shipping_incl = float(order.shipments.price_tax_incl or 0)
            shipping_net = float(order.shipments.price_tax_excl or 0)

        total_gross = float(order.total_price_with_tax or 0)
        total_net = float(order.total_price_net or 0)
        if total_net <= 0:
            total_net = merchandise_net + shipping_net
        total_vat = max(total_gross - total_net, 0.0)

        return {
            "merchandise_net": merchandise_net,
            "shipping_incl": shipping_incl,
            "payment_fee": 0.0,
            "total_vat": total_vat,
            "total_gross": total_gross,
        }

    def generate_pdf(self, *args, **kwargs) -> bytes:
        raise NotImplementedError("Usare generate_ricevuta_pdf")

    def generate_ricevuta_pdf(
        self,
        db: Session,
        ricevuta: Ricevuta,
        order: Order,
    ) -> bytes:
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

        payment_name = "-"
        if order.id_payment:
            payment = (
                db.query(Payment).filter(Payment.id_payment == order.id_payment).first()
            )
            if payment and payment.name:
                payment_name = payment.name

        locale_iso = _resolve_iso_code(invoice_address, delivery_address)
        details_with_products = self.build_details_with_products(
            db, order.id_order, locale_iso=locale_iso
        )
        if not details_with_products:
            raise ValueError("Nessuna riga ordine disponibile per generare la ricevuta")

        company_config = OrderDocumentService(db).get_company_info()
        logo_path = company_config.get("company_logo", "media/logos/logo.png")
        if order.id_store:
            from src.models.store import Store

            store = db.query(Store).filter(Store.id_store == order.id_store).first()
            if store:
                logo_path = get_store_logo_path(store, fallback_path=logo_path)

        pdf = RicevutaPDFLayout.create_pdf()
        RicevutaPDFLayout.render(
            pdf,
            ricevuta_numero=ricevuta.numero,
            ricevuta_anno=ricevuta.anno,
            data_emissione=datetime.combine(
                ricevuta.data_emissione, datetime.min.time()
            ),
            company_config=company_config,
            logo_path=logo_path if logo_path and os.path.exists(logo_path) else None,
            invoice_address=invoice_address,
            delivery_address=delivery_address or invoice_address,
            order_reference=order.reference or str(order.id_order),
            order_date=order.date_add or datetime.now(),
            details=details_with_products,
            payment_name=payment_name,
            totals=self._compute_totals(order, details_with_products),
            note_text=(order.general_note or "").strip(),
            locale_iso=locale_iso,
        )
        return pdf.output()
