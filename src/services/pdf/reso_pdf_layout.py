"""
Layout PDF reso — stile elettronew (allineato a ordine/ricevuta).

Titolo RESO, tabella Impon./IVA/Sc./Quant./Totale, totali con voce Sconto.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import os

from src.services.pdf.discount_display import (
    format_discount_label,
    resolve_line_discount,
)
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
from src.services.pdf.ricevuta_pdf_layout import RicevutaPDFLayout

_ITEM_COLS = [28, 52, 24, 14, 20, 16, 36]
_ROW_H = 5.0
_FONT_SIZE = 8

_LABELS = {
    "billing": "Intestazione",
    "delivery": "Indirizzo di consegna",
    "doc_title": "RESO",
    "order_ref": "ORDINE n\u00b0 {reference} del {date}",
    "headers": ["Codice", "Descrizione", "Impon.", "IVA", "Sc.", "Quant.", "Totale"],
    "merchandise": "Totale merce",
    "discount": "Sconto",
    "shipping": "Spedizione",
    "total_vat": "Totale IVA",
    "grand_total": "Totale - ({qty} pz.)",
    "note": "NOTE:",
}


class ResoPDFLayout:
    """Disegna il PDF reso su un'istanza FPDF già creata."""

    @classmethod
    def render(
        cls,
        pdf,
        *,
        doc_number: str,
        doc_date: Union[datetime, str],
        company_config: Dict[str, Any],
        logo_path: Optional[str],
        invoice_address,
        delivery_address,
        order_reference: str,
        order_date: Union[datetime, str],
        details: List[Dict[str, Any]],
        totals: Dict[str, float],
        note_text: Optional[str] = None,
    ) -> None:
        labels = _LABELS
        if isinstance(doc_date, datetime):
            emission_date = doc_date.strftime("%d/%m/%Y")
        else:
            emission_date = str(doc_date)

        cls._draw_header(
            pdf,
            company_config=company_config,
            logo_path=logo_path,
            doc_title=labels["doc_title"],
            doc_number=doc_number,
            emission_date=emission_date,
        )
        pdf.ln(4)

        RicevutaPDFLayout._draw_address_columns(
            pdf,
            invoice_address=invoice_address,
            delivery_address=delivery_address,
            billing_label=labels["billing"],
            delivery_label=labels["delivery"],
        )
        pdf.ln(3)

        RicevutaPDFLayout._draw_horizontal_rule(pdf, thick=False)
        RicevutaPDFLayout._draw_order_reference(
            pdf,
            labels["order_ref"].format(
                reference=order_reference,
                date=(
                    order_date.strftime("%d/%m/%Y")
                    if isinstance(order_date, datetime)
                    else str(order_date)
                ),
            ),
        )
        total_qty = cls._draw_items_table(pdf, details=details, headers=labels["headers"])
        RicevutaPDFLayout._draw_horizontal_rule(pdf, thick=False)
        pdf.ln(2)

        cls._draw_totals_block(
            pdf,
            totals=totals,
            total_qty=total_qty,
            labels=labels,
        )
        pdf.ln(4)

        if note_text and str(note_text).strip():
            pdf.set_font("Arial", "B", 8)
            pdf.set_x(CONTENT_X)
            pdf.cell(12, 4, _safe(labels["note"]), 0, 0, "L")
            pdf.set_font("Arial", "", 8)
            pdf.multi_cell(CONTENT_W - 12, 4, _safe(str(note_text).strip()), 0, "L")
            pdf.ln(4)

        RicevutaPDFLayout._draw_page_footer(pdf)

    @staticmethod
    def _draw_header(
        pdf,
        company_config: Dict[str, Any],
        logo_path: Optional[str],
        doc_title: str,
        doc_number: str,
        emission_date: str,
    ) -> None:
        y0 = 10

        if logo_path and os.path.exists(logo_path):
            try:
                pdf.image(logo_path, x=CONTENT_X, y=y0, w=42)
            except Exception:
                pass

        pdf.set_xy(CONTENT_X, y0 + 18)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(40, 40, 40)
        for line in OrderPDFService._company_lines(company_config):
            pdf.set_x(CONTENT_X)
            pdf.cell(COL_LEFT_W, 3.8, _safe(line), 0, 1, "L")

        pdf.set_xy(COL_RIGHT_X, y0 + 10)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(COL_RIGHT_W, 7, _safe(doc_title), 0, 1, "R")

        pdf.set_font("Arial", "", 10)
        pdf.set_x(COL_RIGHT_X)
        pdf.cell(
            COL_RIGHT_W,
            5,
            _safe(f"n\u00b0 {doc_number} del {emission_date}"),
            0,
            1,
            "R",
        )

        pdf.set_y(max(pdf.get_y(), y0 + 38))

    @classmethod
    def _draw_items_table(
        cls,
        pdf,
        details: List[Dict[str, Any]],
        headers: List[str],
    ) -> int:
        align = ["L", "L", "R", "C", "R", "R", "R"]
        pdf.set_font("Arial", "B", _FONT_SIZE)
        header_y = pdf.get_y()
        x = CONTENT_X
        for i, header in enumerate(headers):
            pdf.set_xy(x, header_y)
            label = _fit_cell_text(pdf, header, _ITEM_COLS[i])
            pdf.cell(_ITEM_COLS[i], _ROW_H, label, 0, 0, align[i])
            x += _ITEM_COLS[i]
        pdf.ln(_ROW_H + 1)

        pdf.set_font("Arial", "", _FONT_SIZE)
        total_qty = 0
        if not details:
            pdf.set_x(CONTENT_X)
            pdf.cell(CONTENT_W, _ROW_H, "Nessun articolo", 0, 1, "L")
            return 0

        desc_width = _ITEM_COLS[1]
        line_h = 4.2

        for detail in details:
            qty = float(detail.get("product_qty") or 0)
            if not detail.get("is_shipping"):
                total_qty += int(qty) if qty == int(qty) else int(qty)
            unit_net = float(detail.get("unit_price_net") or detail.get("unit_price") or 0)
            line_net = float(detail.get("total_price_net") or 0)
            reduction_pct = float(detail.get("reduction_percent") or 0)
            vat_rate = float(detail.get("vat_rate") or 0)
            vat_label = (
                _fmt_num(vat_rate, 0) if vat_rate else "0"
            )

            line_discount = float(detail.get("line_discount") or 0)
            if line_discount <= 0:
                line_discount, _ = resolve_line_discount(
                    qty=qty,
                    unit_net=unit_net,
                    line_net=line_net,
                    reduction_percent=reduction_pct,
                    reduction_amount=float(detail.get("reduction_amount") or 0),
                )
            discount_label = format_discount_label(
                reduction_percent=reduction_pct,
                discount_amount=line_discount,
                fmt_num=_fmt_num,
                fmt_pct=_fmt_pct,
            )

            code_text = _fit_cell_text(
                pdf, str(detail.get("product_reference") or ""), _ITEM_COLS[0]
            )
            desc_lines = _wrap_description(
                pdf, str(detail.get("product_name") or ""), desc_width, max_lines=2
            )
            row_h = max(_ROW_H, line_h * len(desc_lines))

            values = [
                code_text,
                None,
                _fit_cell_text(pdf, _fmt_num(unit_net, 2), _ITEM_COLS[2]),
                _fit_cell_text(pdf, str(vat_label), _ITEM_COLS[3]),
                _fit_cell_text(pdf, discount_label, _ITEM_COLS[4]),
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
    def _draw_totals_block(
        pdf,
        totals: Dict[str, float],
        total_qty: int,
        labels: Dict[str, Any],
    ) -> None:
        label_x = 118
        value_w = 42
        label_w = CONTENT_W - (label_x - CONTENT_X) - value_w

        def row(label: str, value: str, bold: bool = False) -> None:
            pdf.set_font("Arial", "B" if bold else "", 9)
            pdf.set_x(label_x)
            pdf.cell(label_w, 5, _safe(label), 0, 0, "L")
            pdf.cell(value_w, 5, _safe(value), 0, 1, "R")

        discount_abs = float(totals.get("total_discount") or 0)
        discount_value = -discount_abs if discount_abs > 0 else 0.0

        row(labels["merchandise"], _fmt_eur(totals.get("merchandise_net") or 0))
        row(labels["discount"], _fmt_eur(discount_value))
        row(labels["shipping"], _fmt_eur(totals.get("shipping_incl") or 0))
        row(labels["total_vat"], _fmt_eur(totals.get("total_vat") or 0))
        pdf.ln(1)
        RicevutaPDFLayout._draw_horizontal_rule(pdf, thick=True)
        qty_label = labels["grand_total"].format(qty=int(total_qty))
        row(qty_label, _fmt_eur(totals.get("total_gross") or 0), bold=True)

    @staticmethod
    def create_pdf(margin: int = MARGIN):
        return OrderPDFService.create_pdf(margin=margin)
