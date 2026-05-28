"""Unit test — filtro vies_status su OrderRepository."""
import pytest
from fastapi import HTTPException

from src.models.order import Order, ViesStatus
from src.repository.order_repository import OrderRepository


@pytest.fixture
def order_repo(db_session):
    return OrderRepository(db_session)


def _add_order(db_session, vies):
    order = Order(id_order_state=1, is_invoice_requested=False, vies_status=vies)
    db_session.add(order)
    db_session.commit()
    return order


class TestOrderRepositoryViesFilter:
    def test_filter_eligible(self, order_repo, db_session):
        eligible = _add_order(db_session, ViesStatus.ELIGIBLE)
        _add_order(db_session, ViesStatus.NOT_ELIGIBLE)
        _add_order(db_session, None)

        results = order_repo.get_all(vies_status="eligible", limit=100, page=1)
        assert len(results) == 1
        assert results[0].id_order == eligible.id_order

    def test_filter_not_eligible(self, order_repo, db_session):
        _add_order(db_session, ViesStatus.ELIGIBLE)
        not_eligible = _add_order(db_session, ViesStatus.NOT_ELIGIBLE)

        results = order_repo.get_all(vies_status="not_eligible", limit=100, page=1)
        assert len(results) == 1
        assert results[0].id_order == not_eligible.id_order

    def test_filter_null(self, order_repo, db_session):
        _add_order(db_session, ViesStatus.ELIGIBLE)
        null_order = _add_order(db_session, None)

        results = order_repo.get_all(vies_status="null", limit=100, page=1)
        assert len(results) == 1
        assert results[0].id_order == null_order.id_order

    def test_filter_invalid_raises(self, order_repo):
        with pytest.raises(HTTPException) as exc:
            order_repo.get_all(vies_status="unknown", limit=10, page=1)
        assert exc.value.status_code == 400
