"""Unit test — vies_status su POST create order (OrderSchema)."""
from src.models.order import Order, ViesStatus
from src.schemas.order_schema import OrderSchema

_CREATE_EXCLUDE = [
    "address_delivery",
    "address_invoice",
    "customer",
    "shipping",
    "sectional",
    "order_details",
    "order_packages",
]


def test_order_schema_accepts_vies_status():
    schema = OrderSchema(
        address_delivery=0,
        address_invoice=0,
        customer=0,
        id_order_state=1,
        is_invoice_requested=False,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        total_price_with_tax=100.0,
    )
    assert schema.vies_status == ViesStatus.NOT_ELIGIBLE


def test_order_schema_vies_status_in_model_dump_for_create():
    schema = OrderSchema(
        address_delivery=0,
        address_invoice=0,
        customer=0,
        id_order_state=1,
        is_invoice_requested=False,
        vies_status="eligible",
        total_price_with_tax=50.0,
    )
    dumped = schema.model_dump(exclude=_CREATE_EXCLUDE)
    assert dumped["vies_status"] == ViesStatus.ELIGIBLE


def test_order_model_receives_vies_status_from_schema_dump():
    schema = OrderSchema(
        address_delivery=0,
        address_invoice=0,
        customer=0,
        id_order_state=1,
        is_invoice_requested=True,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        total_price_with_tax=80.0,
    )
    order = Order(**schema.model_dump(exclude=_CREATE_EXCLUDE))
    assert order.vies_status == ViesStatus.NOT_ELIGIBLE
