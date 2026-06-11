"""Unit tests — FastLdvOrderService validation rules."""
import pytest

from src.core.settings import get_fastldv_settings
from src.models.order import Order
from src.services.routers.fastldv_order_service import (
    ORDER_STATE_CANCELED,
    ORDER_STATE_READY,
    ORDER_STATE_SHIPPING_CONFIRMED,
    ORDER_STATE_WAITING,
    FastLdvOrderService,
)


class _FakeOrderRepo:
    def get_by_origin_id(self, id_origin, id_store=None):
        return None


class _FakeDetailRepo:
    def get_by_order_id(self, order_id):
        return []


class _FakeShippingRepo:
    def update_tracking(self, id_shipping, tracking):
        pass


class _FakeCarrierRepo:
    def get_by_id(self, id_):
        return None


@pytest.fixture
def service(db_session):
    return FastLdvOrderService(
        session=db_session,
        order_repository=_FakeOrderRepo(),
        order_detail_repository=_FakeDetailRepo(),
        shipping_repository=_FakeShippingRepo(),
        api_carrier_repository=_FakeCarrierRepo(),
    )


@pytest.mark.unit
class TestFastLdvValidation:
    def test_canceled_order(self, service):
        order = Order(id_order=1, id_order_state=ORDER_STATE_CANCELED, is_payed=True)
        result = service._validate_order(order, None, 69099)
        assert result.printable is False
        assert result.code == "ORDER_CANCELED"

    def test_not_paid(self, service):
        order = Order(id_order=1, id_order_state=ORDER_STATE_READY, is_payed=False)
        result = service._validate_order(order, None, 69099)
        assert result.code == "ORDER_NOT_PAID"

    def test_waiting_locked(self, service):
        order = Order(id_order=1, id_order_state=ORDER_STATE_WAITING, is_payed=True)
        result = service._validate_order(order, None, 69099)
        assert result.code == "ORDER_LOCKED"

    def test_not_ready_state_6_blocks_via_locked(self, service):
        order = Order(id_order=1, id_order_state=ORDER_STATE_WAITING, is_payed=True)
        result = service._validate_order(order, None, 69099)
        assert result.printable is False

    def test_already_shipped(self, service):
        order = Order(
            id_order=1,
            id_order_state=ORDER_STATE_SHIPPING_CONFIRMED,
            is_payed=True,
        )
        result = service._validate_order(order, None, 69099)
        assert result.code == "ORDER_ALREADY_SHIPPED"

    def test_bypass_env(self, service, monkeypatch):
        monkeypatch.setenv("FASTLDV_BYPASS_VALIDATE_IDS", "69099")
        get_fastldv_settings.cache_clear()
        order = Order(id_order=1, id_order_state=ORDER_STATE_CANCELED, is_payed=False)
        result = service._validate_order(order, None, 69099)
        assert result.code == "BYPASS"
        assert result.printable is True
        get_fastldv_settings.cache_clear()
