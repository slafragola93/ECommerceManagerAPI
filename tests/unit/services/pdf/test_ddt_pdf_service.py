"""Unit test generazione PDF DDT — regressione Decimal vs float e IVA."""
from datetime import datetime
from decimal import Decimal

import pytest

from src.schemas.ddt_schema import (
    DDTDetailSchema,
    DDTPackageSchema,
    DDTResponseSchema,
    DDTSenderSchema,
)
from src.services.pdf.ddt_pdf_service import DDTPDFService


class FakeTaxRepo:
    _RATES = {3: 22.0, 5: 10.0}

    def get_percentage_by_id(self, id_tax: int):
        return self._RATES.get(id_tax)


def _minimal_ddt(**overrides) -> DDTResponseSchema:
    base = {
        "id_order_document": 1,
        "document_number": 100,
        "type_document": "DDT",
        "date_add": datetime(2026, 6, 16, 10, 0, 0),
        "updated_at": datetime(2026, 6, 16, 10, 0, 0),
        "note": None,
        "total_weight": Decimal("2.500"),
        "total_price_with_tax": Decimal("122.00"),
        "total_discount": Decimal("0.00"),
        "id_order": 42,
        "customer": {"firstname": "Mario", "lastname": "Rossi"},
        "address_delivery": {
            "address1": "Via Roma 1",
            "city": "Napoli",
            "postcode": "80100",
            "phone": "0811234567",
        },
        "shipping": {
            "price_tax_excl": Decimal("10.00"),
            "price_tax_incl": Decimal("12.20"),
            "weight": Decimal("1.500"),
            "vat_percentage": Decimal("22"),
        },
        "details": [
            DDTDetailSchema(
                id_order_detail=1,
                id_product=10,
                product_name="Prodotto test",
                product_reference="REF-001",
                product_qty=2,
                product_price=Decimal("50.00"),
                product_weight=Decimal("1.000"),
                id_tax=3,
            )
        ],
        "packages": [],
        "sender": DDTSenderSchema(
            company_name="Elettronew Srl",
            address="Via Test 1",
            vat="IT12345678901",
            phone="0810000000",
            email="info@test.it",
        ),
        "is_modifiable": False,
    }
    base.update(overrides)
    return DDTResponseSchema(**base)


class TestDDTPDFService:
    def test_generate_pdf_with_decimal_shipping_does_not_raise(self):
        """Regression: float + Decimal causava 500 in create_totals_section."""
        service = DDTPDFService(tax_repo=FakeTaxRepo())
        pdf_bytes = service.generate_pdf(ddt_data=_minimal_ddt())

        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 100
        assert pdf_bytes[:4] == b"%PDF"

    def test_resolve_vat_rate_uses_tax_repo_not_id(self):
        service = DDTPDFService(tax_repo=FakeTaxRepo())
        assert service._resolve_vat_rate(3) == 22.0
        assert service._resolve_vat_rate(99) == 0.0

    def test_package_count_defaults_to_one(self):
        assert DDTPDFService._package_count(_minimal_ddt()) == 1

    def test_package_count_from_packages_list(self):
        ddt = _minimal_ddt(
            packages=[
                DDTPackageSchema(
                    id_order_package=1,
                    height=10,
                    width=10,
                    depth=10,
                    weight=1,
                    value=100,
                ),
                DDTPackageSchema(
                    id_order_package=2,
                    height=10,
                    width=10,
                    depth=10,
                    weight=1,
                    value=100,
                ),
            ]
        )
        assert DDTPDFService._package_count(ddt) == 2

    def test_row_totals_apply_reduction_percent(self):
        service = DDTPDFService(tax_repo=FakeTaxRepo())
        ddt = _minimal_ddt(
            details=[
                DDTDetailSchema(
                    id_order_detail=1,
                    id_product=10,
                    product_name="Sconto test",
                    product_reference="REF-002",
                    product_qty=2,
                    product_price=Decimal("100.00"),
                    product_weight=Decimal("0.500"),
                    id_tax=3,
                    reduction_percent=Decimal("10.00"),
                )
            ],
            total_price_with_tax=Decimal("219.60"),
        )
        pdf_bytes = service.generate_pdf(ddt_data=ddt)
        assert pdf_bytes[:4] == b"%PDF"
