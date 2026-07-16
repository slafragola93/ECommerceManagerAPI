"""Test mapper customer/address condivisi ricevuta/fattura."""
from src.services.ricevute.order_embed_formatters import (
    map_ricevuta_address_embed,
    map_ricevuta_customer_embed,
)


class TestOrderEmbedFormattersCustomerAddress:
    def test_map_customer_embed(self):
        customer = type(
            "Customer",
            (),
            {
                "id_customer": 5,
                "firstname": "Luigi",
                "lastname": "Verdi",
                "email": "luigi@example.com",
            },
        )()
        result = map_ricevuta_customer_embed(customer)
        assert result.id_customer == 5
        assert result.firstname == "Luigi"
        assert result.email == "luigi@example.com"

    def test_map_address_embed_with_country(self):
        country = type("Country", (), {"iso_code": "IT", "name": "Italia"})()
        address = type(
            "Address",
            (),
            {
                "id_address": 10,
                "company": "Acme",
                "firstname": "Mario",
                "lastname": "Rossi",
                "address1": "Via Roma 1",
                "address2": None,
                "city": "Milano",
                "postcode": "20100",
                "state": "MI",
                "phone": "021234567",
                "vat": "IT12345678901",
                "country": country,
            },
        )()
        result = map_ricevuta_address_embed(address)
        assert result.id_address == 10
        assert result.country.iso_code == "IT"
