from sqlalchemy import asc
from sqlalchemy.orm import Session
from ..models import ShippingState
from src.schemas.shipping_state_schema import ShippingStateSchema, ShippingStateResponseSchema, AllShippingStatesResponseSchema
from src.services import QueryUtils


class ShippingStateRepository:
    """
    Repository shipping states
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                page: int = 1, limit: int = 10
                ) -> AllShippingStatesResponseSchema:
        """
        Recupera tutti gli stati di spedizione disponibili

        Returns:
            AllShippingStatesResponseSchema: Tutti gli stati di spedizione
        """
        return self.session.query(ShippingState).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_by_id(self, _id: int) -> ShippingStateResponseSchema:
        return self.session.query(ShippingState).filter(ShippingState.id_shipping_state == _id).first()

    def create(self, data: ShippingStateSchema):
        shipping_state = ShippingState(**data.model_dump())

        self.session.add(shipping_state)
        self.session.commit()
        self.session.refresh(shipping_state)

    def update(self, edited_shipping_state: ShippingState, data: ShippingStateSchema):

        entity_updated = data.dict(exclude_unset=True)

        for key, value in entity_updated.items():
            if hasattr(edited_shipping_state, key) and value is not None:
                setattr(edited_shipping_state, key, value)

        self.session.add(edited_shipping_state)
        self.session.commit()

    def delete(self, shipping_state: ShippingState) -> bool:
        self.session.delete(shipping_state)
        self.session.commit()

        return True
