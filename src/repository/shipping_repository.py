from datetime import date
from sqlalchemy.orm import Session
from ..models import Shipping
from src.schemas.shipping_schema import *


class ShippingRepository:
    """
    Repository clienti
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_by_id(self, _id: int) -> ShippingResponseSchema:
        return self.session.query(Shipping).filter(Shipping.id_shipping == _id).first()

    def create(self, data: ShippingSchema):
        shipping = Shipping(**data.model_dump())
        shipping.date_add = date.today()

        self.session.add(shipping)
        self.session.commit()

    def create_and_get_id(self, data: ShippingSchema):
        shipping = Shipping(**data.model_dump())
        shipping.date_add = date.today()

        self.session.add(shipping)
        self.session.commit()
        self.session.refresh(shipping)

        return shipping.id_shipping

    def update(self, edited_shipping: Shipping, data: ShippingSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_shipping, key) and value is not None:
                setattr(edited_shipping, key, value)

        self.session.add(edited_shipping)
        self.session.commit()

    def delete(self, shipping: Shipping) -> bool:
        self.session.delete(shipping)
        self.session.commit()

        return True
