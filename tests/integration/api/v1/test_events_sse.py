"""Integration tests — SSE event stream + FastLDV notify-print."""

import asyncio
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.settings import get_fastldv_settings
from src.events.core.event import EventType
from src.models.address import Address
from src.models.carrier_api import CarrierApi, CarrierTypeEnum
from src.models.country import Country
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.services.routers.auth_service import get_current_user
from tests.conftest import EventBusSpy

FASTLDV_TEST_KEY = "test-fastldv-key"


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


@pytest.fixture(autouse=True)
def fastldv_settings(monkeypatch):
    monkeypatch.setenv("FASTLDV_API_KEY", FASTLDV_TEST_KEY)
    get_fastldv_settings.cache_clear()
    yield
    get_fastldv_settings.cache_clear()


def _admin_full_crud_user() -> dict:
    return {
        "username": "admin",
        "id": 1,
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


@pytest.mark.asyncio
async def test_notify_print_emits_order_tracking_updated_event(
    test_app,
    printable_order,
    event_bus_spy: EventBusSpy,
):
    test_app.dependency_overrides[get_current_user] = _admin_full_crud_user

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/fastldv/notify-print",
            json={
                "id_origin": 69099,
                "tracking": "BRT-EMIT-TEST",
            },
            headers={"X-FastLDV-Key": FASTLDV_TEST_KEY},
        )

    assert response.status_code == 200
    events = event_bus_spy.get_events_by_type(EventType.ORDER_TRACKING_UPDATED.value)
    assert len(events) == 1
    assert events[0].data["id_order"] == printable_order["order"].id_order
    assert events[0].data["tracking"] == "BRT-EMIT-TEST"
    assert events[0].data["awb"] == "BRT-EMIT-TEST"
    assert events[0].data["source"] == "fastldv"


@pytest.mark.asyncio
async def test_sse_fanout_receives_event_after_notify_print(
    test_app,
    printable_order,
):
    """End-to-end: notify-print HTTP → EventBus → SseFanoutService queue."""
    from src.events.runtime import get_sse_fanout

    test_app.dependency_overrides[get_current_user] = _admin_full_crud_user
    sse = get_sse_fanout()
    subscriber = await sse.register(user_id=1)

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/fastldv/notify-print",
            json={
                "id_origin": 69099,
                "tracking": "BRT-SSE-QUEUE",
            },
            headers={"X-FastLDV-Key": FASTLDV_TEST_KEY},
        )

    assert response.status_code == 200
    message = await asyncio.wait_for(subscriber.queue.get(), timeout=2.0)
    assert "order.tracking.updated" in message
    assert "BRT-SSE-QUEUE" in message
