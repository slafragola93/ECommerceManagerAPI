"""
Servizio PDF per generazione preventivi
Estende BasePDFService e implementa metodi helper specifici per preventivi
"""
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
import os

from src.services.pdf.base_pdf_service import BasePDFService


# Palette brand (allineata al logo elettronew)
COLOR_ACCENT = (30, 58, 95)            # navy
COLOR_ACCENT_SOFT = (235, 240, 247)    # navy molto chiaro per fill
COLOR_SECONDARY = (242, 201, 76)       # giallo brand (barra header)
COLOR_BORDER = (210, 215, 222)         # bordi sottili
COLOR_ROW_ZEBRA = (247, 249, 252)      # righe alternate tabella
COLOR_TEXT = (40, 40, 40)
COLOR_TEXT_MUTED = (115, 120, 130)
COLOR_TEXT_ON_ACCENT = (255, 255, 255)
COLOR_WHITE = (255, 255, 255)

# Spaziature uniformi
SPACING_SECTION = 5.0
SPACING_BLOCK = 3.0
SPACING_TIGHT = 1.5

# Margini contenuto
CONTENT_X = 10
CONTENT_WIDTH = 190  # A4 (210) - 2 * margin 10
PAGE_RIGHT = CONTENT_X + CONTENT_WIDTH


def _fmt_num(value: Optional[float], decimals: int = 2) -> str:
    """Formatta un numero in stile IT (1.234,56)."""
    if value is None:
        value = 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    formatted = f"{v:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_eur(value: Optional[float]) -> str:
    """Formatta un importo in euro (es. 'EUR 1.234,56').

    Default usa 'EUR' (ASCII puro), che funziona con qualunque font core di
    fpdf2. Se imposti EUR_GLYPH=True in cima al modulo, viene usato il
    simbolo '€' (richiede pdf.core_fonts_encoding='cp1252', vedi create_pdf).
    """
    glyph = "\u20ac " if EUR_GLYPH else "EUR "
    return f"{glyph}{_fmt_num(value, 2)}"


def _safe(text: Any) -> str:
    """Sanifica una stringa per fpdf2 con font core (encoding cp1252).

    Rimpiazza caratteri unicode non rappresentabili in cp1252 (es. emoji,
    caratteri CJK) per evitare 500 da fpdf2. Caratteri tipografici comuni
    (€, virgolette curve, em-dash, ecc.) restano supportati se in cp1252.
    """
    if text is None:
        return ""
    s = str(text)
    return s.encode("cp1252", errors="replace").decode("cp1252")


# Se True usa il glifo €, altrimenti la sigla 'EUR' (più sicura/agnostica)
EUR_GLYPH = True


def _fmt_qty(value: Optional[float]) -> str:
    """Formatta una quantità intera o decimale compatta."""
    if value is None:
        return "0"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0"
    if v.is_integer():
        return str(int(v))
    return _fmt_num(v, 2)


def _set_fill(pdf, rgb):
    pdf.set_fill_color(*rgb)


def _set_draw(pdf, rgb):
    pdf.set_draw_color(*rgb)


def _set_text(pdf, rgb):
    pdf.set_text_color(*rgb)


class PreventivoPDFService(BasePDFService):
    """Servizio per generazione PDF di preventivi"""

    def __init__(self, db_session, preventivo_repo=None, customer_repo=None, tax_repo=None, order_doc_service=None):
        """
        Inizializza il servizio

        Args:
            db_session: Sessione database SQLAlchemy
            preventivo_repo: Repository preventivi (opzionale)
            customer_repo: Repository clienti (opzionale)
            tax_repo: Repository tasse (opzionale)
            order_doc_service: Servizio order document (opzionale)
        """
        self.db = db_session
        self.preventivo_repo = preventivo_repo
        self.customer_repo = customer_repo
        self.tax_repo = tax_repo
        self.order_doc_service = order_doc_service

    def generate_pdf(self, preventivo_data, order_document=None,
                     customer_data=None, address_delivery_data=None,
                     shipping_data=None, shipping_vat_percentage: float = 0.0,
                     sender_config: Dict[str, Any] = None, logo_path: Optional[str] = None) -> bytes:
        """Genera il PDF del preventivo (vedi modulo per dettagli grafici)."""
        try:
            if not preventivo_data:
                raise ValueError("preventivo_data è richiesto")
            if not sender_config:
                raise ValueError("sender_config è richiesto")

            pdf = self.create_pdf(margin=12)
            _set_draw(pdf, COLOR_BORDER)
            _set_text(pdf, COLOR_TEXT)

            # ---------- HEADER ----------
            document_date = preventivo_data.date_add if preventivo_data.date_add else datetime.now()
            self.create_document_header(
                pdf=pdf,
                title="PREVENTIVO",
                document_number=preventivo_data.document_number,
                date=document_date,
                logo_path=logo_path,
            )
            pdf.ln(SPACING_SECTION)

            # ---------- MITTENTE / DESTINATARIO ----------
            # Mittente per preventivi = dati legali societa' (company_info).
            # Compone una riga indirizzo aggregata "via, civico" e mette
            # citta'/CAP/provincia separati per il blocco indirizzo.
            address_main = sender_config.get('address', '') or ''
            civic_number = sender_config.get('civic_number', '') or ''
            address_line = f"{address_main}, {civic_number}".strip(', ') if civic_number else address_main
            province = sender_config.get('province', '') or ''
            city_value = sender_config.get('city', '') or ''
            city_full = f"{city_value} ({province})".strip() if province else city_value

            sender_info_dict = {
                'name': sender_config.get('company_name', ''),
                'address': address_line,
                'city': city_full,
                'postcode': sender_config.get('postal_code', ''),
                'country': sender_config.get('country', ''),
                'vat': sender_config.get('vat_number', ''),
                'fiscal_code': sender_config.get('fiscal_code', ''),
                'sdi': sender_config.get('sdi_code', ''),
                'pec': sender_config.get('pec', ''),
                'phone': sender_config.get('phone', ''),
                'email': sender_config.get('email', ''),
            }

            recipient_info_dict = {}
            if customer_data and address_delivery_data:
                customer_name = f"{customer_data.get('firstname', '')} {customer_data.get('lastname', '')}".strip()
                recipient_info_dict = {
                    'name': customer_name,
                    'address': address_delivery_data.get('address1', ''),
                    'city': address_delivery_data.get('city', ''),
                    'postcode': address_delivery_data.get('postcode', ''),
                    'phone': address_delivery_data.get('phone', ''),
                }

            self.create_address_boxes(
                pdf=pdf,
                sender_data=sender_info_dict,
                recipient_data=recipient_info_dict,
            )
            pdf.ln(SPACING_SECTION)

            # ---------- TABELLA ARTICOLI ----------
            self.create_items_table_header(pdf)

            subtotal = 0.0
            total_with_vat_sum = 0.0
            total_quantity = 0
            total_weight = 0.0
            row_index = 0
            vat_rate = 0.0

            if preventivo_data.articoli:
                for articolo in preventivo_data.articoli:
                    code = (articolo.product_reference or '')
                    description = (articolo.product_name or '')
                    quantity = float(articolo.product_qty or 0)

                    vat_rate = float(getattr(articolo, 'aliquota_iva', None) or 0.0)
                    if not vat_rate and articolo.id_tax and self.tax_repo:
                        vat_rate = float(self.tax_repo.get_percentage_by_id(int(articolo.id_tax)) or 0.0)
                    vat_multiplier = 1 + (vat_rate / 100.0) if vat_rate else 1.0

                    unit_price = float(
                        getattr(articolo, 'product_price', None)
                        or articolo.unit_price_net
                        or 0.0
                    )
                    if unit_price <= 0 and articolo.unit_price_with_tax:
                        unit_price = float(articolo.unit_price_with_tax) / vat_multiplier

                    reduction = 0.0
                    if articolo.reduction_percent and articolo.reduction_percent > 0:
                        reduction = float((unit_price * quantity) * (float(articolo.reduction_percent) / 100.0))
                    elif articolo.reduction_amount and articolo.reduction_amount > 0:
                        reduction = float(articolo.reduction_amount)

                    total_amount = float(
                        getattr(articolo, 'taxable', None)
                        or articolo.total_price_net
                        or 0.0
                    )
                    if total_amount <= 0:
                        total_amount = float((unit_price * quantity) - reduction)

                    total_with_vat = float(
                        getattr(articolo, 'prezzo_totale_riga', None)
                        or articolo.total_price_with_tax
                        or 0.0
                    )
                    if total_with_vat <= 0:
                        total_with_vat = float(total_amount * vat_multiplier)

                    self.add_items_table_row(
                        pdf=pdf,
                        code=code,
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        vat_rate=vat_rate,
                        total_with_vat=total_with_vat,
                        zebra=(row_index % 2 == 1),
                    )
                    row_index += 1

                    subtotal += total_amount
                    total_with_vat_sum += total_with_vat
                    total_quantity += int(quantity)
                    if articolo.product_weight:
                        total_weight += float(articolo.product_weight or 0.0) * quantity

            pdf.ln(SPACING_SECTION)

            # ---------- INFO SPEDIZIONE ----------
            total_weight_kg = total_weight or (shipping_data.get('weight', 0.0) if shipping_data else 0.0)
            shipping_cost = float(shipping_data.get('price_tax_excl', 0.0)) if shipping_data else 0.0
            shipping_cost_with_vat = float(shipping_data.get('price_tax_incl', 0.0)) if shipping_data else 0.0

            self.create_section_title(pdf, 'INFORMAZIONI SPEDIZIONE')
            self.create_simple_table(
                pdf=pdf,
                headers=['Tot. Quantità', 'Peso (Kg)', 'Colli'],
                rows=[[_fmt_qty(total_quantity), _fmt_num(total_weight_kg, 3), '1']],
            )
            pdf.ln(SPACING_SECTION)

            # ---------- RIEPILOGO IVA ----------
            self.create_section_title(pdf, 'RIEPILOGO IVA')
            vat_rate_label = f"{_fmt_num(vat_rate, 0)}%" if vat_rate else '0%'
            self.create_vat_summary_table(
                pdf=pdf,
                vat_rate_label=vat_rate_label,
                merchandise_amount=subtotal,
                shipping_amount=shipping_cost,
                shipping_with_vat=shipping_cost_with_vat,
                shipping_vat_percentage=shipping_vat_percentage,
                total_vat=float(preventivo_data.total_iva or 0.0),
            )
            pdf.ln(SPACING_SECTION)

            # ---------- TOTALI ----------
            total_doc = float(preventivo_data.total_price_with_tax or 0.0)
            total_vat = float(preventivo_data.total_iva or 0.0)
            self.create_totals_section(
                pdf=pdf,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total_with_vat_sum=total_with_vat_sum,
                total_vat=total_vat,
                total_doc=total_doc,
            )
            pdf.ln(SPACING_SECTION)

            # ---------- NOTE ----------
            if preventivo_data.note:
                self.add_notes(pdf=pdf, notes=preventivo_data.note)
                pdf.ln(SPACING_BLOCK)

            # ---------- FOOTER ----------
            self.add_footer(pdf=pdf)

            return pdf.output()

        except ImportError:
            raise Exception("Libreria fpdf2 non installata. Installare con: pip install fpdf2")
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")

    # ------------------------------------------------------------------
    # Helper grafici
    # ------------------------------------------------------------------

    @staticmethod
    def create_pdf(margin: int = 12) -> Any:
        from fpdf import FPDF
        pdf = FPDF()
        # Abilita encoding cp1252 sui font core (Arial/Helvetica) così
        # caratteri come '€', virgolette curve, em-dash, ecc. sono supportati.
        try:
            pdf.core_fonts_encoding = "cp1252"
        except Exception:
            pass
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=margin)
        return pdf

    @staticmethod
    def insert_logo(pdf, logo_path: Optional[str], x: float = 10, y: float = 10, width: float = 38) -> bool:
        if not logo_path or not os.path.exists(logo_path):
            return False
        try:
            pdf.image(logo_path, x=x, y=y, w=width)
            return True
        except Exception:
            return False

    @staticmethod
    def create_document_header(
        pdf,
        title: str,
        document_number: str,
        date: Union[str, datetime],
        logo_path: Optional[str] = None,
    ) -> Dict[str, float]:
        """Header con logo a sinistra, titolo + numero + data a destra, barra accent in basso."""
        y_start = 10

        PreventivoPDFService.insert_logo(pdf, logo_path, x=CONTENT_X, y=y_start, width=38)

        _set_text(pdf, COLOR_ACCENT)
        pdf.set_xy(110, y_start + 2)
        pdf.set_font('Arial', 'B', 20)
        pdf.cell(CONTENT_X + CONTENT_WIDTH - 110, 9, title, 0, 1, 'R')

        _set_text(pdf, COLOR_TEXT)
        pdf.set_xy(110, y_start + 12)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(CONTENT_X + CONTENT_WIDTH - 110, 6, _safe(f"N. {document_number}"), 0, 1, 'R')

        _set_text(pdf, COLOR_TEXT_MUTED)
        pdf.set_xy(110, y_start + 18)
        pdf.set_font('Arial', '', 10)
        date_str = date.strftime('%d/%m/%Y') if isinstance(date, datetime) else str(date)
        pdf.cell(CONTENT_X + CONTENT_WIDTH - 110, 5, f"Data: {date_str}", 0, 1, 'R')

        # Barra accent sotto al header
        bar_y = max(y_start + 26, pdf.get_y() + 1)
        _set_fill(pdf, COLOR_ACCENT)
        pdf.rect(CONTENT_X, bar_y, CONTENT_WIDTH, 1.2, style='F')
        _set_fill(pdf, COLOR_SECONDARY)
        pdf.rect(CONTENT_X, bar_y + 1.2, 40, 1.2, style='F')

        pdf.set_y(bar_y + 4)
        _set_text(pdf, COLOR_TEXT)
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_address_boxes(
        pdf,
        sender_data: Dict[str, Any],
        recipient_data: Dict[str, Any],
        col_width: float = 92,
        gap: float = 6,
    ) -> Dict[str, float]:
        """Mittente / Destinatario in box affiancati, con header colorato."""
        y_start = pdf.get_y()
        header_h = 6

        def _draw_box(x: float, title: str, data: Dict[str, Any], font_size_body: int = 9):
            # Header colorato
            _set_fill(pdf, COLOR_ACCENT)
            _set_text(pdf, COLOR_TEXT_ON_ACCENT)
            pdf.set_xy(x, y_start)
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(col_width, header_h, f"  {title}", 0, 0, 'L', True)

            # Corpo
            _set_text(pdf, COLOR_TEXT)
            _set_fill(pdf, COLOR_WHITE)
            pdf.set_xy(x, y_start + header_h)
            pdf.set_font('Arial', '', font_size_body)

            lines = []
            if data.get('name'):
                lines.append(data['name'])
            if data.get('address'):
                lines.append(data['address'])
            if data.get('city') or data.get('postcode'):
                line = f"{data.get('postcode', '')} {data.get('city', '')}".strip()
                if line:
                    lines.append(line)
            if data.get('country'):
                lines.append(data['country'])
            if data.get('vat'):
                lines.append(f"P.IVA: {data['vat']}")
            if data.get('fiscal_code') and data.get('fiscal_code') != data.get('vat'):
                lines.append(f"C.F.: {data['fiscal_code']}")
            if data.get('sdi'):
                lines.append(f"SDI: {data['sdi']}")
            if data.get('pec'):
                lines.append(f"PEC: {data['pec']}")
            if data.get('phone'):
                lines.append(f"Tel: {data['phone']}")
            if data.get('email'):
                lines.append(f"Email: {data['email']}")

            body = "\n".join(lines) if lines else "-"
            _set_draw(pdf, COLOR_BORDER)
            pdf.multi_cell(col_width, 4.6, _safe(body), border='LRB')
            return pdf.get_y()

        y_end_sender = _draw_box(CONTENT_X, 'MITTENTE', sender_data)
        y_end_recipient = _draw_box(CONTENT_X + col_width + gap, 'DESTINATARIO', recipient_data)

        pdf.set_y(max(y_end_sender, y_end_recipient))
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_section_title(pdf, title: str, font_size: int = 9) -> Dict[str, float]:
        """Titolo sezione in accent color, sottile, maiuscolo."""
        _set_text(pdf, COLOR_ACCENT)
        pdf.set_font('Arial', 'B', font_size)
        pdf.cell(0, 5, title.upper(), 0, 1, 'L')
        # Linea sottile sotto al titolo
        y = pdf.get_y()
        _set_draw(pdf, COLOR_ACCENT)
        pdf.set_line_width(0.4)
        pdf.line(CONTENT_X, y, PAGE_RIGHT, y)
        pdf.set_line_width(0.2)
        _set_draw(pdf, COLOR_BORDER)
        _set_text(pdf, COLOR_TEXT)
        pdf.ln(SPACING_BLOCK)
        return {'y_end': pdf.get_y()}

    # Colonne tabella articoli
    _ITEMS_COLS = [28, 78, 14, 28, 14, 28]  # totale = 190
    _ITEMS_HEADERS = ['Codice', 'Descrizione', 'Qta', 'Prezzo', 'IVA', 'Totale']
    _ITEMS_ALIGN = ['L', 'L', 'C', 'R', 'C', 'R']

    @classmethod
    def create_items_table_header(cls, pdf, column_widths: List[float] = None) -> Dict[str, float]:
        widths = column_widths or cls._ITEMS_COLS
        _set_fill(pdf, COLOR_ACCENT)
        _set_text(pdf, COLOR_TEXT_ON_ACCENT)
        pdf.set_font('Arial', 'B', 8.5)
        for i, h in enumerate(cls._ITEMS_HEADERS):
            pdf.cell(widths[i], 7, f" {h}" if cls._ITEMS_ALIGN[i] == 'L' else h, 0, 0, cls._ITEMS_ALIGN[i], True)
        pdf.ln()
        _set_text(pdf, COLOR_TEXT)
        return {'y_end': pdf.get_y()}

    @classmethod
    def add_items_table_row(
        cls,
        pdf,
        code: str,
        description: str,
        quantity: float,
        unit_price: float,
        vat_rate: float,
        total_with_vat: float,
        column_widths: List[float] = None,
        zebra: bool = False,
    ) -> Dict[str, float]:
        widths = column_widths or cls._ITEMS_COLS

        # Calcolo dinamico righe per descrizione (max 2 righe)
        pdf.set_font('Arial', '', 8.5)
        desc = str(description or '')
        # Spezza descrizione lunga su 2 righe approssimando
        max_chars_per_line = 60
        if len(desc) > max_chars_per_line:
            desc_lines = [desc[:max_chars_per_line], desc[max_chars_per_line:max_chars_per_line * 2]]
            if len(desc) > max_chars_per_line * 2:
                desc_lines[1] = desc_lines[1][:-3] + '...'
            row_h = 5.5
            total_h = row_h * 2
        else:
            desc_lines = [desc]
            row_h = 6
            total_h = row_h

        # Fill zebra
        if zebra:
            _set_fill(pdf, COLOR_ROW_ZEBRA)
            pdf.rect(CONTENT_X, pdf.get_y(), CONTENT_WIDTH, total_h, style='F')

        # Bordo inferiore riga (linea separatrice morbida)
        _set_draw(pdf, COLOR_BORDER)

        y_row = pdf.get_y()
        x = CONTENT_X
        # Codice
        pdf.set_xy(x, y_row)
        pdf.cell(widths[0], total_h, _safe(f" {str(code or '')[:20]}"), 0, 0, 'L')
        x += widths[0]
        # Descrizione (multi-line)
        pdf.set_xy(x, y_row + (1 if len(desc_lines) > 1 else 0))
        for i, line in enumerate(desc_lines):
            pdf.set_xy(x, y_row + i * row_h)
            pdf.cell(widths[1], row_h, _safe(f" {line}"), 0, 0, 'L')
        x += widths[1]
        # Qta
        pdf.set_xy(x, y_row)
        pdf.cell(widths[2], total_h, _fmt_qty(quantity), 0, 0, 'C')
        x += widths[2]
        # Prezzo unitario
        pdf.set_xy(x, y_row)
        pdf.cell(widths[3], total_h, _fmt_eur(unit_price), 0, 0, 'R')
        x += widths[3]
        # IVA
        pdf.set_xy(x, y_row)
        pdf.cell(widths[4], total_h, f"{_fmt_num(vat_rate, 0)}%" if vat_rate else '-', 0, 0, 'C')
        x += widths[4]
        # Totale con IVA
        pdf.set_xy(x, y_row)
        pdf.cell(widths[5], total_h, _fmt_eur(total_with_vat), 0, 0, 'R')

        # Linea separatrice
        pdf.set_y(y_row + total_h)
        pdf.line(CONTENT_X, pdf.get_y(), PAGE_RIGHT, pdf.get_y())
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_simple_table(
        pdf,
        headers: List[str],
        rows: List[List[str]],
        column_width: Optional[float] = None,
    ) -> Dict[str, float]:
        """Tabella compatta con header in accent soft."""
        n = max(len(headers), 1)
        cw = column_width or (CONTENT_WIDTH / n)

        _set_fill(pdf, COLOR_ACCENT_SOFT)
        _set_text(pdf, COLOR_ACCENT)
        pdf.set_font('Arial', 'B', 8)
        for header in headers:
            pdf.cell(cw, 5.5, f" {header}", 0, 0, 'L', True)
        pdf.ln()

        _set_text(pdf, COLOR_TEXT)
        pdf.set_font('Arial', '', 9)
        _set_draw(pdf, COLOR_BORDER)
        for row in rows:
            for cell in row:
                pdf.cell(cw, 6, f" {cell}", 'B', 0, 'L')
            pdf.ln()
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_vat_summary_table(
        pdf,
        vat_rate_label: str,
        merchandise_amount: float,
        shipping_amount: float,
        shipping_with_vat: float = 0.0,
        shipping_vat_percentage: float = 0.0,
        total_vat: float = 0.0,
    ) -> Dict[str, float]:
        """Riepilogo IVA: tabella con eventuali righe spese trasporto integrate (non fuori griglia)."""
        col_widths = [30, 50, 50, 60]  # tot 190
        headers = ['Aliquota', 'Imponibile merce', 'Imponibile spese', 'Tot. IVA']
        aligns = ['C', 'R', 'R', 'R']

        # Header
        _set_fill(pdf, COLOR_ACCENT_SOFT)
        _set_text(pdf, COLOR_ACCENT)
        pdf.set_font('Arial', 'B', 8)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 6, h, 0, 0, aligns[i], True)
        pdf.ln()

        # Riga principale (merce)
        _set_text(pdf, COLOR_TEXT)
        pdf.set_font('Arial', '', 9)
        _set_draw(pdf, COLOR_BORDER)
        values = [vat_rate_label, _fmt_eur(merchandise_amount), _fmt_eur(shipping_amount), _fmt_eur(total_vat)]
        for i, v in enumerate(values):
            pdf.cell(col_widths[i], 6.5, v, 'B', 0, aligns[i])
        pdf.ln()

        # Riga eventuale per dettaglio spese trasporto (se presenti)
        if shipping_with_vat or shipping_amount:
            shipping_label = 'Spese trasporto'
            if shipping_vat_percentage:
                shipping_label += f" (IVA {_fmt_num(shipping_vat_percentage, 0)}%)"
            pdf.set_font('Arial', '', 8.5)
            _set_text(pdf, COLOR_TEXT_MUTED)
            # label su 130, valore su 60 (allineato a destra come 'Tot. IVA')
            pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 5.5, f" {shipping_label}", 0, 0, 'L')
            _set_text(pdf, COLOR_TEXT)
            pdf.set_font('Arial', 'B', 8.5)
            pdf.cell(col_widths[3], 5.5, _fmt_eur(shipping_with_vat), 0, 1, 'R')
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_totals_section(
        pdf,
        subtotal: float,
        shipping_cost: float,
        total_with_vat_sum: float,
        total_vat: float,
        total_doc: float,
    ) -> Dict[str, float]:
        """Blocco totali con due colonne ordinate + box accent per 'Totale documento'."""
        y_start = pdf.get_y()

        # Due colonne (Imponibili a sinistra, IVA a destra), label small caps
        left_x = CONTENT_X
        right_x = CONTENT_X + 100
        label_w = 60
        value_w = 30

        rows_left = [
            ('Imponibile merce', _fmt_eur(subtotal)),
            ('Imponibile spese', _fmt_eur(shipping_cost)),
            ('Totale imponibile', _fmt_eur(subtotal + shipping_cost)),
        ]
        rows_right = [
            ('Totale IVA', _fmt_eur(total_vat)),
            ('Merce lorda', _fmt_eur(total_with_vat_sum)),
            ('Spese varie', _fmt_eur(0.0)),
        ]

        pdf.set_font('Arial', '', 9)
        for i, ((l_label, l_val), (r_label, r_val)) in enumerate(zip(rows_left, rows_right)):
            pdf.set_xy(left_x, y_start + i * 5.5)
            _set_text(pdf, COLOR_TEXT_MUTED)
            pdf.cell(label_w, 5.5, l_label, 0, 0, 'L')
            _set_text(pdf, COLOR_TEXT)
            pdf.cell(value_w, 5.5, l_val, 0, 0, 'R')

            pdf.set_xy(right_x, y_start + i * 5.5)
            _set_text(pdf, COLOR_TEXT_MUTED)
            pdf.cell(label_w, 5.5, r_label, 0, 0, 'L')
            _set_text(pdf, COLOR_TEXT)
            pdf.cell(value_w, 5.5, r_val, 0, 1, 'R')

        pdf.ln(SPACING_BLOCK)

        # Box "Totale documento" evidenziato a destra
        box_y = pdf.get_y()
        box_h = 12
        box_w = 90
        box_x = PAGE_RIGHT - box_w

        _set_fill(pdf, COLOR_ACCENT)
        pdf.rect(box_x, box_y, box_w, box_h, style='F')

        _set_text(pdf, COLOR_TEXT_ON_ACCENT)
        pdf.set_xy(box_x + 4, box_y + 2)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(box_w / 2 - 4, 8, 'TOTALE DOCUMENTO', 0, 0, 'L')

        pdf.set_xy(box_x + box_w / 2, box_y + 1)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(box_w / 2 - 4, 10, _fmt_eur(total_doc), 0, 0, 'R')

        _set_text(pdf, COLOR_TEXT)
        pdf.set_y(box_y + box_h)
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_payment_section(
        pdf,
        payment_text: str = '-',
        deadlines_text: str = '',
    ) -> Dict[str, float]:
        """Sezione pagamento/scadenze (mostrata solo se ha contenuto)."""
        if (not payment_text or payment_text.strip() in ('', '-')) and not deadlines_text:
            return {'y_end': pdf.get_y()}

        col_width = CONTENT_WIDTH / 2
        _set_fill(pdf, COLOR_ACCENT_SOFT)
        _set_text(pdf, COLOR_ACCENT)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(col_width, 5.5, '  Pagamento', 0, 0, 'L', True)
        pdf.cell(col_width, 5.5, '  Scadenze', 0, 1, 'L', True)

        _set_text(pdf, COLOR_TEXT)
        pdf.set_font('Arial', '', 9)
        _set_draw(pdf, COLOR_BORDER)
        pdf.cell(col_width, 7, _safe(f"  {payment_text}"), 'B', 0, 'L')
        pdf.cell(col_width, 7, _safe(f"  {deadlines_text}"), 'B', 1, 'L')
        return {'y_end': pdf.get_y()}

    @staticmethod
    def create_transport_signature_section(pdf) -> Dict[str, float]:
        """Mantenuto per compat (non usato nel preventivo nuovo layout)."""
        return {'y_end': pdf.get_y()}

    @staticmethod
    def add_notes(pdf, notes: str, font_size: int = 9) -> Dict[str, float]:
        if not notes:
            return {'y_end': pdf.get_y()}
        _set_text(pdf, COLOR_ACCENT)
        pdf.set_font('Arial', 'B', font_size)
        pdf.cell(0, 5, 'NOTE', 0, 1)
        _set_text(pdf, COLOR_TEXT)
        pdf.set_font('Arial', '', font_size)
        pdf.multi_cell(0, 5, _safe(notes))
        return {'y_end': pdf.get_y()}

    @staticmethod
    def add_footer(pdf, text: str = None) -> Dict[str, float]:
        """Footer in fondo alla pagina, separato da una sottile linea."""
        # Posiziona footer in fondo pagina (margin bottom ~10)
        pdf.set_y(-18)
        _set_draw(pdf, COLOR_BORDER)
        pdf.line(CONTENT_X, pdf.get_y(), PAGE_RIGHT, pdf.get_y())
        pdf.ln(1)

        if text is None:
            text = f"Documento generato automaticamente - {datetime.now().strftime('%d/%m/%Y %H:%M')}"

        _set_text(pdf, COLOR_TEXT_MUTED)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 5, text, 0, 1, 'C')
        _set_text(pdf, COLOR_TEXT)
        return {'y_end': pdf.get_y()}
