"""Unit tests — OrderRepository.get_by_fastldv_code."""
import pytest

from src.models.order import Order
from src.repository.order_repository import OrderRepository


@pytest.mark.unit
class TestOrderRepositoryFastLdvCode:
    def test_resolve_by_id_origin_prestashop(self, db_session):
        order = Order(
            id_origin=457300,
            id_order_state=2,
            is_payed=True,
            total_price_with_tax=10.0,
            products_total_price_with_tax=10.0,
            products_total_price_net=8.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        repo = OrderRepository(db_session)
        found = repo.get_by_fastldv_code(457300)
        assert found is not None
        assert found.id_order == order.id_order
        assert found.id_origin == 457300

    def test_resolve_by_id_order_when_origin_zero(self, db_session):
        order = Order(
            id_origin=0,
            id_order_state=2,
            is_payed=True,
            total_price_with_tax=10.0,
            products_total_price_with_tax=10.0,
            products_total_price_net=8.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        repo = OrderRepository(db_session)
        assert repo.get_by_fastldv_code(457300) is None
        found = repo.get_by_fastldv_code(order.id_order)
        assert found is not None
        assert found.id_origin == 0
        assert found.id_order == order.id_order

    def test_prestashop_wins_over_internal_same_number(self, db_session):
        ps_order = Order(
            id_origin=69099,
            id_order_state=2,
            is_payed=True,
            total_price_with_tax=10.0,
            products_total_price_with_tax=10.0,
            products_total_price_net=8.0,
        )
        internal_order = Order(
            id_origin=0,
            id_order_state=2,
            is_payed=True,
            total_price_with_tax=20.0,
            products_total_price_with_tax=20.0,
            products_total_price_net=16.0,
        )
        db_session.add_all([ps_order, internal_order])
        db_session.commit()
        db_session.refresh(ps_order)

        repo = OrderRepository(db_session)
        found = repo.get_by_fastldv_code(69099)
        assert found.id_order == ps_order.id_order
        assert found.id_origin == 69099
