"""
OrderPayment Service — pagamenti multipli per ordine (senza rate).
"""
from datetime import date, datetime
from typing import Any, Dict

from src.core.exceptions import NotFoundException
from src.models.order import Order
from src.models.order_payment import OrderPayment
from src.models.payment import Payment
from src.repository.interfaces.order_payment_repository_interface import IOrderPaymentRepository
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.payment_repository_interface import IPaymentRepository
from src.schemas.order_payment_schema import (
    OrderPaymentCreateSchema,
    OrderPaymentPaidStatusSchema,
    OrderPaymentUpdateSchema,
)
from src.services.interfaces.order_payment_service_interface import IOrderPaymentService
from src.services.orders.payment_status import (
    compute_payment_summary,
    sync_order_payment_status,
)


class OrderPaymentService(IOrderPaymentService):
    """Gestione CRUD pagamenti collegati a un ordine."""

    def __init__(
        self,
        order_payment_repository: IOrderPaymentRepository,
        order_repository: IOrderRepository,
        payment_repository: IPaymentRepository,
    ):
        self._order_payment_repository = order_payment_repository
        self._order_repository = order_repository
        self._payment_repository = payment_repository

    def _get_order_or_raise(self, order_id: int) -> Order:
        order = self._order_repository.get_by_id(_id=order_id)
        if not order:
            raise NotFoundException("Order", order_id)
        return order

    def _get_payment_method_or_raise(self, id_payment: int) -> Payment:
        payment = self._payment_repository.get_by_id(id_payment)
        if not payment:
            raise NotFoundException("Payment", id_payment)
        return payment

    def _get_order_payment_or_raise(self, order_id: int, id_order_payment: int) -> OrderPayment:
        entity = self._order_payment_repository.get_by_id_and_order(id_order_payment, order_id)
        if not entity:
            raise NotFoundException("OrderPayment", id_order_payment)
        return entity

    def format_order_payment(self, payment: OrderPayment) -> Dict[str, Any]:
        method = None
        if getattr(payment, "payment", None) is not None:
            method = {
                "id_payment": payment.payment.id_payment,
                "name": payment.payment.name,
            }
        elif payment.id_payment:
            pm = self._payment_repository.get_by_id(payment.id_payment)
            if pm:
                method = {"id_payment": pm.id_payment, "name": pm.name}

        return {
            "id_order_payment": payment.id_order_payment,
            "id_order": payment.id_order,
            "id_payment": payment.id_payment,
            "amount": float(payment.amount) if payment.amount is not None else 0.0,
            "is_paid": bool(payment.is_paid),
            "payment_date": payment.payment_date,
            "note": payment.note,
            "date_add": payment.date_add,
            "payment": method,
        }

    async def list_order_payments(self, order_id: int) -> Dict[str, Any]:
        order = self._get_order_or_raise(order_id)
        payments = self._order_payment_repository.get_by_order_id(order_id)
        summary = compute_payment_summary(order, payments)
        return {
            "order_payments": [self.format_order_payment(p) for p in payments],
            "payment_summary": summary,
            "total": len(payments),
        }

    async def create_order_payment(
        self, order_id: int, data: OrderPaymentCreateSchema
    ) -> OrderPayment:
        self._get_order_or_raise(order_id)
        self._get_payment_method_or_raise(data.id_payment)

        payment_date = data.payment_date
        if data.is_paid and payment_date is None:
            payment_date = date.today()
        if not data.is_paid:
            payment_date = None

        entity = OrderPayment(
            id_order=order_id,
            id_payment=data.id_payment,
            amount=data.amount,
            is_paid=data.is_paid,
            payment_date=payment_date,
            note=data.note,
            date_add=datetime.now(),
        )
        entity = self._order_payment_repository.create(entity)

        session = self._order_payment_repository._session
        sync_order_payment_status(
            session,
            order_id,
            force_unpaid=not data.is_paid,
            commit=True,
        )
        return entity

    async def update_order_payment(
        self, order_id: int, id_order_payment: int, data: OrderPaymentUpdateSchema
    ) -> OrderPayment:
        self._get_order_or_raise(order_id)
        entity = self._get_order_payment_or_raise(order_id, id_order_payment)

        updates = data.model_dump(exclude_unset=True)
        if "id_payment" in updates and updates["id_payment"] is not None:
            self._get_payment_method_or_raise(updates["id_payment"])
            entity.id_payment = updates["id_payment"]
        if "amount" in updates and updates["amount"] is not None:
            entity.amount = updates["amount"]
        if "note" in updates:
            entity.note = updates["note"]

        entity = self._order_payment_repository.update(entity)

        session = self._order_payment_repository._session
        sync_order_payment_status(session, order_id, commit=True)
        return entity

    async def update_paid_status(
        self, order_id: int, id_order_payment: int, data: OrderPaymentPaidStatusSchema
    ) -> OrderPayment:
        self._get_order_or_raise(order_id)
        entity = self._get_order_payment_or_raise(order_id, id_order_payment)

        entity.is_paid = data.is_paid
        if data.is_paid:
            entity.payment_date = data.payment_date or date.today()
        else:
            entity.payment_date = None

        entity = self._order_payment_repository.update(entity)

        session = self._order_payment_repository._session
        sync_order_payment_status(
            session,
            order_id,
            force_unpaid=not data.is_paid,
            commit=True,
        )
        return entity

    async def delete_order_payment(self, order_id: int, id_order_payment: int) -> bool:
        self._get_order_or_raise(order_id)
        entity = self._get_order_payment_or_raise(order_id, id_order_payment)
        deleted = self._order_payment_repository.delete(entity.id_order_payment)

        session = self._order_payment_repository._session
        sync_order_payment_status(session, order_id, commit=True)
        return deleted

    async def validate_business_rules(self, data: Any) -> None:
        pass
