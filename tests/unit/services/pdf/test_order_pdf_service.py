"""Unit test PDF ordine: sconto % vs importo + voce Sconto nei totali."""
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

from src.services.pdf.order_pdf_service import OrderPDFService


def _pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _company():
    return {
        "company_name": "Web Market s.r.l.",
        "address": "Corso Vittorio Emanuele",
        "postal_code": "80121",
        "city": "Napoli",
        "province": "NA",
        "vat_number": "IT08632861210",
        "fiscal_code": "08632861210",
        "iban": "IT79A0306939845100000014622",
    }


class TestOrderPDFDiscount:
    def test_line_amounts_amount_discount(self):
        detail = SimpleNamespace(
            product_qty=1,
            unit_price_net=2565.57,
            product_price=2565.57,
            total_price_net=2065.57,
            reduction_percent=0.0,
            reduction_amount=500.0,
        )
        impon, net, pct, discount = OrderPDFService._line_amounts(detail, 22.0)
        assert impon == pytest.approx(2565.57)
        assert net == pytest.approx(2065.57)
        assert pct == pytest.approx(0.0)
        assert discount == pytest.approx(500.0)

    def test_compute_totals_includes_discount(self):
        order = SimpleNamespace(
            products_total_price_net=2065.57,
            total_price_net=2091.79,
            total_price_with_tax=2551.99,
        )
        details = [
            SimpleNamespace(
                product_qty=1,
                unit_price_net=2565.57,
                product_price=2565.57,
                total_price_net=2065.57,
                reduction_percent=0.0,
                reduction_amount=500.0,
            )
        ]
        totals = OrderPDFService._compute_totals(
            order, details, shipping=None, tax_percentages={}
        )
        assert totals["total_discount"] == pytest.approx(500.0)

    def test_pdf_shows_amount_not_percent_and_totals_sconto(self):
        svc = OrderPDFService()
        order = SimpleNamespace(
            id_order=1,
            id_origin=0,
            reference="509488/W",
            date_add=datetime(2026, 7, 14),
            products_total_price_net=2065.57,
            total_price_net=2091.79,
            total_price_with_tax=2551.99,
            general_note="",
        )
        details = [
            SimpleNamespace(
                product_reference="FHA50Z",
                product_name="Climatizzatore Daikin",
                product_qty=1,
                unit_price_net=2565.57,
                product_price=2565.57,
                total_price_net=2065.57,
                reduction_percent=0.0,
                reduction_amount=500.0,
                id_tax=None,
            )
        ]
        out = svc.generate_pdf(
            order=order,
            order_details=details,
            company_config=_company(),
            payment_name="PayPal",
        )
        assert out[:4] == b"%PDF"
        text = _pdf_text(out)
        assert "500,00" in text
        assert "Sconto" in text
        # non deve mostrare % equivalente inventata in colonna
        assert "19,49" not in text
