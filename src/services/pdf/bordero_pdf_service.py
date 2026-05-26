"""Servizio PDF per generazione borderò spedizioni.

Genera un PDF tabellare A4 landscape con la lista delle spedizioni in stato
"Spediti" per un corriere selezionato. Riprende il pattern di
`DDTPDFService` (estensione di `BasePDFService`, fpdf2, helper statici,
output bytes).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.schemas.bordero_schema import BorderoRow
from src.services.pdf.base_pdf_service import BasePDFService


# Larghezze colonne in mm su A4 landscape.
# Area utile = 297 - 2*8 (margini) = 281 mm. Somma colonne = 281 mm.
COLUMN_WIDTHS: List[float] = [
    18,   # Corriere
    14,   # ID
    32,   # Numero Spedizione (tracking)
    16,   # RIF.
    40,   # Destinatario
    50,   # Indirizzo
    12,   # Colli
    16,   # Peso
    18,   # C/Ass.
    65,   # Articoli
]
COLUMN_HEADERS: List[str] = [
    "Corriere",
    "ID",
    "Numero Spedizione",
    "RIF.",
    "Destinatario",
    "Indirizzo",
    "Colli",
    "Peso",
    "C/Ass.",
    "Articoli",
]
PAGE_MARGIN: float = 8.0
ROW_HEIGHT: float = 6.0


class BorderoPDFService(BasePDFService):
    """Servizio per la generazione del PDF borderò spedizioni."""

    def generate_pdf(
        self,
        rows: List[BorderoRow],
        company_info: Optional[Dict[str, Any]] = None,
        carrier_name: str = "",
        generated_at: Optional[datetime] = None,
    ) -> bytes:
        """Genera il PDF del borderò.

        Args:
            rows: Lista di `BorderoRow`, una per spedizione.
            company_info: Dict con i campi di `AppConfiguration.company_info`
                (company_name, address, civic_number, postal_code, city,
                province, phone, email, ...). Usato per l'header mittente.
            carrier_name: Nome del corriere per il titolo del documento.
            generated_at: Timestamp di generazione (default: now).

        Returns:
            bytes: Contenuto del PDF.
        """
        try:
            from fpdf import FPDF
        except ImportError as exc:
            raise Exception(
                "Libreria fpdf2 non installata. Installare con: pip install fpdf2"
            ) from exc

        generated_at = generated_at or datetime.now()
        company_info = company_info or {}

        pdf = FPDF(orientation="L", format="A4")
        pdf.set_auto_page_break(auto=True, margin=PAGE_MARGIN)
        pdf.core_fonts_encoding = "cp1252"
        pdf.set_margins(left=PAGE_MARGIN, top=PAGE_MARGIN, right=PAGE_MARGIN)

        # Callback per ripetere l'header tabella su ogni pagina.
        def _draw_header() -> None:
            self._render_document_header(pdf, company_info, carrier_name, generated_at)
            self._render_table_header(pdf)

        pdf.add_page()
        _draw_header()

        if not rows:
            # Caso "0 ordini idonei": il contratto FE prevede comunque PDF
            # valido + count=0 in header (no eccezione). Renderizziamo una
            # riga informativa nella tabella per chiarezza visuale.
            self._render_empty_message(pdf)
        else:
            # Righe della tabella: gestione paginazione manuale + ripetizione header.
            usable_height = pdf.h - PAGE_MARGIN
            for row in rows:
                if pdf.get_y() + ROW_HEIGHT > usable_height - 15:  # 15mm reserved per footer
                    pdf.add_page()
                    _draw_header()
                self._render_table_row(pdf, row)

        self._render_footer(pdf, rows)

        return pdf.output()

    # ------------------------------------------------------------------
    # Helper interni di rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _safe(text: Any) -> str:
        """Converte qualsiasi valore in stringa cp1252-safe per fpdf2 core fonts."""
        if text is None:
            return ""
        try:
            return str(text).encode("cp1252", errors="replace").decode("cp1252")
        except Exception:
            return str(text)

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if text is None:
            return ""
        text = str(text)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1] + "…"

    @staticmethod
    def _compose_company_address(company_info: Dict[str, Any]) -> str:
        """Compone la riga indirizzo del mittente: 'Via X 1, 12345 Citta (PR)'."""
        address = company_info.get("address") or ""
        civic = company_info.get("civic_number") or ""
        line1_parts: List[str] = []
        if address:
            line1_parts.append(address)
        if civic:
            line1_parts.append(str(civic))
        line1 = " ".join(line1_parts).strip()

        postal = company_info.get("postal_code") or ""
        city = company_info.get("city") or ""
        province = company_info.get("province") or ""
        line2_parts: List[str] = []
        if postal:
            line2_parts.append(str(postal))
        if city:
            line2_parts.append(str(city))
        line2 = " ".join(line2_parts).strip()
        if province:
            line2 = f"{line2} ({province})".strip()

        full = ", ".join(p for p in [line1, line2] if p)
        return full

    @classmethod
    def _render_document_header(
        cls,
        pdf: Any,
        company_info: Dict[str, Any],
        carrier_name: str,
        generated_at: datetime,
    ) -> None:
        """Disegna l'header del documento: mittente a sinistra, titolo + data a destra."""
        y_start = pdf.get_y()

        # Box mittente (sinistra)
        pdf.set_xy(PAGE_MARGIN, y_start)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 5, cls._safe(company_info.get("company_name") or ""), 0, 1, "L")

        pdf.set_x(PAGE_MARGIN)
        pdf.set_font("Arial", "", 9)
        composed_address = cls._compose_company_address(company_info)
        if composed_address:
            pdf.cell(0, 4, cls._safe(composed_address), 0, 1, "L")
            pdf.set_x(PAGE_MARGIN)

        phone = company_info.get("phone") or ""
        email = company_info.get("email") or ""
        contact_parts: List[str] = []
        if phone:
            contact_parts.append(f"Tel: {phone}")
        if email:
            contact_parts.append(f"Email: {email}")
        if contact_parts:
            pdf.cell(0, 4, cls._safe(" - ".join(contact_parts)), 0, 1, "L")

        # Titolo + data (destra, sovrapposto)
        title = f"Riepilogo spedizioni - {carrier_name}" if carrier_name else "Riepilogo spedizioni"
        pdf.set_xy(180, y_start)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(108, 6, cls._safe(title), 0, 1, "R")

        pdf.set_xy(180, y_start + 7)
        pdf.set_font("Arial", "", 9)
        pdf.cell(
            108,
            5,
            cls._safe(f"Generato il {generated_at.strftime('%d/%m/%Y %H:%M')}"),
            0,
            1,
            "R",
        )

        pdf.set_y(max(pdf.get_y(), y_start + 22))
        pdf.ln(2)

    @classmethod
    def _render_table_header(cls, pdf: Any) -> None:
        """Disegna l'intestazione della tabella (10 colonne)."""
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(224, 224, 224)
        pdf.set_x(PAGE_MARGIN)
        for header, width in zip(COLUMN_HEADERS, COLUMN_WIDTHS):
            pdf.cell(width, 6, cls._safe(header), 1, 0, "C", True)
        pdf.ln()

    @classmethod
    def _render_empty_message(cls, pdf: Any) -> None:
        """Riga unica che copre tutta la larghezza tabella: 'Nessuna spedizione'."""
        total_width = sum(COLUMN_WIDTHS)
        pdf.set_font("Arial", "I", 9)
        pdf.set_x(PAGE_MARGIN)
        pdf.cell(
            total_width,
            ROW_HEIGHT * 1.5,
            cls._safe("Nessuna spedizione idonea per il corriere selezionato."),
            1,
            1,
            "C",
        )

    @classmethod
    def _render_table_row(cls, pdf: Any, row: BorderoRow) -> None:
        """Disegna una riga della tabella borderò."""
        pdf.set_font("Arial", "", 7)
        pdf.set_x(PAGE_MARGIN)

        cells: List[tuple] = [
            (cls._truncate(row.carrier_name, 12), "L"),
            (str(row.id_shipping), "C"),
            (cls._truncate(row.tracking or "", 22), "L"),
            (str(row.id_order), "C"),
            (cls._truncate(row.recipient, 30), "L"),
            (cls._truncate(row.address, 40), "L"),
            (str(row.packages_count), "C"),
            (f"{float(row.weight):.2f}", "R"),
            (f"{float(row.cash_on_delivery):.2f}", "R") if row.cash_on_delivery else ("-", "C"),
            (cls._truncate(row.articles, 55), "L"),
        ]

        for (value, align), width in zip(cells, COLUMN_WIDTHS):
            pdf.cell(width, ROW_HEIGHT, cls._safe(value), 1, 0, align)
        pdf.ln()

    @classmethod
    def _render_footer(cls, pdf: Any, rows: List[BorderoRow]) -> None:
        """Disegna il footer: linea firma + totali."""
        if pdf.get_y() + 30 > pdf.h - PAGE_MARGIN:
            pdf.add_page()

        pdf.ln(8)
        pdf.set_x(PAGE_MARGIN)
        pdf.set_font("Arial", "", 9)
        pdf.cell(0, 5, cls._safe("Firma _________________________________________"), 0, 1, "L")

        total_shipments = len(rows)
        total_packages = sum(int(r.packages_count or 0) for r in rows)
        total_weight = sum(float(r.weight or 0.0) for r in rows)
        total_cod = sum(float(r.cash_on_delivery or 0.0) for r in rows)

        pdf.ln(4)
        pdf.set_x(PAGE_MARGIN)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(
            0,
            5,
            cls._safe(
                f"TOT spedizioni: {total_shipments}    "
                f"TOT colli: {total_packages}    "
                f"TOT peso: {total_weight:.2f} kg    "
                f"TOT C/Ass.: {total_cod:.2f} EUR"
            ),
            0,
            1,
            "L",
        )
