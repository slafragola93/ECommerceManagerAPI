from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from ..models import OrderState
from src.schemas.order_state_schema import *
from src.services import QueryUtils


class OrderStateRepository:
    """Repository order state"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllOrdersStateResponseSchema:
        return self.session.query(OrderState).order_by(desc(OrderState.id_order_state)).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self):
        return self.session.query(func.count(OrderState.id_order_state)).scalar()

    def get_by_id(self, _id: int) -> OrderStateResponseSchema:
        return self.session.query(OrderState).filter(OrderState.id_order_state == _id).first()

    def create(self, data: OrderStateSchema):

        order_state = OrderState(**data.model_dump())

        self.session.add(order_state)
        self.session.commit()
        self.session.refresh(order_state)

    def update(self,
               edited_order_state: OrderState,
               data: OrderStateSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_order_state, key) and value is not None:
                setattr(edited_order_state, key, value)

        self.session.add(edited_order_state)
        self.session.commit()

    def delete(self, order_state: OrderState) -> bool:
        self.session.delete(order_state)
        self.session.commit()

        return True
