"""Unit test generazione PDF ricevuta — layout elettronew."""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.services.ricevute.date_utils import format_emission_datetime
from src.services.pdf.ricevuta_pdf_layout import (
    RicevutaPDFLayout,
    _labels_for_country,
    _vat_display,
)
from src.services.pdf.ricevuta_pdf_service import RicevutaPDFService


def _address(**kwargs):
    defaults = {
        "firstname": "Monique",
        "lastname": "BONINO THEVENARD",
        "address1": "78 Strada Di L'aghja",
        "postcode": "20243",
        "city": "Prunelli-di-Fiumorbo",
        "state": "",
        "phone": "+33667100120",
        "mobile_phone": "0667100120",
        "country": SimpleNamespace(iso_code="FR", name="Francia"),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _minimal_context():
    return {
        "ricevuta_numero": 7055,
        "ricevuta_anno": 2026,
        "data_emissione": datetime(2026, 7, 8, 12, 30),
        "company_config": {
            "company_name": "Web Market s.r.l.",
            "address": "Corso Vittorio Emanuele, 110/5",
            "postal_code": "80121",
            "city": "Napoli",
            "province": "NA",
            "vat_number": "IT08632861210",
            "fiscal_code": "08632861210",
            "iban": "IT79A0306939845100000014622",
        },
        "logo_path": None,
        "invoice_address": _address(),
        "delivery_address": _address(),
        "order_reference": "506886/W",
        "order_date": datetime(2026, 7, 6),
        "details": [
            {
                "product_reference": "KIT HAIGEOSR12",
                "product_name": "Climatizzatore Haier Geos R 3,5KW 12000Btu A++/A+ R32 WIFI",
                "product_qty": 1,
                "unit_price": 349.98,
                "total_price_net": 349.98,
                "reduction_percent": 0.0,
                "vat_rate": 20.0,
                "tax_code": "20FR",
            }
        ],
        "totals": {
            "merchandise_net": 349.98,
            "shipping_incl": 0.0,
            "total_vat": 70.0,
            "total_gross": 419.98,
        },
        "locale_iso": "FR",
    }


class TestRicevutaPDFLayout:
    def test_labels_french_for_fr_iso(self):
        labels = _labels_for_country("FR")
        assert labels["billing"] == "En-t\u00eate"
        assert labels["headers"][2] == "Prix"

    def test_vat_display_prefers_tax_code(self):
        assert _vat_display(20.0, "20FR", "FR") == "20FR"
        assert _vat_display(20.0, None, "FR") == "20FR"

    def test_render_produces_valid_pdf_bytes(self):
        pdf = RicevutaPDFLayout.create_pdf()
        ctx = _minimal_context()
        assert format_emission_datetime(ctx["data_emissione"]) == "08/07/2026 14:30"
        RicevutaPDFLayout.render(pdf, **ctx)
        out = pdf.output()
        assert isinstance(out, (bytes, bytearray))
        assert out[:4] == b"%PDF"


class TestRicevutaPDFService:
    def test_compute_totals_from_order(self):
        order = SimpleNamespace(
            products_total_price_net=Decimal("349.98"),
            products_total_price_with_tax=Decimal("419.98"),
            total_price_net=Decimal("349.98"),
            total_price_with_tax=Decimal("419.98"),
            shipments=None,
        )
        details = [{"total_price_net": 349.98}]
        totals = RicevutaPDFService._compute_totals(order, details)
        assert totals["merchandise_net"] == pytest.approx(349.98)
        assert totals["total_vat"] == pytest.approx(70.0)
        assert totals["total_gross"] == pytest.approx(419.98)

    def test_compute_totals_includes_shipping(self):
        order = SimpleNamespace(
            products_total_price_net=Decimal("100.00"),
            products_total_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("110.00"),
            total_price_with_tax=Decimal("134.20"),
        )
        shipping = SimpleNamespace(price_tax_excl=Decimal("10.00"), price_tax_incl=Decimal("12.20"))
        details = [{"total_price_net": 100.0, "is_shipping": False}]
        totals = RicevutaPDFService._compute_totals(order, details, shipping)
        assert totals["merchandise_net"] == pytest.approx(100.0)
        assert totals["shipping_incl"] == pytest.approx(12.2)
        assert totals["shipping_net"] == pytest.approx(10.0)
        assert totals["total_gross"] == pytest.approx(134.2)
