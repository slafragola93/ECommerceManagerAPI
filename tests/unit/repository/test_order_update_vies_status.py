"""Verifica persistenza vies_status su PUT ordine (OrderRepository.update)."""
from src.models.order import Order, ViesStatus
from src.repository.order_repository import OrderRepository
from src.schemas.order_schema import OrderUpdateSchema


def test_order_update_persists_vies_status(db_session):
    order = Order(
        id_order_state=1,
        is_invoice_requested=False,
        total_price_with_tax=100.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    assert order.vies_status is None

    repo = OrderRepository(db_session)
    updated = repo.update(
        order,
        OrderUpdateSchema(vies_status=ViesStatus.ELIGIBLE),
    )
    assert updated.vies_status == ViesStatus.ELIGIBLE

    db_session.expire_all()
    reloaded = db_session.get(Order, order.id_order)
    assert reloaded.vies_status == ViesStatus.ELIGIBLE

    formatted = repo.formatted_output(reloaded, show_details=False)
    assert formatted["vies_status"] == "eligible"


def test_order_update_can_clear_vies_status(db_session):
    order = Order(
        id_order_state=1,
        is_invoice_requested=False,
        total_price_with_tax=50.0,
        vies_status=ViesStatus.ELIGIBLE,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    repo = OrderRepository(db_session)
    # Explicit null must clear the field (regression for `value is None: continue`)
    updated = repo.update(
        order,
        OrderUpdateSchema.model_validate({"vies_status": None}),
    )
    assert updated.vies_status is None

    db_session.expire_all()
    reloaded = db_session.get(Order, order.id_order)
    assert reloaded.vies_status is None
