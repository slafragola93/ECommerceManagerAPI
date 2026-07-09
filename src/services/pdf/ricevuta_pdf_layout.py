"""
Layout PDF ricevuta estero — stile elettronew (B/N, linee orizzontali).

Allineato al template legacy: logo + anagrafica, RICEVUTA n°/data,
En-tête / indirizzo consegna, tabella righe e totali a destra.
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

# Larghezze colonne tabella (totale = CONTENT_W 190 mm)
_RICEVUTA_ITEM_COLS = [28, 52, 22, 16, 22, 14, 36]
_RICEVUTA_ROW_H = 5.0
_RICEVUTA_FONT_SIZE = 8

_LABELS_IT = {
    "billing": "Intestazione",
    "delivery": "Indirizzo di consegna",
    "doc_title": "RICEVUTA",
    "order_ref": "ORDINE n\u00b0 {reference} del {date}",
    "headers": ["Code", "Description", "Prezzo", "IVA", "Sconto", "Quant.", "Totale"],
    "merchandise": "Totale merce",
    "shipping": "Spedizione",
    "shipping_line": "Spedizione",
    "total_vat": "Totale IVA",
    "grand_total": "Totale - ({qty} pz.)",
    "note": "NOTE:",
}

_LABELS_FR = {
    "billing": "En-t\u00eate",
    "delivery": "Adresse de livraison",
    "doc_title": "RICEVUTA",
    "order_ref": "ORDINE n\u00b0 {reference} del {date}",
    "headers": ["Code", "Description", "Prix", "TVA", "R\u00e9duction", "Quant.", "Total"],
    "merchandise": "Totale merce",
    "shipping": "Spedizione",
    "shipping_line": "Livraison",
    "total_vat": "TVA totale",
    "grand_total": "Total - ({qty} pz.)",
    "note": "NOTE:",
}

_LABELS_BY_ISO = {
    "FR": _LABELS_FR,
}


def _labels_for_country(iso_code: Optional[str]) -> Dict[str, Any]:
    if not iso_code:
        return _LABELS_IT
    return _LABELS_BY_ISO.get(iso_code.upper(), _LABELS_IT)


def _resolve_iso_code(invoice_address, delivery_address) -> Optional[str]:
    for addr in (invoice_address, delivery_address):
        if not addr:
            continue
        country = getattr(addr, "country", None)
        if country and getattr(country, "iso_code", None):
            return str(country.iso_code).upper()
    return None


def _vat_display(vat_rate: float, tax_code: Optional[str], iso_code: Optional[str]) -> str:
    if tax_code and str(tax_code).strip():
        return str(tax_code).strip()
    if vat_rate and iso_code:
        pct = int(vat_rate) if float(vat_rate).is_integer() else vat_rate
        return f"{pct}{iso_code}"
    if vat_rate:
        return f"{_fmt_num(vat_rate, 0)}%"
    return "-"


class RicevutaPDFLayout:
    """Disegna il PDF ricevuta su un'istanza FPDF già creata."""

    @classmethod
    def render(
        cls,
        pdf,
        *,
        ricevuta_numero: int,
        ricevuta_anno: int,
        data_emissione: datetime,
        company_config: Dict[str, Any],
        logo_path: Optional[str],
        invoice_address,
        delivery_address,
        order_reference: str,
        order_date: Union[datetime, str],
        details: List[Dict[str, Any]],
        totals: Dict[str, float],
        note_text: str = "",
        locale_iso: Optional[str] = None,
    ) -> None:
        labels = _labels_for_country(locale_iso)
        doc_number = f"{ricevuta_numero}/{ricevuta_anno}"
        emission_date = data_emissione.strftime("%d/%m/%Y")

        cls._draw_header(
            pdf,
            company_config=company_config,
            logo_path=logo_path,
            doc_title=labels["doc_title"],
            doc_number=doc_number,
            emission_date=emission_date,
        )
        pdf.ln(4)

        cls._draw_address_columns(
            pdf,
            invoice_address=invoice_address,
            delivery_address=delivery_address,
            billing_label=labels["billing"],
            delivery_label=labels["delivery"],
        )
        pdf.ln(3)

        cls._draw_horizontal_rule(pdf, thick=False)
        cls._draw_order_reference(
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
        total_qty = cls._draw_items_table(
            pdf,
            details=details,
            headers=labels["headers"],
            locale_iso=locale_iso,
        )
        cls._draw_horizontal_rule(pdf, thick=False)
        pdf.ln(2)

        cls._draw_totals_block(
            pdf,
            totals=totals,
            total_qty=total_qty,
            labels=labels,
        )
        pdf.ln(6)

        cls._draw_footer(pdf, note_text=note_text, note_label=labels["note"])

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
            _safe(f"n\u00b0 {doc_number} la {emission_date}"),
            0,
            1,
            "R",
        )

        pdf.set_y(max(pdf.get_y(), y0 + 38))

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
        for line in RicevutaPDFLayout._format_billing_lines(invoice_address):
            pdf.set_x(CONTENT_X)
            pdf.cell(COL_LEFT_W, 4.2, _safe(line), 0, 1, "L")

        pdf.set_xy(COL_RIGHT_X, y_start)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(COL_RIGHT_W, 5, _safe(delivery_label), 0, 1, "R")

        pdf.set_font("Arial", "", 8.5)
        for line in RicevutaPDFLayout._format_delivery_lines(delivery_address):
            pdf.set_x(COL_RIGHT_X)
            pdf.cell(COL_RIGHT_W, 4.2, _safe(line), 0, 1, "R")

        pdf.set_y(max(pdf.get_y(), y_start + 28))

    @staticmethod
    def _person_name(address) -> str:
        if not address:
            return ""
        if getattr(address, "company", None):
            return ""
        parts = [
            getattr(address, "firstname", "") or "",
            getattr(address, "lastname", "") or "",
        ]
        return " ".join(p for p in parts if p).strip()

    @classmethod
    def _format_billing_lines(cls, address) -> List[str]:
        if not address:
            return ["-"]
        lines: List[str] = []
        name = cls._person_name(address)
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
        if getattr(address, "postcode", None):
            city_bits.append(str(address.postcode))
        if getattr(address, "city", None):
            city_bits.append(str(address.city))
        state = getattr(address, "state", None)
        if state:
            city_bits.append(f"({state})")
        city_line = " - ".join(city_bits)
        if country_name:
            city_line = f"{city_line} {country_name}".strip()
        if city_line:
            lines.append(city_line)

        phone = getattr(address, "phone", None)
        mobile = getattr(address, "mobile_phone", None)
        if phone and mobile:
            lines.append(f"TEL. {phone} CELL. {mobile}")
        elif phone:
            lines.append(f"TEL. {phone}")
        elif mobile:
            lines.append(f"CELL. {mobile}")

        return lines or ["-"]

    @classmethod
    def _format_delivery_lines(cls, address) -> List[str]:
        if not address:
            return ["-"]
        lines: List[str] = []
        name = cls._person_name(address)
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
        if getattr(address, "postcode", None):
            city_bits.append(str(address.postcode))
        if getattr(address, "city", None):
            city_bits.append(str(address.city))
        state = getattr(address, "state", None)
        if state:
            city_bits.append(f"({state})")
        city_line = " - ".join(city_bits)
        if country_name:
            city_line = f"{city_line} {country_name}".strip()
        if city_line:
            lines.append(city_line)

        return lines or ["-"]

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
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_x(CONTENT_X)
        pdf.cell(CONTENT_W, 5, _safe(text), 0, 1, "L")
        pdf.ln(0.5)

    @classmethod
    def _draw_items_table(
        cls,
        pdf,
        details: List[Dict[str, Any]],
        headers: List[str],
        locale_iso: Optional[str],
    ) -> int:
        align = ["L", "L", "R", "C", "R", "R", "R"]
        pdf.set_font("Arial", "B", _RICEVUTA_FONT_SIZE)
        header_y = pdf.get_y()
        x = CONTENT_X
        for i, header in enumerate(headers):
            pdf.set_xy(x, header_y)
            label = _fit_cell_text(pdf, header, _RICEVUTA_ITEM_COLS[i])
            pdf.cell(_RICEVUTA_ITEM_COLS[i], _RICEVUTA_ROW_H, label, 0, 0, align[i])
            x += _RICEVUTA_ITEM_COLS[i]
        pdf.ln(_RICEVUTA_ROW_H + 1)

        pdf.set_font("Arial", "", _RICEVUTA_FONT_SIZE)
        total_qty = 0
        if not details:
            pdf.set_x(CONTENT_X)
            pdf.cell(CONTENT_W, _RICEVUTA_ROW_H, "Nessun articolo", 0, 1, "L")
            return 0

        desc_width = _RICEVUTA_ITEM_COLS[1]
        line_h = 4.2

        for detail in details:
            qty = int(detail.get("product_qty") or 0)
            if not detail.get("is_shipping"):
                total_qty += qty
            unit_net = float(detail.get("unit_price") or 0)
            line_net = float(detail.get("total_price_net") or 0)
            reduction_pct = float(detail.get("reduction_percent") or 0)
            vat_rate = float(detail.get("vat_rate") or 0)
            tax_code = detail.get("tax_code")
            vat_label = _vat_display(vat_rate, tax_code, locale_iso)

            code_text = _fit_cell_text(
                pdf, str(detail.get("product_reference") or ""), _RICEVUTA_ITEM_COLS[0]
            )
            desc_lines = _wrap_description(
                pdf, str(detail.get("product_name") or ""), desc_width, max_lines=2
            )
            row_h = max(_RICEVUTA_ROW_H, line_h * len(desc_lines))

            values = [
                code_text,
                None,
                _fit_cell_text(pdf, _fmt_num(unit_net, 2), _RICEVUTA_ITEM_COLS[2]),
                _fit_cell_text(pdf, vat_label, _RICEVUTA_ITEM_COLS[3]),
                _fit_cell_text(pdf, _fmt_pct(reduction_pct), _RICEVUTA_ITEM_COLS[4]),
                _fit_cell_text(pdf, _fmt_qty(qty), _RICEVUTA_ITEM_COLS[5]),
                _fit_cell_text(pdf, _fmt_num(line_net, 2), _RICEVUTA_ITEM_COLS[6]),
            ]

            row_y = pdf.get_y()
            x = CONTENT_X

            pdf.set_xy(x, row_y)
            pdf.cell(_RICEVUTA_ITEM_COLS[0], row_h, code_text, 0, 0, "L")
            x += _RICEVUTA_ITEM_COLS[0]

            pdf.set_xy(x, row_y)
            for li, line in enumerate(desc_lines):
                pdf.set_xy(x, row_y + li * line_h)
                pdf.cell(desc_width, line_h, line, 0, 0, "L")
            x += desc_width

            for i in range(2, len(values)):
                pdf.set_xy(x, row_y)
                pdf.cell(
                    _RICEVUTA_ITEM_COLS[i],
                    row_h,
                    values[i],
                    0,
                    0,
                    align[i],
                )
                x += _RICEVUTA_ITEM_COLS[i]

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

        row(labels["merchandise"], _fmt_eur(totals["merchandise_net"]))
        row(labels["shipping"], _fmt_eur(totals["shipping_incl"]))
        row(labels["total_vat"], _fmt_eur(totals["total_vat"]))
        pdf.ln(1)
        RicevutaPDFLayout._draw_horizontal_rule(pdf, thick=True)
        qty_label = labels["grand_total"].format(qty=int(total_qty))
        row(qty_label, _fmt_eur(totals["total_gross"]), bold=True)

    @staticmethod
    def _draw_footer(pdf, note_text: str, note_label: str) -> None:
        pdf.set_font("Arial", "B", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(12, 4, _safe(note_label), 0, 0, "L")
        pdf.set_font("Arial", "", 8)
        pdf.multi_cell(CONTENT_W - 12, 4, _safe(note_text), 0, "L")
        pdf.ln(8)
        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(CONTENT_W, 4, "Pagina 1 di 1", 0, 0, "L")

    @staticmethod
    def create_pdf(margin: int = MARGIN):
        return OrderPDFService.create_pdf(margin=margin)
