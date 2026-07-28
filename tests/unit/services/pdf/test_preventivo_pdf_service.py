"""Unit test PDF preventivo: colonna Sc. (%/importo) + voce Sconto nei totali."""
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

from src.services.pdf.preventivo_pdf_service import PreventivoPDFService


def _pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _sender():
    return {
        "company_name": "Web Market s.r.l.",
        "address": "Corso Vittorio Emanuele",
        "civic_number": "110",
        "postal_code": "80121",
        "city": "Napoli",
        "province": "NA",
        "vat_number": "IT08632861210",
        "fiscal_code": "08632861210",
        "country": "Italia",
    }


class TestPreventivoPDFDiscount:
    def test_headers_include_sc(self):
        assert "Sc." in PreventivoPDFService._ITEMS_HEADERS
        assert len(PreventivoPDFService._ITEMS_COLS) == 7
        assert sum(PreventivoPDFService._ITEMS_COLS) == 190

    def test_pdf_amount_discount_shows_cifra_and_totals_sconto(self):
        svc = PreventivoPDFService(db_session=None)
        preventivo = SimpleNamespace(
            document_number="P-100",
            date_add=datetime(2026, 7, 14),
            note=None,
            total_price_with_tax=2520.0,
            total_iva=454.43,
            total_discount=0.0,
            total_discounts=0.0,
            articoli=[
                SimpleNamespace(
                    product_reference="FHA50Z",
                    product_name="Climatizzatore Daikin",
                    product_qty=1,
                    product_price=2565.57,
                    unit_price_net=2565.57,
                    unit_price_with_tax=None,
                    total_price_net=2065.57,
                    total_price_with_tax=2520.0,
                    taxable=2065.57,
                    prezzo_totale_riga=2520.0,
                    reduction_percent=0.0,
                    reduction_amount=500.0,
                    aliquota_iva=22.0,
                    id_tax=None,
                    product_weight=40.0,
                )
            ],
        )
        out = svc.generate_pdf(
            preventivo_data=preventivo,
            sender_config=_sender(),
        )
        assert out[:4] == b"%PDF"
        text = _pdf_text(out)
        assert "500,00" in text
        assert "Sconto" in text
        assert "19,49" not in text

    def test_pdf_percent_discount_shows_pct(self):
        svc = PreventivoPDFService(db_session=None)
        preventivo = SimpleNamespace(
            document_number="P-101",
            date_add=datetime(2026, 7, 14),
            note=None,
            total_price_with_tax=219.6,
            total_iva=39.6,
            total_discount=0.0,
            articoli=[
                SimpleNamespace(
                    product_reference="SKU1",
                    product_name="Prodotto test",
                    product_qty=1,
                    product_price=200.0,
                    unit_price_net=200.0,
                    unit_price_with_tax=None,
                    total_price_net=180.0,
                    total_price_with_tax=219.6,
                    taxable=180.0,
                    prezzo_totale_riga=219.6,
                    reduction_percent=10.0,
                    reduction_amount=0.0,
                    aliquota_iva=22.0,
                    id_tax=None,
                    product_weight=1.0,
                )
            ],
        )
        out = svc.generate_pdf(
            preventivo_data=preventivo,
            sender_config=_sender(),
        )
        text = _pdf_text(out)
        assert "10,00 %" in text or "10,00%" in text
