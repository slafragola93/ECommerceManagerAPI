"""Unit test — normalizzazione FK opzionali su AddressSchema."""
import pytest

from src.schemas.address_schema import AddressSchema


def _base_payload(**overrides):
    data = {
        "firstname": "Mario",
        "lastname": "Rossi",
        "address1": "Via Roma 1",
        "state": "RM",
        "postcode": "00100",
        "city": "Roma",
        "phone": "0612345678",
    }
    data.update(overrides)
    return data


def test_id_country_zero_normalized_to_none():
    schema = AddressSchema(**_base_payload(id_country=0))
    assert schema.id_country is None


def test_id_customer_zero_normalized_to_none():
    schema = AddressSchema(**_base_payload(id_customer=0))
    assert schema.id_customer is None


@pytest.mark.asyncio
async def test_update_address_skips_zero_id_country():
    from unittest.mock import MagicMock

    from src.models.address import Address
    from src.services.routers.address_service import AddressService

    address = Address(
        id_address=631897,
        id_country=217,
        firstname="enricaaaa",
        lastname="stancooo",
        address1="via blabla 11",
        city="marano di napoli",
        postcode="80016",
        state="napoli",
        phone="3347122853",
    )
    repo = MagicMock()
    repo.get_by_id_or_raise.return_value = address
    repo.update.side_effect = lambda row: row

    service = AddressService(repo)
    payload = AddressSchema(
        **_base_payload(id_country=0, firstname="enricaaaaSSSSSSSSS")
    )

    updated = await service.update_address(631897, payload)

    assert updated.firstname == "enricaaaaSSSSSSSSS"
    assert updated.id_country == 217
    repo.update.assert_called_once()
