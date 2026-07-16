"""Embed payment/shipping ordine per response ricevuta (subset GET order)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.models.carrier_api import CarrierApi
from src.models.payment import Payment
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.schemas.ricevuta_schema import (
    RicevutaCarrierApiEmbedSchema,
    RicevutaPaymentEmbedSchema,
    RicevutaShippingEmbedSchema,
    RicevutaTaxEmbedSchema,
)


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def map_ricevuta_payment_embed(
    session: Session, id_payment: Optional[int]
) -> Optional[RicevutaPaymentEmbedSchema]:
    if not id_payment:
        return None
    payment = (
        session.query(Payment).filter(Payment.id_payment == id_payment).first()
    )
    if not payment:
        return None
    return RicevutaPaymentEmbedSchema(
        id_payment=payment.id_payment,
        name=payment.name,
    )


def map_ricevuta_shipping_embed(
    session: Session, shipping: Optional[Shipping]
) -> Optional[RicevutaShippingEmbedSchema]:
    """Shipping ordine per ricevuta — senza shipping_state e tracking."""
    if not shipping:
        return None

    carrier_api = None
    if shipping.id_carrier_api:
        carrier = (
            session.query(CarrierApi)
            .filter(CarrierApi.id_carrier_api == shipping.id_carrier_api)
            .first()
        )
        if carrier:
            carrier_api = RicevutaCarrierApiEmbedSchema(
                id_carrier_api=carrier.id_carrier_api,
                name=carrier.name,
            )

    tax = None
    if shipping.id_tax:
        tax_row = session.query(Tax).filter(Tax.id_tax == shipping.id_tax).first()
        if tax_row:
            tax = RicevutaTaxEmbedSchema(
                id_tax=tax_row.id_tax,
                code=tax_row.code,
                percentage=_to_float(tax_row.percentage),
                name=tax_row.name,
            )

    return RicevutaShippingEmbedSchema(
        id_shipping=shipping.id_shipping,
        carrier_api=carrier_api,
        tax=tax,
        weight=_to_float(shipping.weight),
        shipping_message=shipping.shipping_message,
    )
