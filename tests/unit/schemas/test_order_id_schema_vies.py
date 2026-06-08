"""Unit test — vies_status esposto in GET /orders/{id} (OrderIdSchema)."""
from src.models.order import Order, ViesStatus
from src.repository.order_repository import OrderRepository
from src.schemas.order_schema import OrderIdSchema


def test_order_id_schema_declares_vies_status_field():
    assert "vies_status" in OrderIdSchema.model_fields
    field = OrderIdSchema.model_fields["vies_status"]
    assert field.annotation is not None


def test_formatted_output_vies_status_roundtrip(db_session):
    order = Order(
        id_order_state=1,
        is_invoice_requested=True,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        total_price_with_tax=100.0,
        products_total_price_net=80.0,
        products_total_price_with_tax=100.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    payload = OrderRepository(db_session).formatted_output(order, show_details=False)
    assert payload["vies_status"] == "not_eligible"

    validated = OrderIdSchema.model_validate(payload)
    assert validated.vies_status == ViesStatus.NOT_ELIGIBLE
