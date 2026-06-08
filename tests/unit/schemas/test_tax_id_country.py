"""Unit test — serializzazione id_country su Tax (BE-ALIQ-04)."""
import pytest

from src.models.country import Country
from src.models.tax import Tax
from src.schemas.tax_schema import (
    TaxCountryDefaultResponseSchema,
    TaxResponseSchema,
    TaxSchema,
    coerce_optional_int,
    serialize_tax_response,
    serialize_taxes_response,
)


class TestCoerceOptionalInt:
    def test_none_and_empty(self):
        assert coerce_optional_int(None) is None
        assert coerce_optional_int("") is None
        assert coerce_optional_int("   ") is None

    def test_int_passthrough(self):
        assert coerce_optional_int(12) == 12

    def test_string_numeric(self):
        assert coerce_optional_int("7") == 7

    def test_bool_rejected(self):
        with pytest.raises(ValueError):
            coerce_optional_int(True)


class TestTaxSchemaIdCountry:
    def test_accepts_string_on_input(self):
        schema = TaxSchema(name="IVA Test 22%", id_country="5")
        assert schema.id_country == 5

    def test_null_country(self):
        schema = TaxSchema(name="IVA Global 22%", id_country=None)
        assert schema.id_country is None


class TestTaxResponseSchemaIdCountry:
    def test_from_orm_with_null_country(self, db_session):
        tax = Tax(name="IVA Global", percentage=22, code="G", is_default=1)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        payload = serialize_tax_response(tax)
        assert payload["id_country"] is None
        assert isinstance(payload["id_tax"], int)

    def test_from_dict_with_string_country(self):
        payload = serialize_tax_response(
            {
                "id_tax": 1,
                "id_country": "9",
                "is_default": 0,
                "name": "IVA 22%",
                "note": "",
                "percentage": 22,
                "electronic_code": "",
            }
        )
        assert payload["id_country"] == 9

    def test_country_default_schema_inherits_coercion(self, db_session):
        country = Country(id_origin=1, name="Italy", iso_code="IT")
        db_session.add(country)
        db_session.commit()
        tax = Tax(
            id_country=country.id_country,
            is_default=1,
            name="IVA IT 22%",
            percentage=22,
            code="IT",
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        schema = TaxCountryDefaultResponseSchema.model_validate(
            {
                **serialize_tax_response(tax),
                "country_iso_code": "IT",
                "country_name": "Italy",
            }
        )
        assert schema.id_country == country.id_country

    def test_serialize_taxes_response_list(self, db_session):
        tax = Tax(name="IVA 10%", percentage=10, code="T10", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        items = serialize_taxes_response([tax])
        assert len(items) == 1
        assert items[0]["id_country"] is None
