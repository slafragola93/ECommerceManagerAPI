"""
OrderPayment Repository
"""
from typing import List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.models.order_payment import OrderPayment
from src.repository.interfaces.order_payment_repository_interface import IOrderPaymentRepository


class OrderPaymentRepository(BaseRepository[OrderPayment, int], IOrderPaymentRepository):
    """Repository per i pagamenti collegati a un ordine."""

    def __init__(self, session: Session):
        super().__init__(session, OrderPayment)

    def get_all(self, **filters) -> List[OrderPayment]:
        try:
            query = self._session.query(self._model_class).order_by(
                desc(OrderPayment.id_order_payment)
            )
            id_order = filters.get("id_order")
            if id_order is not None:
                query = query.filter(OrderPayment.id_order == id_order)
            page = filters.get("page", 1)
            limit = filters.get("limit", 100)
            offset = self.get_offset(limit, page)
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving {self._model_class.__name__} list: {str(e)}"
            )

    def get_count(self, **filters) -> int:
        try:
            query = self._session.query(self._model_class)
            id_order = filters.get("id_order")
            if id_order is not None:
                query = query.filter(OrderPayment.id_order == id_order)
            return query.count()
        except Exception as e:
            raise InfrastructureException(
                f"Database error counting {self._model_class.__name__}: {str(e)}"
            )

    def get_by_order_id(self, id_order: int) -> List[OrderPayment]:
        try:
            return (
                self._session.query(OrderPayment)
                .filter(OrderPayment.id_order == id_order)
                .order_by(OrderPayment.id_order_payment.asc())
                .all()
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving order_payments for order {id_order}: {str(e)}"
            )

    def get_by_id_and_order(self, id_order_payment: int, id_order: int) -> Optional[OrderPayment]:
        try:
            return (
                self._session.query(OrderPayment)
                .filter(
                    OrderPayment.id_order_payment == id_order_payment,
                    OrderPayment.id_order == id_order,
                )
                .first()
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving order_payment {id_order_payment}: {str(e)}"
            )

    def sum_amounts_by_order(self, id_order: int, only_paid: bool = False) -> float:
        try:
            query = self._session.query(func.coalesce(func.sum(OrderPayment.amount), 0)).filter(
                OrderPayment.id_order == id_order
            )
            if only_paid:
                query = query.filter(OrderPayment.is_paid.is_(True))
            result = query.scalar()
            return float(result or 0)
        except Exception as e:
            raise InfrastructureException(
                f"Database error summing order_payments for order {id_order}: {str(e)}"
            )
