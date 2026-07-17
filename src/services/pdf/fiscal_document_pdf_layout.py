"""
Layout PDF fattura / nota di credito — stile elettronew (B/N).

Allineato ai campioni cartacei: logo + anagrafica, titolo FATTURA/FACTURE,
Intestazione / consegna, tabella Impon./IVA, info spedizione, riepilogo IVA,
totali, pagamento, firme, NOTE precompilate. Multipagina con header ripetuto.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import os

from src.services.pdf.order_pdf_service import (
    CONTENT_W,
    CONTENT_X,
    COL_LEFT_W,
    COL_RIGHT_W,
    COL_RIGHT_X,
    MARGIN,
    PAGE_RIGHT,
    OrderPDFService,
    _fit_cell_text,
    _fmt_eur,
    _fmt_num,
    _fmt_pct,
    _fmt_qty,
    _safe,
    _wrap_description,
)
from src.services.ricevute.date_utils import format_emission_datetime

# Colonne tabella (totale = CONTENT_W 190 mm) — allineate a order PDF
_ITEM_COLS = [28, 52, 24, 14, 20, 16, 36]
_ITEM_ALIGN = ["L", "L", "R", "R", "R", "R", "R"]
_ITEM_ROW_H = 5.0
_ITEM_FONT_SIZE = 8
_HEADER_TOP_MARGIN = 10
_HEADER_BOTTOM_Y = 78  # spazio riservato all'header ripetuto


class InvoiceFPDF:
    """Factory: crea FPDF con header/footer per fattura multipagina."""

    @staticmethod
    def create(
        *,
        margin: int = MARGIN,
        labels: Dict[str, Any],
        company_config: Dict[str, Any],
        logo_path: Optional[str],
        doc_title: str,
        doc_number_line: str,
        credit_note_ref: Optional[str],
        invoice_address,
        delivery_address,
        item_headers: List[str],
    ):
        from fpdf import FPDF

        class _InvoicePDF(FPDF):
            def header(self):
                FiscalDocumentPDFLayout._draw_repeating_header(
                    self,
                    company_config=company_config,
                    logo_path=logo_path,
                    doc_title=doc_title,
                    doc_number_line=doc_number_line,
                    credit_note_ref=credit_note_ref,
                    invoice_address=invoice_address,
                    delivery_address=delivery_address,
                    billing_label=labels["billing"],
                    delivery_label=labels["delivery"],
                    item_headers=item_headers,
                )

            def footer(self):
                self.set_y(-12)
                self.set_font("Arial", "", 8)
                self.set_text_color(0, 0, 0)
                text = labels["page_footer"].format(
                    page=self.page_no(),
                    total="{nb}",
                )
                self.set_x(CONTENT_X)
                self.cell(CONTENT_W, 4, _safe(text), 0, 0, "L")

        pdf = _InvoicePDF()
        try:
            pdf.core_fonts_encoding = "cp1252"
        except Exception:
            pass
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_left_margin(MARGIN)
        pdf.set_right_margin(MARGIN)
        pdf.add_page()
        return pdf


class FiscalDocumentPDFLayout:
    """Disegna il PDF fattura su un'istanza FPDF già creata (o via render_document)."""

    @classmethod
    def render_document(cls, context: Dict[str, Any]) -> bytes:
        """
        Genera PDF completo da un context dict.

        Chiavi attese:
          company_config, logo_path, labels, locale,
          doc_title, doc_number, doc_date,
          is_credit_note, credit_note_ref_number, credit_note_ref_date,
          credit_note_reason,
          invoice_address, delivery_address,
          order_reference, order_date,
          details (list of dict),
          totals (dict),
          vat_summary (list of {rate, merchandise, shipping, vat}),
          payment_name, deadlines_text,
          notes_text,
          packages (int, default 1)
        """
        labels = context["labels"]
        is_credit_note = bool(context.get("is_credit_note"))
        doc_title = (
            labels["credit_note_title"] if is_credit_note else labels["doc_title"]
        )
        doc_number = str(context.get("doc_number") or "N/A")
        doc_date = context.get("doc_date") or ""
        doc_number_line = labels["doc_number_date"].format(
            number=doc_number, date=doc_date
        )

        credit_note_ref = None
        if is_credit_note and context.get("credit_note_ref_number"):
            credit_note_ref = labels["credit_note_ref"].format(
                number=context["credit_note_ref_number"],
                date=context.get("credit_note_ref_date") or "",
            )

        pdf = InvoiceFPDF.create(
            labels=labels,
            company_config=context.get("company_config") or {},
            logo_path=context.get("logo_path"),
            doc_title=doc_title,
            doc_number_line=doc_number_line,
            credit_note_ref=credit_note_ref,
            invoice_address=context.get("invoice_address"),
            delivery_address=context.get("delivery_address"),
            item_headers=labels["item_headers"],
        )

        cls._draw_order_reference(
            pdf,
            labels["order_ref"].format(
                reference=context.get("order_reference") or "-",
                date=cls._format_date(context.get("order_date")),
            ),
        )

        total_qty = cls._draw_items_table(
            pdf,
            details=context.get("details") or [],
        )

        cls._draw_horizontal_rule(pdf, thick=False)
        pdf.ln(2)

        totals = context.get("totals") or {}
        cls._draw_shipping_info(
            pdf,
            labels=labels,
            total_qty=total_qty,
            total_weight=float(totals.get("total_weight") or 0),
            packages=int(context.get("packages") or 1),
        )
        pdf.ln(2)

        cls._draw_vat_and_totals(
            pdf,
            labels=labels,
            vat_summary=context.get("vat_summary") or [],
            totals=totals,
        )
        pdf.ln(2)

        cls._draw_payment_section(
            pdf,
            labels=labels,
            payment_text=context.get("payment_name") or "-",
            deadlines_text=context.get("deadlines_text") or "",
        )
        pdf.ln(2)

        cls._draw_transport_signatures(pdf, labels=labels)
        pdf.ln(3)

        if is_credit_note and context.get("credit_note_reason"):
            pdf.set_font("Arial", "B", 8)
            pdf.set_x(CONTENT_X)
            pdf.cell(0, 4, _safe(labels["credit_note_reason"]), 0, 1, "L")
            pdf.set_font("Arial", "", 8)
            pdf.set_x(CONTENT_X)
            pdf.multi_cell(CONTENT_W, 4, _safe(context["credit_note_reason"]), 0, "L")
            pdf.ln(1)

        notes_text = (context.get("notes_text") or "").strip()
        cls._draw_notes(pdf, labels=labels, notes_text=notes_text)

        return pdf.output()

    # ------------------------------------------------------------------
    # Header ripetuto
    # ------------------------------------------------------------------

    @classmethod
    def _draw_repeating_header(
        cls,
        pdf,
        *,
        company_config: Dict[str, Any],
        logo_path: Optional[str],
        doc_title: str,
        doc_number_line: str,
        credit_note_ref: Optional[str],
        invoice_address,
        delivery_address,
        billing_label: str,
        delivery_label: str,
        item_headers: List[str],
    ) -> None:
        y0 = _HEADER_TOP_MARGIN

        if logo_path and os.path.exists(logo_path):
            try:
                pdf.image(logo_path, x=CONTENT_X, y=y0, w=42)
            except Exception:
                pass

        pdf.set_xy(CONTENT_X, y0 + 18)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(40, 40, 40)
        for line in cls._company_lines(company_config):
            pdf.set_x(CONTENT_X)
            pdf.cell(COL_LEFT_W, 3.6, _safe(line), 0, 1, "L")

        pdf.set_xy(COL_RIGHT_X, y0 + 8)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(COL_RIGHT_W, 7, _safe(doc_title), 0, 1, "R")

        pdf.set_font("Arial", "", 10)
        pdf.set_x(COL_RIGHT_X)
        pdf.cell(COL_RIGHT_W, 5, _safe(doc_number_line), 0, 1, "R")

        if credit_note_ref:
            pdf.set_font("Arial", "I", 8)
            pdf.set_x(COL_RIGHT_X)
            pdf.cell(COL_RIGHT_W, 4, _safe(credit_note_ref), 0, 1, "R")

        pdf.set_y(max(pdf.get_y(), y0 + 40))
        pdf.ln(2)

        cls._draw_address_columns(
            pdf,
            invoice_address=invoice_address,
            delivery_address=delivery_address,
            billing_label=billing_label,
            delivery_label=delivery_label,
        )
        pdf.ln(2)
        cls._draw_horizontal_rule(pdf, thick=False)
        cls._draw_items_table_header(pdf, item_headers)

    @staticmethod
    def _company_lines(config: Dict[str, Any]) -> List[str]:
        """Anagrafica società stile campione (righe separate + BIC)."""
        lines: List[str] = []
        if config.get("company_name"):
            lines.append(str(config["company_name"]))

        address = (config.get("address") or "").strip()
        civic = (config.get("civic_number") or "").strip()
        if address and civic:
            lines.append(f"{address} {civic}".strip())
        elif address:
            lines.append(address)

        cap = (config.get("postal_code") or "").strip()
        city = (config.get("city") or "").strip()
        province = (config.get("province") or "").strip()
        city_parts = []
        if cap and city:
            city_parts.append(f"{cap} - {city}")
        elif city:
            city_parts.append(city)
        elif cap:
            city_parts.append(cap)
        if province and city_parts:
            city_parts[0] = f"{city_parts[0]} ({province})"
        elif province:
            city_parts.append(f"({province})")
        if city_parts:
            lines.append(city_parts[0])

        fiscal = []
        if config.get("vat_number"):
            fiscal.append(f"P.I. {config['vat_number']}")
        if config.get("fiscal_code"):
            fiscal.append(f"C.F. {config['fiscal_code']}")
        if fiscal:
            lines.append(" - ".join(fiscal))

        if config.get("iban"):
            lines.append(f"IBAN {config['iban']}")
        if config.get("bic_swift"):
            lines.append(f"BIC/SWIFT {config['bic_swift']}")

        return lines or ["-"]

    @staticmethod
    def _draw_address_columns(
        pdf,
        invoice_address,
        delivery_address,
        billing_label: str,
        delivery_label: str,
    ) -> None:
        y_start = pdf.get_y()

        pdf.set_xy(CONTENT_X, y_start)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(COL_LEFT_W, 5, _safe(billing_label), 0, 1, "L")

        pdf.set_font("Arial", "", 8.5)
        for line in OrderPDFService._format_invoice_lines(invoice_address):
            pdf.set_x(CONTENT_X)
            pdf.cell(COL_LEFT_W, 4.0, _safe(line), 0, 1, "L")
        y_left = pdf.get_y()

        pdf.set_xy(COL_RIGHT_X, y_start)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(COL_RIGHT_W, 5, _safe(delivery_label), 0, 1, "R")

        pdf.set_font("Arial", "", 8.5)
        for line in FiscalDocumentPDFLayout._format_delivery_lines(delivery_address):
            pdf.set_x(COL_RIGHT_X)
            pdf.cell(COL_RIGHT_W, 4.0, _safe(line), 0, 1, "R")
        y_right = pdf.get_y()

        pdf.set_y(max(y_left, y_right, y_start + 26))

    @staticmethod
    def _format_delivery_lines(address) -> List[str]:
        if not address:
            return ["-"]
        lines: List[str] = []
        name = OrderPDFService._person_name(address)
        if name:
            lines.append(name)
        if getattr(address, "company", None):
            lines.append(str(address.company))
        addr1 = getattr(address, "address1", None) or ""
        addr2 = getattr(address, "address2", None) or ""
        street = " ".join(p for p in [addr1, addr2] if p).strip()
        if street:
            lines.append(street)

        country_name = ""
        country = getattr(address, "country", None)
        if country and getattr(country, "name", None):
            country_name = country.name

        city_bits = []
        if getattr(address, "city", None):
            city_bits.append(str(address.city))
        state = getattr(address, "state", None)
        if state:
            city_bits.append(f"({state})")
        city_line = " ".join(city_bits)
        if country_name:
            city_line = f"{city_line} {country_name}".strip()
        if city_line:
            lines.append(city_line)
        return lines or ["-"]

    # ------------------------------------------------------------------
    # Corpo documento
    # ------------------------------------------------------------------

    @staticmethod
    def _draw_horizontal_rule(pdf, thick: bool = False) -> None:
        y = pdf.get_y()
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.6 if thick else 0.2)
        pdf.line(CONTENT_X, y, PAGE_RIGHT, y)
        pdf.set_line_width(0.2)
        pdf.ln(1.5 if thick else 1)

    @staticmethod
    def _draw_order_reference(pdf, text: str) -> None:
        pdf.set_font("Arial", "B", 9)
        pdf.set_x(CONTENT_X)
        pdf.cell(CONTENT_W, 5, _safe(text), 0, 1, "L")
        pdf.ln(1)

    @staticmethod
    def _draw_items_table_header(pdf, headers: List[str]) -> None:
        pdf.set_font("Arial", "B", _ITEM_FONT_SIZE)
        header_y = pdf.get_y()
        x = CONTENT_X
        for i, header in enumerate(headers):
            pdf.set_xy(x, header_y)
            label = _fit_cell_text(pdf, header, _ITEM_COLS[i])
            pdf.cell(_ITEM_COLS[i], _ITEM_ROW_H, label, 0, 0, _ITEM_ALIGN[i])
            x += _ITEM_COLS[i]
        pdf.ln(_ITEM_ROW_H + 1)

    @classmethod
    def _draw_items_table(
        cls,
        pdf,
        details: List[Dict[str, Any]],
    ) -> int:
        pdf.set_font("Arial", "", _ITEM_FONT_SIZE)
        total_qty = 0
        if not details:
            pdf.set_x(CONTENT_X)
            pdf.cell(CONTENT_W, _ITEM_ROW_H, "-", 0, 1, "L")
            return 0

        desc_width = _ITEM_COLS[1]
        line_h = 4.2
        align = _ITEM_ALIGN

        for detail in details:
            qty = float(detail.get("product_qty") or 0)
            total_qty += int(qty) if qty == int(qty) else int(qty)
            unit_net = float(
                detail.get("unit_price_net")
                or detail.get("unit_price")
                or detail.get("imponibile")
                or 0
            )
            line_net = float(
                detail.get("total_price_net")
                or detail.get("line_net")
                or detail.get("total_price_with_tax")
                or 0
            )
            reduction_pct = float(detail.get("reduction_percent") or 0)
            vat_rate = float(detail.get("vat_rate") or 0)
            vat_label = detail.get("vat_display")
            if not vat_label:
                vat_label = (
                    _fmt_num(vat_rate, 0) if vat_rate else "0"
                )

            # Imponibile unitario: se manca, deriva dal totale riga
            if not unit_net and line_net and qty:
                unit_net = line_net / qty

            code_text = _fit_cell_text(
                pdf, str(detail.get("product_reference") or ""), _ITEM_COLS[0]
            )
            desc_lines = _wrap_description(
                pdf,
                str(detail.get("product_name") or ""),
                desc_width,
                max_lines=2,
            )
            row_h = max(_ITEM_ROW_H, line_h * len(desc_lines))

            # Salto pagina se poco spazio (lascia margine per footer)
            if pdf.get_y() + row_h > pdf.page_break_trigger:
                pdf.add_page()

            values = [
                code_text,
                None,
                _fit_cell_text(pdf, _fmt_num(unit_net, 2), _ITEM_COLS[2]),
                _fit_cell_text(pdf, str(vat_label), _ITEM_COLS[3]),
                _fit_cell_text(pdf, _fmt_pct(reduction_pct), _ITEM_COLS[4]),
                _fit_cell_text(pdf, _fmt_qty(qty), _ITEM_COLS[5]),
                _fit_cell_text(pdf, _fmt_num(line_net, 2), _ITEM_COLS[6]),
            ]

            row_y = pdf.get_y()
            x = CONTENT_X

            pdf.set_xy(x, row_y)
            pdf.cell(_ITEM_COLS[0], row_h, code_text, 0, 0, "L")
            x += _ITEM_COLS[0]

            pdf.set_xy(x, row_y)
            for li, line in enumerate(desc_lines):
                pdf.set_xy(x, row_y + li * line_h)
                pdf.cell(desc_width, line_h, line, 0, 0, "L")
            x += desc_width

            for i in range(2, len(values)):
                pdf.set_xy(x, row_y)
                pdf.cell(_ITEM_COLS[i], row_h, values[i], 0, 0, align[i])
                x += _ITEM_COLS[i]

            pdf.set_y(row_y + row_h + 0.8)

        return total_qty

    @staticmethod
    def _draw_shipping_info(
        pdf,
        labels: Dict[str, Any],
        total_qty: int,
        total_weight: float,
        packages: int,
    ) -> None:
        """Tabella 3 colonne: qty/peso/colli + porto/causale/inizio."""
        col_w = CONTENT_W / 3.0
        row_h = 5.0
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)

        # Header + valori qty/peso/colli
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(235, 235, 235)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, row_h, _safe(labels["tot_qty"]), 1, 0, "L", True)
        pdf.cell(col_w, row_h, _safe(labels["weight"]), 1, 0, "L", True)
        pdf.cell(col_w, row_h, _safe(labels["packages"]), 1, 1, "L", True)

        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, row_h, str(int(total_qty)), 1, 0, "C")
        pdf.cell(col_w, row_h, _fmt_num(total_weight, 3), 1, 0, "C")
        pdf.cell(col_w, row_h, str(packages), 1, 1, "C")

        # Porto / causale / inizio trasporto
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(235, 235, 235)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, row_h, _safe(labels["porto"]), 1, 0, "L", True)
        pdf.cell(col_w, row_h, _safe(labels["transport_cause"]), 1, 0, "L", True)
        pdf.cell(col_w, row_h, _safe(labels["transport_start"]), 1, 1, "L", True)

        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, row_h, "-", 1, 0, "C")
        pdf.cell(col_w, row_h, "-", 1, 0, "C")
        pdf.cell(col_w, row_h, "-", 1, 1, "C")

    @classmethod
    def _draw_vat_and_totals(
        cls,
        pdf,
        labels: Dict[str, Any],
        vat_summary: List[Dict[str, Any]],
        totals: Dict[str, float],
    ) -> None:
        """
        Due tabelle affiancate:
        - sinistra: riepilogo IVA (Aliquota / Imp.Merce / Imp.Spese / Tot.IVA)
        - destra: totali documento (label | valore)
        """
        gap = 4.0
        vat_w = 106.0
        tot_w = CONTENT_W - vat_w - gap
        vat_cols = [22, 28, 28, 28]  # somma = 106
        label_w = tot_w * 0.62
        value_w = tot_w - label_w
        row_h = 5.0
        header_h = 5.5
        tot_x = CONTENT_X + vat_w + gap

        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        y0 = pdf.get_y()

        # --- Header IVA ---
        headers = labels["vat_headers"]
        pdf.set_font("Arial", "B", 7.5)
        pdf.set_fill_color(235, 235, 235)
        x = CONTENT_X
        for i, h in enumerate(headers):
            pdf.set_xy(x, y0)
            pdf.cell(vat_cols[i], header_h, _safe(h), 1, 0, "C", True)
            x += vat_cols[i]

        # --- Righe IVA ---
        vat_rows = list(vat_summary) if vat_summary else [
            {"rate": 0, "merchandise": 0, "shipping": 0, "vat": 0}
        ]
        pdf.set_font("Arial", "", 8)
        y_vat = y0 + header_h
        for row in vat_rows:
            rate = row.get("rate", 0)
            rate_label = (
                _fmt_num(rate, 0)
                if float(rate) == int(float(rate))
                else _fmt_num(rate, 2)
            )
            pdf.set_xy(CONTENT_X, y_vat)
            pdf.cell(vat_cols[0], row_h, rate_label, 1, 0, "C")
            pdf.cell(
                vat_cols[1],
                row_h,
                _fmt_num(row.get("merchandise") or 0, 2),
                1,
                0,
                "R",
            )
            pdf.cell(
                vat_cols[2],
                row_h,
                _fmt_num(row.get("shipping") or 0, 2),
                1,
                0,
                "R",
            )
            pdf.cell(
                vat_cols[3],
                row_h,
                _fmt_num(row.get("vat") or 0, 2),
                1,
                0,
                "R",
            )
            y_vat += row_h

        # --- Righe totali a destra (allineate in alto con l'header IVA) ---
        tot_items = [
            (labels["shipping_cost"], _fmt_num(totals.get("shipping_incl") or 0, 2), False),
            (labels["merchandise_net"], _fmt_num(totals.get("merchandise_net") or 0, 2), False),
            (labels["taxable_total"], _fmt_num(totals.get("taxable_total") or 0, 2), False),
            (labels["collection_fee"], _fmt_num(totals.get("collection_fee") or 0, 2), False),
            (labels["merchandise_gross"], _fmt_num(totals.get("merchandise_gross") or 0, 2), False),
            (labels["total_vat"], _fmt_num(totals.get("total_vat") or 0, 2), False),
            (labels["misc_fee"], _fmt_num(totals.get("misc_fee") or 0, 2), False),
            (labels["doc_total"], _fmt_eur(totals.get("doc_total") or 0), True),
        ]

        y_tot = y0
        for label, value, bold in tot_items:
            pdf.set_font("Arial", "B" if bold else "", 8)
            pdf.set_xy(tot_x, y_tot)
            if bold:
                pdf.set_fill_color(245, 245, 245)
                pdf.cell(label_w, row_h, _safe(label), 1, 0, "L", True)
                pdf.cell(value_w, row_h, _safe(value), 1, 0, "R", True)
            else:
                pdf.cell(label_w, row_h, _safe(label), 1, 0, "L")
                pdf.cell(value_w, row_h, _safe(value), 1, 0, "R")
            y_tot += row_h

        pdf.set_y(max(y_vat, y_tot) + 3)

    @staticmethod
    def _draw_payment_section(
        pdf,
        labels: Dict[str, Any],
        payment_text: str,
        deadlines_text: str,
    ) -> None:
        """Tabella 2 colonne: Pagamento | Scadenze."""
        col_w = CONTENT_W / 2.0
        row_h = 5.0
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(235, 235, 235)

        pdf.set_font("Arial", "B", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, row_h, _safe(labels["payment"]), 1, 0, "L", True)
        pdf.cell(col_w, row_h, _safe(labels["deadlines"]), 1, 1, "L", True)

        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, 8, _safe(payment_text or "-"), 1, 0, "L")
        pdf.cell(col_w, 8, _safe(deadlines_text or ""), 1, 1, "L")

    @staticmethod
    def _draw_transport_signatures(pdf, labels: Dict[str, Any]) -> None:
        """Tabelle firme trasporto con spazio per firma."""
        col_w = CONTENT_W / 2.0
        label_h = 5.0
        value_h = 12.0
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(235, 235, 235)

        pdf.set_font("Arial", "B", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, label_h, _safe(labels["transporter"]), 1, 0, "L", True)
        pdf.cell(col_w, label_h, _safe(labels["appearance"]), 1, 1, "L", True)

        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, value_h, "", 1, 0, "L")
        pdf.cell(col_w, value_h, "", 1, 1, "L")

        pdf.set_font("Arial", "B", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, label_h, _safe(labels["recipient_sign"]), 1, 0, "L", True)
        pdf.cell(col_w, label_h, _safe(labels["driver_sign"]), 1, 1, "L", True)

        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(col_w, value_h, "", 1, 0, "L")
        pdf.cell(col_w, value_h, "", 1, 1, "L")

    @staticmethod
    def _draw_notes(pdf, labels: Dict[str, Any], notes_text: str) -> None:
        """Blocco NOTE con bordo."""
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(235, 235, 235)

        title = labels["notes_title"]
        pdf.set_font("Arial", "B", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(CONTENT_W, 5, _safe(title), 1, 1, "L", True)

        pdf.set_font("Arial", "", 7.5)
        body = _safe(notes_text) if notes_text else "-"
        # Altezza dinamica in base al testo
        pdf.set_x(CONTENT_X)
        y_before = pdf.get_y()
        pdf.multi_cell(CONTENT_W, 3.8, body, 1, "L")
        # multi_cell con border=1 disegna già il bordo intorno al blocco
        if pdf.get_y() <= y_before:
            pdf.set_xy(CONTENT_X, y_before)
            pdf.cell(CONTENT_W, 8, "-", 1, 1, "L")

    @staticmethod
    def _format_date(value: Union[datetime, str, None]) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        return str(value)
