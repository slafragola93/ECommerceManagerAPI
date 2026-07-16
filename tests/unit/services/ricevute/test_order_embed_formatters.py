"""Test embed payment/shipping per ricevuta."""
from decimal import Decimal

from src.models.carrier_api import CarrierApi, CarrierTypeEnum
from src.models.payment import Payment
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.services.ricevute.order_embed_formatters import (
    map_ricevuta_payment_embed,
    map_ricevuta_shipping_embed,
)


def test_map_payment_embed(db_session):
    payment = Payment(name="Bonifico bancario", is_complete_payment=True)
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    result = map_ricevuta_payment_embed(db_session, payment.id_payment)

    assert result is not None
    assert result.id_payment == payment.id_payment
    assert result.name == "Bonifico bancario"
    assert not hasattr(result, "is_complete_payment")


def test_map_shipping_embed_excludes_state_and_tracking(db_session):
    tax = Tax(name="Aliquota Italia", percentage=Decimal("22.00"), code="22")
    carrier = CarrierApi(name="BRT", carrier_type=CarrierTypeEnum.BRT)
    db_session.add_all([tax, carrier])
    db_session.commit()
    db_session.refresh(tax)
    db_session.refresh(carrier)

    shipping = Shipping(
        id_carrier_api=carrier.id_carrier_api,
        id_tax=tax.id_tax,
        id_shipping_state=1,
        tracking="TRACK-123",
        weight=Decimal("26.45000"),
        price_tax_incl=Decimal("20.00000"),
        price_tax_excl=Decimal("16.39000"),
    )
    db_session.add(shipping)
    db_session.commit()
    db_session.refresh(shipping)

    result = map_ricevuta_shipping_embed(db_session, shipping)
    payload = result.model_dump()

    assert result is not None
    assert result.id_shipping == shipping.id_shipping
    assert result.carrier_api.name == "BRT"
    assert result.tax.percentage == 22.0
    assert "shipping_state" not in payload
    assert "tracking" not in payload
    assert "price_tax_incl" not in payload
    assert "price_tax_excl" not in payload
