"""
Servizio PDF per la stampa del singolo ordine (layout elettronew legacy).

Layout B/N: logo + anagrafica società, barcode + titolo ordine, intestazione /
indirizzo consegna, tabella righe (Codice, Descrizione, Impon., IVA, Sconto,
Quant., Totale) e riepilogo totali a destra.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import os

from src.services.pdf.base_pdf_service import BasePDFService

MARGIN = 10
CONTENT_X = 10
CONTENT_W = 190
PAGE_RIGHT = CONTENT_X + CONTENT_W
COL_LEFT_W = 95
COL_RIGHT_W = 95
COL_RIGHT_X = CONTENT_X + COL_LEFT_W

# Larghezze colonne tabella articoli (totale = CONTENT_W 190 mm)
# Codice più largo per reference tipo "VOR 0000016151"; numeri compatti a destra.
_ITEM_COLS = [40, 50, 24, 11, 17, 12, 36]
_ITEM_HEADERS = ["Codice", "Descrizione", "Impon.", "IVA", "Sconto", "Quant.", "Totale"]
_ITEM_ALIGN = ["L", "L", "R", "R", "R", "R", "R"]
_ITEM_ROW_H = 5.0
_ITEM_FONT_SIZE = 8
_ITEM_HEADER_FONT_SIZE = 8

EUR_GLYPH = True


def _fmt_num(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        value = 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    formatted = f"{v:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_eur(value: Optional[float]) -> str:
    glyph = "\u20ac " if EUR_GLYPH else "EUR "
    return f"{glyph}{_fmt_num(value, 2)}"


def _fmt_qty(value: Optional[float]) -> str:
    if value is None:
        return "0"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0"
    if v.is_integer():
        return str(int(v))
    return _fmt_num(v, 2)


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "0.00 %"
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return f"{_fmt_num(v, 2)} %"


def _safe(text: Any) -> str:
    if text is None:
        return ""
    return str(text).encode("cp1252", errors="replace").decode("cp1252")


def _fit_cell_text(pdf, text: str, max_width: float, padding: float = 1.0) -> str:
    """Tronca il testo alla larghezza cella (mm) per evitare overlap tra colonne."""
    usable = max(max_width - padding, 1.0)
    s = _safe(text).strip()
    if not s:
        return ""
    if pdf.get_string_width(s) <= usable:
        return s
    ellipsis = "..."
    trimmed = s
    while trimmed and pdf.get_string_width(trimmed + ellipsis) > usable:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def _wrap_description(pdf, text: str, col_width: float, max_lines: int = 2) -> List[str]:
    """Spezza la descrizione su al massimo max_lines righe dentro col_width."""
    s = _safe(text).strip() or "-"
    usable = max(col_width - 1.0, 1.0)
    if pdf.get_string_width(s) <= usable:
        return [s]

    words = s.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.get_string_width(candidate) <= usable:
            current = candidate
        elif current:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        else:
            # parola singola più larga della colonna
            chunk = word
            while chunk and pdf.get_string_width(chunk + "...") > usable:
                chunk = chunk[:-1]
            lines.append((chunk + "...") if chunk else "...")
            current = ""
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and " ".join(words) != " ".join(lines):
        last = lines[-1]
        if pdf.get_string_width(last + "...") > usable:
            trimmed = last
            while trimmed and pdf.get_string_width(trimmed + "...") > usable:
                trimmed = trimmed[:-1]
            lines[-1] = (trimmed + "...") if trimmed else "..."
        elif not last.endswith("..."):
            trimmed = last
            while trimmed and pdf.get_string_width(trimmed + "...") > usable:
                trimmed = trimmed[:-1]
            if trimmed != last:
                lines[-1] = trimmed + "..."
    return lines or ["-"]


class OrderPDFService(BasePDFService):
    """Genera il PDF di stampa ordine in stile elettronew."""

    def generate_pdf(
        self,
        order,
        order_details: List[Any],
        company_config: Dict[str, Any],
        invoice_address=None,
        delivery_address=None,
        payment_name: Optional[str] = None,
        shipping=None,
        tax_percentages: Optional[Dict[int, float]] = None,
        logo_path: Optional[str] = None,
    ) -> bytes:
        if not order:
            raise ValueError("order è richiesto")
        if company_config is None:
            raise ValueError("company_config è richiesto")

        tax_percentages = tax_percentages or {}
        pdf = self.create_pdf(margin=MARGIN)

        barcode_value = self._barcode_value(order)
        order_code_label = self._order_code_label(order)
        order_ref = order.reference or str(order.id_order)
        order_date = order.date_add if order.date_add else datetime.now()

        self._draw_header(
            pdf=pdf,
            company_config=company_config,
            logo_path=logo_path,
            barcode_value=barcode_value,
            order_code_label=order_code_label,
            order_reference=order_ref,
            order_date=order_date,
        )
        pdf.ln(4)

        self._draw_address_columns(
            pdf=pdf,
            invoice_address=invoice_address,
            delivery_address=delivery_address,
        )
        pdf.ln(3)

        self._draw_horizontal_rule(pdf, thick=False)
        total_qty = self._draw_items_table(pdf, order_details, tax_percentages)
        self._draw_horizontal_rule(pdf, thick=False)
        pdf.ln(2)

        totals = self._compute_totals(order, order_details, shipping, tax_percentages)
        self._draw_totals_block(
            pdf=pdf,
            totals=totals,
            payment_name=payment_name or "-",
            total_qty=total_qty,
        )
        pdf.ln(6)

        note_text = (order.general_note or "").strip()
        self._draw_footer(pdf, note_text=note_text)

        return pdf.output()

    # ------------------------------------------------------------------
    # Sezioni layout
    # ------------------------------------------------------------------

    @staticmethod
    def _draw_header(
        pdf,
        company_config: Dict[str, Any],
        logo_path: Optional[str],
        barcode_value: str,
        order_code_label: str,
        order_reference: str,
        order_date: Union[datetime, str],
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

        # Barcode Code39 (fpdf2): asterischi start/stop obbligatori per code39()
        try:
            pdf.code39(_safe(f"*{barcode_value}*"), x=132, y=y0, w=0.35, h=10)
        except Exception:
            pass

        pdf.set_xy(COL_RIGHT_X, y0 + 12)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(COL_RIGHT_W, 6, _safe(f"ORDINE - {order_code_label}"), 0, 1, "R")

        date_str = (
            order_date.strftime("%d/%m/%Y")
            if isinstance(order_date, datetime)
            else str(order_date)
        )
        pdf.set_font("Arial", "", 9)
        pdf.set_x(COL_RIGHT_X)
        pdf.cell(COL_RIGHT_W, 5, _safe(f"n\u00b0 {order_reference} del {date_str}"), 0, 1, "R")

        pdf.set_y(max(pdf.get_y(), y0 + 38))

    @staticmethod
    def _company_lines(config: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        if config.get("company_name"):
            lines.append(str(config["company_name"]))

        address_parts = [config.get("address", "")]
        civic = config.get("civic_number")
        if civic:
            address_parts[0] = f"{address_parts[0]} {civic}".strip()
        city_line = " ".join(
            p
            for p in [
                address_parts[0] if address_parts else "",
                ", ".join(
                    x
                    for x in [
                        config.get("postal_code"),
                        config.get("city"),
                    ]
                    if x
                ),
            ]
            if p
        ).strip(", ")
        province = config.get("province")
        if province and city_line:
            city_line = f"{city_line} ({province})"
        elif province:
            city_line = f"({province})"
        if city_line:
            lines.append(city_line)

        fiscal_parts = []
        vat = config.get("vat_number")
        if vat:
            fiscal_parts.append(f"P.I. {vat}")
        cf = config.get("fiscal_code")
        if cf:
            fiscal_parts.append(f"C.F. {cf}")
        if fiscal_parts:
            lines.append(" - ".join(fiscal_parts))

        iban = config.get("iban")
        if iban:
            lines.append(f"IBAN {iban}")
        return lines or ["-"]

    @staticmethod
    def _draw_address_columns(pdf, invoice_address=None, delivery_address=None) -> None:
        y_start = pdf.get_y()

        pdf.set_xy(CONTENT_X, y_start)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(COL_LEFT_W, 5, "Intestazione", 0, 1, "L")

        pdf.set_font("Arial", "", 8.5)
        for line in OrderPDFService._format_invoice_lines(invoice_address):
            pdf.set_x(CONTENT_X)
            pdf.cell(COL_LEFT_W, 4.2, _safe(line), 0, 1, "L")

        pdf.set_xy(COL_RIGHT_X, y_start)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(COL_RIGHT_W, 5, "Indirizzo di consegna", 0, 1, "R")

        pdf.set_font("Arial", "", 8.5)
        for line in OrderPDFService._format_delivery_lines(delivery_address):
            pdf.set_x(COL_RIGHT_X)
            pdf.cell(COL_RIGHT_W, 4.2, _safe(line), 0, 1, "R")

        pdf.set_y(max(pdf.get_y(), y_start + 28))

    @staticmethod
    def _person_name(address) -> str:
        if not address:
            return ""
        if getattr(address, "company", None):
            return ""
        parts = [getattr(address, "firstname", "") or "", getattr(address, "lastname", "") or ""]
        return " ".join(p for p in parts if p).strip()

    @staticmethod
    def _format_invoice_lines(address) -> List[str]:
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

        pi = getattr(address, "vat", None)
        cf = getattr(address, "dni", None)
        if pi or cf:
            fiscal = []
            if pi:
                fiscal.append(f"PI {pi}")
            if cf:
                fiscal.append(f"CF {cf}")
            lines.append("  ".join(fiscal))

        phone = getattr(address, "mobile_phone", None) or getattr(address, "phone", None)
        if phone:
            lines.append(f"CELL. {phone}")
        return lines or ["-"]

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

        city_bits = []
        if getattr(address, "postcode", None):
            city_bits.append(str(address.postcode))
        if getattr(address, "city", None):
            city_bits.append(str(address.city))
        state = getattr(address, "state", None)
        if state:
            city_bits.append(f"({state})")
        if city_bits:
            lines.append(" - ".join(city_bits))
        return lines or ["-"]

    @staticmethod
    def _draw_horizontal_rule(pdf, thick: bool = False) -> None:
        y = pdf.get_y()
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.6 if thick else 0.2)
        pdf.line(CONTENT_X, y, PAGE_RIGHT, y)
        pdf.set_line_width(0.2)
        pdf.ln(1.5 if thick else 1)

    @classmethod
    def _draw_items_table(cls, pdf, order_details: List[Any], tax_percentages: Dict[int, float]) -> int:
        pdf.set_font("Arial", "B", _ITEM_HEADER_FONT_SIZE)
        header_y = pdf.get_y()
        x = CONTENT_X
        for i, header in enumerate(_ITEM_HEADERS):
            pdf.set_xy(x, header_y)
            label = _fit_cell_text(pdf, header, _ITEM_COLS[i])
            pdf.cell(_ITEM_COLS[i], _ITEM_ROW_H, label, 0, 0, _ITEM_ALIGN[i])
            x += _ITEM_COLS[i]
        pdf.ln(_ITEM_ROW_H + 1)

        pdf.set_font("Arial", "", _ITEM_FONT_SIZE)
        total_qty = 0
        if not order_details:
            pdf.set_x(CONTENT_X)
            pdf.cell(CONTENT_W, _ITEM_ROW_H, "Nessun articolo", 0, 1, "L")
            return 0

        desc_col_idx = 1
        desc_width = _ITEM_COLS[desc_col_idx]
        line_h = 4.2

        for detail in order_details:
            qty = int(detail.product_qty or 0)
            total_qty += qty
            vat_rate = cls._vat_rate(detail, tax_percentages)
            impon_before, net_after, reduction_pct = cls._line_amounts(detail, vat_rate)

            code_text = _fit_cell_text(
                pdf, str(detail.product_reference or ""), _ITEM_COLS[0]
            )
            desc_lines = _wrap_description(
                pdf, str(detail.product_name or ""), desc_width, max_lines=2
            )
            row_h = max(_ITEM_ROW_H, line_h * len(desc_lines))

            values = [
                code_text,
                None,  # descrizione disegnata a parte
                _fit_cell_text(pdf, _fmt_num(impon_before, 2), _ITEM_COLS[2]),
                _fit_cell_text(pdf, _fmt_num(vat_rate, 0), _ITEM_COLS[3]),
                _fit_cell_text(pdf, _fmt_pct(reduction_pct), _ITEM_COLS[4]),
                _fit_cell_text(pdf, _fmt_qty(qty), _ITEM_COLS[5]),
                _fit_cell_text(pdf, _fmt_num(net_after, 2), _ITEM_COLS[6]),
            ]

            row_y = pdf.get_y()
            x = CONTENT_X

            # Codice
            pdf.set_xy(x, row_y)
            pdf.cell(_ITEM_COLS[0], row_h, code_text, 0, 0, "L")
            x += _ITEM_COLS[0]

            # Descrizione (multi-riga, resta nella sua colonna)
            pdf.set_xy(x, row_y)
            for li, line in enumerate(desc_lines):
                pdf.set_xy(x, row_y + li * line_h)
                pdf.cell(desc_width, line_h, line, 0, 0, "L")
            x += desc_width

            # Colonne numeriche (allineate in alto sulla riga)
            for i in range(2, len(values)):
                pdf.set_xy(x, row_y)
                pdf.cell(_ITEM_COLS[i], row_h, values[i], 0, 0, _ITEM_ALIGN[i])
                x += _ITEM_COLS[i]

            pdf.set_y(row_y + row_h + 0.8)

        return total_qty

    @staticmethod
    def _vat_rate(detail, tax_percentages: Dict[int, float]) -> float:
        if getattr(detail, "id_tax", None) and detail.id_tax in tax_percentages:
            return float(tax_percentages[detail.id_tax] or 0)
        return 0.0

    @staticmethod
    def _line_amounts(detail, vat_rate: float):
        qty = float(detail.product_qty or 0)
        unit_net = float(detail.unit_price_net or detail.product_price or 0)
        net_after = float(detail.total_price_net or (unit_net * qty))
        reduction_pct = float(detail.reduction_percent or 0)
        if reduction_pct > 0 and net_after > 0:
            impon_before = net_after / (1 - reduction_pct / 100.0)
        else:
            impon_before = unit_net * qty if unit_net else net_after
        return impon_before, net_after, reduction_pct

    @staticmethod
    def _compute_totals(order, order_details, shipping, tax_percentages):
        merchandise_net = float(order.products_total_price_net or 0)
        if merchandise_net <= 0 and order_details:
            merchandise_net = sum(
                float(d.total_price_net or 0) for d in order_details
            )

        shipping_incl = 0.0
        shipping_net = 0.0
        if shipping:
            shipping_incl = float(shipping.price_tax_incl or 0)
            shipping_net = float(shipping.price_tax_excl or 0)

        total_gross = float(order.total_price_with_tax or 0)
        total_net = float(order.total_price_net or 0)
        if total_net <= 0:
            total_net = merchandise_net + shipping_net
        total_vat = max(total_gross - total_net, 0.0)

        payment_fee = 0.0
        return {
            "merchandise_net": merchandise_net,
            "shipping_incl": shipping_incl,
            "payment_fee": payment_fee,
            "total_vat": total_vat,
            "total_gross": total_gross,
        }

    @staticmethod
    def _draw_totals_block(pdf, totals: Dict[str, float], payment_name: str, total_qty: int) -> None:
        label_x = 118
        value_w = 42
        label_w = CONTENT_W - (label_x - CONTENT_X) - value_w

        def row(label: str, value: str, bold: bool = False) -> None:
            pdf.set_font("Arial", "B" if bold else "", 9)
            pdf.set_x(label_x)
            pdf.cell(label_w, 5, _safe(label), 0, 0, "L")
            pdf.cell(value_w, 5, _safe(value), 0, 1, "R")

        row("Totale merce", _fmt_eur(totals["merchandise_net"]))
        row("Spedizione", _fmt_eur(totals["shipping_incl"]))
        row(f"Spese incasso - {payment_name}", _fmt_eur(totals["payment_fee"]))
        row("Totale IVA", _fmt_eur(totals["total_vat"]))
        pdf.ln(1)
        OrderPDFService._draw_horizontal_rule(pdf, thick=True)
        qty_label = f"Totale - ({int(total_qty)} pz.)"
        row(qty_label, _fmt_eur(totals["total_gross"]), bold=True)

    @staticmethod
    def _draw_footer(pdf, note_text: str) -> None:
        pdf.set_font("Arial", "B", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(12, 4, "NOTE:", 0, 0, "L")
        pdf.set_font("Arial", "", 8)
        pdf.multi_cell(CONTENT_W - 12, 4, _safe(note_text), 0, "L")
        pdf.ln(8)
        pdf.set_font("Arial", "", 8)
        pdf.set_x(CONTENT_X)
        pdf.cell(CONTENT_W, 4, "Pagina 1 di 1", 0, 0, "L")

    # ------------------------------------------------------------------
    # Identificativi ordine e barcode
    # ------------------------------------------------------------------

    @staticmethod
    def _barcode_value(order) -> str:
        """Valore numerico codificato nel barcode (stesso criterio FastLDV / scansione magazzino).

        - Ordine PrestaShop (sync): ``id_origin`` (es. ``805260``)
        - Ordine nativo gestionale: ``id_order`` (``id_origin`` resta 0)
        """
        id_origin = getattr(order, "id_origin", None) or 0
        if id_origin and int(id_origin) > 0:
            return str(int(id_origin))
        return str(order.id_order)

    @staticmethod
    def _order_code_label(order) -> str:
        """Etichetta testuale accanto a ORDINE - … (può differire dal barcode).

        - ``internal_reference`` se valorizzato (es. ``SM805260``)
        - altrimenti prefisso legacy ``SM`` + ``id_origin`` per ordini PS
        - altrimenti ``id_order`` per ordini gestionale
        """
        if getattr(order, "internal_reference", None):
            return str(order.internal_reference)
        id_origin = getattr(order, "id_origin", None) or 0
        if id_origin and int(id_origin) > 0:
            return f"SM{int(id_origin)}"
        return str(order.id_order)

    @staticmethod
    def create_pdf(margin: int = MARGIN):
        from fpdf import FPDF

        pdf = FPDF()
        try:
            pdf.core_fonts_encoding = "cp1252"
        except Exception:
            pass
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=margin)
        return pdf
