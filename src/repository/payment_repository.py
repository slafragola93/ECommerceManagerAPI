from sqlalchemy import func, asc
from sqlalchemy.orm import Session
from ..models import Payment
from src.services import QueryUtils
from ..schemas.payment_schema import PaymentSchema, AllPaymentsResponseSchema, PaymentResponseSchema


class PaymentRepository:
    """Repository payment"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> AllPaymentsResponseSchema:
        return self.session.query(Payment).order_by(asc(Payment.name)).offset(QueryUtils.get_offset(limit, page)).limit(
            limit).all()

    def list_all(self) -> list[dict]:
        return self.session.query(Payment).order_by(asc(Payment.name)).all()

    def get_count(self) -> int:
        return self.session.query(func.count(Payment.id_payment)).scalar()

    def get_by_id(self, _id: int) -> PaymentResponseSchema:
        """
        Ottieni brand per ID

        Args:
            _id (int):  ID Payment.

        Returns:
            PaymentResponseSchema: Istanza configurazione
        """
        return self.session.query(Payment).filter(Payment.id_payment == _id).first()
    
    def get_by_name(self, name: str) -> Payment:
        """Get payment by name"""
        return self.session.query(Payment).filter(Payment.name == name).first()

    def create(self, data: PaymentSchema):

        payment = Payment(**data.model_dump())

        self.session.add(payment)
        self.session.commit()
        self.session.refresh(payment)

    def update(self,
               edited_payment: Payment,
               data: PaymentSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        # Set su ogni proprietà
        for key, value in entity_updated.items():
            if hasattr(edited_payment, key) and value is not None:
                setattr(edited_payment, key, value)

        self.session.add(edited_payment)
        self.session.commit()

    def delete(self, payment: Payment) -> bool:
        self.session.delete(payment)
        self.session.commit()

        return True
