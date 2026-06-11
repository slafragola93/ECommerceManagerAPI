"""Integration tests — FastLDV API (GET order + notify-print)."""
from datetime import date

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.settings import get_fastldv_settings
from src.models.address import Address
from src.models.carrier_api import CarrierApi, CarrierTypeEnum
from src.models.country import Country
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.services.routers.auth_service import get_current_user

FASTLDV_TEST_KEY = "test-fastldv-key"


@pytest.fixture(autouse=True)
def fastldv_settings(monkeypatch):
    monkeypatch.setenv("FASTLDV_API_KEY", FASTLDV_TEST_KEY)
    get_fastldv_settings.cache_clear()
    yield
    get_fastldv_settings.cache_clear()


@pytest.fixture
def fastldv_client(test_app):
    test_app.dependency_overrides[get_current_user] = lambda: {
        "username": "admin",
        "id": 1,
        "roles": [{"name": "ADMIN", "permissions": ["R"]}],
    }
    return TestClient(test_app)


def _headers():
    return {"X-FastLDV-Key": FASTLDV_TEST_KEY}


@pytest.fixture
def printable_order(db_session):
    country = Country(name="Italia", iso_code="IT")
    db_session.add(country)
    db_session.commit()

    address = Address(
        id_country=country.id_country,
        firstname="Mario",
        lastname="Rossi",
        city="Napoli",
        postcode="80100",
        date_add=date.today(),
    )
    db_session.add(address)
    db_session.commit()

    carrier_api = CarrierApi(
        name="BRT NAPOLI",
        carrier_type=CarrierTypeEnum.BRT,
        is_active=True,
    )
    db_session.add(carrier_api)
    db_session.commit()

    shipping = Shipping(
        id_carrier_api=carrier_api.id_carrier_api,
        weight=1.5,
        tracking="",
    )
    db_session.add(shipping)
    db_session.commit()

    order = Order(
        id_origin=69099,
        id_order_state=2,
        is_payed=True,
        id_address_delivery=address.id_address,
        id_shipping=shipping.id_shipping,
        total_price_with_tax=100.0,
        products_total_price_with_tax=100.0,
        products_total_price_net=80.0,
        total_price_net=80.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    detail = OrderDetail(
        id_order=order.id_order,
        product_name="Prodotto Test",
        product_reference="SKU-1",
        product_qty=2,
        unit_price_with_tax=50.0,
        unit_price_net=40.0,
        total_price_with_tax=100.0,
        total_price_net=80.0,
    )
    db_session.add(detail)
    db_session.commit()

    return {
        "order": order,
        "shipping": shipping,
        "carrier_api": carrier_api,
    }


@pytest.mark.integration
class TestFastLdvApi:
    def test_get_order_200_printable(self, fastldv_client, printable_order):
        response = fastldv_client.get(
            "/api/v1/fastldv/order/69099",
            headers=_headers(),
            params={"carrier": "BRT NAPOLI"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["id_origin"] == 69099
        assert body["data"]["validation"]["printable"] is True
        assert body["data"]["validation"]["code"] == "OK"
        assert len(body["data"]["lines"]) == 1
        assert body["data"]["lines"][0]["quantity"] == 2
        assert body["data"]["legacy"]["corrieri_carrier"] == "BRT NAPOLI"

    def test_get_order_422_not_paid(self, fastldv_client, printable_order, db_session):
        order = printable_order["order"]
        order.is_payed = False
        db_session.commit()

        response = fastldv_client.get(
            "/api/v1/fastldv/order/69099",
            headers=_headers(),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        assert body["error_code"] == "FASTLDV_NOT_PRINTABLE"
        assert body["data"]["validation"]["code"] == "ORDER_NOT_PAID"
        assert body["data"]["lines"]

    def test_get_order_404(self, fastldv_client):
        response = fastldv_client.get(
            "/api/v1/fastldv/order/99999",
            headers=_headers(),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_order_missing_api_key(self, fastldv_client):
        response = fastldv_client.get("/api/v1/fastldv/order/69099")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_order_401_wrong_key(self, fastldv_client):
        response = fastldv_client.get(
            "/api/v1/fastldv/order/69099",
            headers={"X-FastLDV-Key": "wrong"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_notify_print_200(self, fastldv_client, printable_order, db_session):
        response = fastldv_client.post(
            "/api/v1/fastldv/notify-print",
            headers=_headers(),
            json={
                "id_origin": 69099,
                "tracking": "BRT999888777",
                "operatore": "mario",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["tracking"] == "BRT999888777"

        shipping = (
            db_session.query(Shipping)
            .filter(Shipping.id_shipping == printable_order["shipping"].id_shipping)
            .first()
        )
        assert shipping.tracking == "BRT999888777"

    def test_get_order_internal_id_origin_zero_by_id_order(
        self, fastldv_client, db_session
    ):
        """Ordine gestionale (id_origin=0): lookup per id_order."""
        country = Country(name="Italia", iso_code="IT")
        db_session.add(country)
        db_session.commit()

        address = Address(
            id_country=country.id_country,
            firstname="Luigi",
            lastname="Verdi",
            city="Roma",
            postcode="00100",
            date_add=date.today(),
        )
        db_session.add(address)
        db_session.commit()

        carrier_api = CarrierApi(
            name="BRT ROMA",
            carrier_type=CarrierTypeEnum.BRT,
            is_active=True,
        )
        db_session.add(carrier_api)
        db_session.commit()

        shipping = Shipping(
            id_carrier_api=carrier_api.id_carrier_api,
            weight=2.0,
            tracking="",
        )
        db_session.add(shipping)
        db_session.commit()

        order = Order(
            id_origin=0,
            id_order_state=2,
            is_payed=True,
            id_address_delivery=address.id_address,
            id_shipping=shipping.id_shipping,
            total_price_with_tax=80.0,
            products_total_price_with_tax=80.0,
            products_total_price_net=65.0,
            total_price_net=65.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        scanned_code = order.id_order
        response = fastldv_client.get(
            f"/api/v1/fastldv/order/{scanned_code}",
            headers=_headers(),
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["data"]["id_order"] == scanned_code
        assert body["data"]["id_origin"] == 0
        assert body["data"]["document"]["num_doc"] == str(scanned_code)
        assert body["data"]["legacy"]["id_doc"] == scanned_code

    def test_reprint_warning_200(self, fastldv_client, printable_order, db_session):
        shipping = printable_order["shipping"]
        shipping.tracking = "EXISTING-TRACK"
        db_session.commit()

        response = fastldv_client.get(
            "/api/v1/fastldv/order/69099",
            headers=_headers(),
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["data"]["validation"]["code"] == "LABEL_ALREADY_PRINTED"
        assert body["data"]["validation"]["severity"] == "warning"
        assert body["data"]["validation"]["printable"] is True
