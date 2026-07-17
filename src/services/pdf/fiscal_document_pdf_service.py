"""
Servizio PDF per generazione documenti fiscali (fatture e note di credito).

Orchestrazione dati → FiscalDocumentPDFLayout (stile elettronew + i18n).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.pdf.base_pdf_service import BasePDFService
from src.services.pdf.fiscal_document_pdf_layout import FiscalDocumentPDFLayout
from src.services.pdf.i18n.invoice_pdf_labels import (
    DEFAULT_PRE_INVOICE_DISCLAIMER,
    get_invoice_labels,
)
from src.services.pdf.i18n.locale_resolver import (
    resolve_country_iso,
    resolve_invoice_locale,
)
from src.services.media.media_utils import get_store_logo_path
from src.services.ricevute.date_utils import format_emission_datetime


class FiscalDocumentPDFService(BasePDFService):
    """Servizio per generazione PDF di documenti fiscali (fattura / NC)."""

    @staticmethod
    def _as_float(value, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def generate_pdf(
        self,
        fiscal_document,
        order=None,
        invoice_address=None,
        delivery_address=None,
        details_with_products: Optional[List[Dict[str, Any]]] = None,
        payment_name: Optional[str] = None,
        company_config: Optional[Dict[str, Any]] = None,
        referenced_invoice=None,
        db=None,
        doc_title: Optional[str] = None,
        invoice_pdf_config: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Genera il PDF del documento fiscale in stile elettronew.

        Args:
            fiscal_document: FiscalDocument (fattura o nota di credito)
            order: Order collegato (opzionale)
            invoice_address / delivery_address: Address
            details_with_products: Lista dettagli con info prodotto
            payment_name: Nome metodo di pagamento
            company_config: Configurazioni aziendali (company_info)
            referenced_invoice: FiscalDocument di riferimento per NC
            db: Sessione DB (logo store)
            invoice_pdf_config: Config categoria invoice_pdf (dicitura NOTE)

        Returns:
            bytes: Contenuto PDF
        """
        if not fiscal_document:
            raise ValueError("fiscal_document è richiesto")
        if not details_with_products:
            raise ValueError("details_with_products è richiesto")
        if not company_config:
            raise ValueError("company_config è richiesto")

        try:
            context = self._build_context(
                fiscal_document=fiscal_document,
                order=order,
                invoice_address=invoice_address,
                delivery_address=delivery_address,
                details_with_products=details_with_products,
                payment_name=payment_name,
                company_config=company_config,
                referenced_invoice=referenced_invoice,
                db=db,
                invoice_pdf_config=invoice_pdf_config or {},
            )
            return FiscalDocumentPDFLayout.render_document(context)
        except ImportError:
            raise Exception(
                "Libreria fpdf2 non installata. Installare con: pip install fpdf2"
            )
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")

    def _build_context(
        self,
        *,
        fiscal_document,
        order,
        invoice_address,
        delivery_address,
        details_with_products: List[Dict[str, Any]],
        payment_name: Optional[str],
        company_config: Dict[str, Any],
        referenced_invoice,
        db,
        invoice_pdf_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        is_credit_note = fiscal_document.document_type == "credit_note"
        doc_number = (
            fiscal_document.document_number
            or fiscal_document.internal_number
            or "N/A"
        )
        doc_date = (
            format_emission_datetime(fiscal_document.date_add)
            if fiscal_document.date_add
            else ""
        )
        # Solo data (gg/mm/aaaa) per allineamento campioni
        if fiscal_document.date_add and hasattr(fiscal_document.date_add, "strftime"):
            doc_date = fiscal_document.date_add.strftime("%d/%m/%Y")

        country_iso = resolve_country_iso(invoice_address, delivery_address)
        locale = resolve_invoice_locale(country_iso)
        labels = get_invoice_labels(locale)

        logo_path = company_config.get("company_logo", "media/logos/logo.png")
        if getattr(fiscal_document, "id_store", None) and db:
            from src.models.store import Store
            import os

            store = (
                db.query(Store)
                .filter(Store.id_store == fiscal_document.id_store)
                .first()
            )
            if store:
                logo_path = get_store_logo_path(store, fallback_path=logo_path)
            if logo_path and not os.path.exists(logo_path):
                logo_path = None
        else:
            import os

            if logo_path and not os.path.exists(logo_path):
                logo_path = None

        # Dettagli normalizzati
        details: List[Dict[str, Any]] = []
        for d in details_with_products:
            qty = self._as_float(d.get("product_qty"), 0)
            unit_net = self._as_float(
                d.get("unit_price_net", d.get("unit_price")), 0
            )
            line_net = self._as_float(
                d.get("total_price_net", d.get("total_price_with_tax")), 0
            )
            # total_price_with_tax su FiscalDocumentDetail è spesso netto riga
            # (naming legacy); preferisci total_price_net se presente
            if d.get("total_price_net") is not None:
                line_net = self._as_float(d.get("total_price_net"), 0)
            vat_rate = self._as_float(d.get("vat_rate"), 0)
            details.append(
                {
                    "product_reference": d.get("product_reference") or "",
                    "product_name": d.get("product_name") or "",
                    "product_qty": qty,
                    "unit_price_net": unit_net,
                    "total_price_net": line_net,
                    "reduction_percent": self._as_float(
                        d.get("reduction_percent"), 0
                    ),
                    "vat_rate": vat_rate,
                    "vat_display": d.get("vat_display"),
                    "tax_note": (d.get("tax_note") or "").strip() or None,
                }
            )

        totals, vat_summary = self._compute_totals(
            fiscal_document=fiscal_document,
            order=order,
            details=details,
            db=db,
        )

        order_reference = "-"
        order_date: Optional[datetime] = None
        if order:
            order_reference = order.reference or str(order.id_order)
            order_date = order.date_add

        deadlines_text = ""
        if order and getattr(order, "payment_due_date", None):
            due = order.payment_due_date
            if hasattr(due, "strftime"):
                deadlines_text = due.strftime("%d/%m/%Y")
            else:
                deadlines_text = str(due)

        credit_note_ref_number = None
        credit_note_ref_date = None
        if is_credit_note and referenced_invoice:
            credit_note_ref_number = (
                referenced_invoice.document_number
                or referenced_invoice.internal_number
            )
            if referenced_invoice.date_add and hasattr(
                referenced_invoice.date_add, "strftime"
            ):
                credit_note_ref_date = referenced_invoice.date_add.strftime(
                    "%d/%m/%Y"
                )

        notes_text = self._build_notes_text(
            invoice_pdf_config=invoice_pdf_config,
            details=details,
        )

        return {
            "company_config": company_config,
            "logo_path": logo_path,
            "labels": labels,
            "locale": locale,
            "doc_number": doc_number,
            "doc_date": doc_date,
            "is_credit_note": is_credit_note,
            "credit_note_ref_number": credit_note_ref_number,
            "credit_note_ref_date": credit_note_ref_date,
            "credit_note_reason": getattr(
                fiscal_document, "credit_note_reason", None
            ),
            "invoice_address": invoice_address,
            "delivery_address": delivery_address,
            "order_reference": order_reference,
            "order_date": order_date,
            "details": details,
            "totals": totals,
            "vat_summary": vat_summary,
            "payment_name": payment_name or "-",
            "deadlines_text": deadlines_text,
            "notes_text": notes_text,
            "packages": 1,
        }

    def _compute_totals(
        self,
        *,
        fiscal_document,
        order,
        details: List[Dict[str, Any]],
        db,
    ) -> tuple:
        merchandise_net = sum(
            self._as_float(d.get("total_price_net"), 0) for d in details
        )
        if order and getattr(order, "products_total_price_net", None):
            merchandise_net = self._as_float(order.products_total_price_net)

        shipping_excl = 0.0
        shipping_incl = 0.0
        shipping_vat_rate = 0.0

        shipping = None
        if order and getattr(order, "shipments", None):
            shipping = order.shipments
        if shipping:
            shipping_excl = self._as_float(shipping.price_tax_excl)
            shipping_incl = self._as_float(shipping.price_tax_incl)
            if getattr(shipping, "id_tax", None) and db:
                from src.repository.tax_repository import TaxRepository

                tax_repo = TaxRepository(db)
                shipping_vat_rate = self._as_float(
                    tax_repo.get_percentage_by_id(shipping.id_tax)
                )
                if shipping_vat_rate and not shipping_incl and shipping_excl:
                    shipping_incl = shipping_excl * (
                        1 + shipping_vat_rate / 100.0
                    )

        # Raggruppa IVA per aliquota (merce)
        buckets: Dict[float, Dict[str, float]] = {}
        for d in details:
            rate = self._as_float(d.get("vat_rate"), 0)
            net = self._as_float(d.get("total_price_net"), 0)
            if rate not in buckets:
                buckets[rate] = {
                    "rate": rate,
                    "merchandise": 0.0,
                    "shipping": 0.0,
                    "vat": 0.0,
                }
            buckets[rate]["merchandise"] += net
            buckets[rate]["vat"] += net * (rate / 100.0)

        # Assegna spese trasporto all'aliquota spedizione (o prima aliquota)
        if shipping_excl:
            ship_rate = shipping_vat_rate
            if ship_rate not in buckets:
                buckets[ship_rate] = {
                    "rate": ship_rate,
                    "merchandise": 0.0,
                    "shipping": 0.0,
                    "vat": 0.0,
                }
            buckets[ship_rate]["shipping"] += shipping_excl
            buckets[ship_rate]["vat"] += shipping_excl * (ship_rate / 100.0)

        vat_summary = sorted(buckets.values(), key=lambda r: r["rate"])
        total_vat = sum(r["vat"] for r in vat_summary)

        taxable_total = merchandise_net + shipping_excl
        doc_total = self._as_float(
            getattr(fiscal_document, "total_price_with_tax", None)
        )
        if not doc_total and order:
            doc_total = self._as_float(order.total_price_with_tax)
        if not doc_total:
            doc_total = taxable_total + total_vat

        merchandise_gross = merchandise_net + sum(
            self._as_float(d.get("total_price_net"), 0)
            * (self._as_float(d.get("vat_rate"), 0) / 100.0)
            for d in details
        )

        total_weight = 0.0
        if order and getattr(order, "total_weight", None):
            total_weight = self._as_float(order.total_weight)

        totals = {
            "merchandise_net": merchandise_net,
            "shipping_incl": shipping_incl,
            "shipping_excl": shipping_excl,
            "taxable_total": taxable_total,
            "collection_fee": 0.0,
            "merchandise_gross": merchandise_gross,
            "total_vat": total_vat,
            "misc_fee": 0.0,
            "doc_total": doc_total,
            "total_weight": total_weight,
        }
        return totals, vat_summary

    @staticmethod
    def _build_notes_text(
        *,
        invoice_pdf_config: Dict[str, Any],
        details: List[Dict[str, Any]],
    ) -> str:
        disclaimer = (
            invoice_pdf_config.get("pre_invoice_disclaimer") or ""
        ).strip()
        if not disclaimer:
            disclaimer = DEFAULT_PRE_INVOICE_DISCLAIMER

        append_flag = str(
            invoice_pdf_config.get("append_tax_normative", "true")
        ).strip().lower()
        append = append_flag in ("1", "true", "yes", "si", "sì")

        parts = [disclaimer]
        if append:
            seen = set()
            for d in details:
                note = (d.get("tax_note") or "").strip()
                if note and note not in seen:
                    seen.add(note)
                    parts.append(note)

        return " ".join(parts)
