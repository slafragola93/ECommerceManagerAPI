"""Unit test — Tax.percentage DECIMAL (BE-ALIQ-05)."""
from decimal import Decimal

import pytest

from src.models.country import Country
from src.models.tax import Tax
from src.schemas.tax_schema import (
    TaxResponseSchema,
    TaxSchema,
    coerce_tax_percentage,
    serialize_tax_response,
)
from src.vies.eu_vat_seed import EU_VAT_STANDARD_RATES, setup_eu_country_taxes


class TestCoerceTaxPercentage:
    def test_integer_input(self):
        assert coerce_tax_percentage(22) == Decimal("22.00")

    def test_decimal_string(self):
        assert coerce_tax_percentage("25.5") == Decimal("25.50")

    def test_float_input(self):
        assert coerce_tax_percentage(5.5) == Decimal("5.50")

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            coerce_tax_percentage(101)


class TestTaxPercentageApiSchema:
    def test_response_serializes_as_json_number(self, db_session):
        tax = Tax(
            name="IVA FI 25.5%",
            percentage=Decimal("25.50"),
            code="FI",
            is_default=0,
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        payload = serialize_tax_response(tax)
        assert payload["percentage"] == 25.5
        assert isinstance(payload["percentage"], float)

    def test_post_schema_accepts_decimal_string(self):
        schema = TaxSchema(name="IVA FR 5.5%", percentage="5.5")
        assert schema.percentage == Decimal("5.50")

    def test_response_from_orm_decimal(self, db_session):
        tax = Tax(name="IVA 22%", percentage=Decimal("22.00"), code="T22")
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        parsed = TaxResponseSchema.model_validate(tax)
        assert parsed.percentage == Decimal("22.00")


class TestEuVatSeedFinlandDecimal:
    def test_fi_rate_is_25_5(self):
        fi = next(item for item in EU_VAT_STANDARD_RATES if item[0] == "FI")
        assert fi[1] == Decimal("25.50")

    def test_seed_creates_fi_25_5(self, db_session):
        country = Country(id_origin=1, name="Finland", iso_code="FI")
        db_session.add(country)
        db_session.commit()

        setup_eu_country_taxes(db_session)

        tax = (
            db_session.query(Tax)
            .join(Country, Tax.id_country == Country.id_country)
            .filter(Country.iso_code == "FI", Tax.is_default == 1)
            .first()
        )
        assert tax is not None
        assert tax.percentage == Decimal("25.50")
