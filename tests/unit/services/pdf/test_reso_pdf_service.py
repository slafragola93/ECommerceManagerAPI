"""Unit test PDF reso: Sc. %/importo + voce Sconto nei totali."""
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.services.pdf.reso_pdf_layout import ResoPDFLayout
from src.services.pdf.reso_pdf_service import ResoPDFService


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


def _address():
    return SimpleNamespace(
        firstname="Mario",
        lastname="Rossi",
        company=None,
        address1="Via Roma 1",
        address2="",
        postcode="00100",
        city="Roma",
        state="RM",
        phone="061234567",
        mobile_phone=None,
        country=SimpleNamespace(iso_code="IT", name="Italia"),
    )


class TestResoPDFLayout:
    def test_amount_discount_shows_cifra_and_totals_sconto(self):
        pdf = ResoPDFLayout.create_pdf()
        ResoPDFLayout.render(
            pdf,
            doc_number="12",
            doc_date=datetime(2026, 7, 28),
            company_config=_company(),
            logo_path=None,
            invoice_address=_address(),
            delivery_address=_address(),
            order_reference="509488/W",
            order_date=datetime(2026, 7, 14),
            details=[
                {
                    "product_reference": "FHA50Z",
                    "product_name": "Climatizzatore Daikin",
                    "product_qty": 1,
                    "unit_price_net": 2565.57,
                    "total_price_net": 2065.57,
                    "reduction_percent": 0.0,
                    "reduction_amount": 500.0,
                    "line_discount": 500.0,
                    "vat_rate": 22.0,
                    "is_shipping": False,
                }
            ],
            totals={
                "merchandise_net": 2065.57,
                "shipping_incl": 0.0,
                "total_vat": 454.43,
                "total_gross": 2520.0,
                "total_discount": 500.0,
            },
        )
        text = _pdf_text(pdf.output())
        assert "RESO" in text
        assert "500,00" in text
        assert "19,49" not in text
        assert "Sconto" in text


class TestResoPDFService:
    def test_compute_totals_includes_line_discount(self):
        svc = ResoPDFService()
        fiscal = SimpleNamespace(
            includes_shipping=False,
            products_total_price_net=2065.57,
            total_price_net=2065.57,
            total_price_with_tax=2520.0,
        )
        order = SimpleNamespace(total_price_with_tax=2520.0)
        details = [
            {
                "total_price_net": 2065.57,
                "line_discount": 500.0,
                "is_shipping": False,
            }
        ]
        totals = svc._compute_totals(fiscal, order, details, shipping=None)
        assert totals["total_discount"] == pytest.approx(500.0)
        assert totals["merchandise_net"] == pytest.approx(2065.57)

    def test_build_details_scales_amount_for_partial_qty(self):
        from src.models.fiscal_document_detail import FiscalDocumentDetail
        from src.models.order_detail import OrderDetail
        from src.models.tax import Tax

        svc = ResoPDFService()
        fiscal = SimpleNamespace(
            id_fiscal_document=1,
            includes_shipping=False,
        )
        order = SimpleNamespace(id_order=10)
        detail = SimpleNamespace(
            id_order_detail=99,
            product_qty=1,
            unit_price_net=100.0,
            total_price_net=90.0,
            id_tax=1,
        )
        od = SimpleNamespace(
            id_order_detail=99,
            product_qty=2,
            product_name="Prodotto",
            product_reference="SKU1",
            reduction_percent=0.0,
            reduction_amount=20.0,  # su qty 2 → 10 sul reso qty 1
        )
        tax = SimpleNamespace(id_tax=1, percentage=22.0)

        def query_side_effect(model):
            m = MagicMock()
            if model is FiscalDocumentDetail:
                m.filter.return_value.all.return_value = [detail]
            elif model is OrderDetail:
                m.filter.return_value = [od]
            elif model is Tax:
                m.filter.return_value = [tax]
            else:
                m.filter.return_value.all.return_value = []
            return m

        db = MagicMock()
        db.query.side_effect = query_side_effect

        rows = svc.build_details(db, fiscal, order, shipping=None)
        assert len(rows) == 1
        assert rows[0]["reduction_amount"] == pytest.approx(10.0)
        assert rows[0]["line_discount"] == pytest.approx(10.0)
