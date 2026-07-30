"""
Interfaccia per OrderPayment Service
"""
from abc import abstractmethod
from typing import Any, Dict, List

from src.core.interfaces import IBaseService
from src.models.order_payment import OrderPayment
from src.schemas.order_payment_schema import (
    OrderPaymentCreateSchema,
    OrderPaymentPaidStatusSchema,
    OrderPaymentUpdateSchema,
)


class IOrderPaymentService(IBaseService):
    """Interface per il servizio pagamenti ordine."""

    @abstractmethod
    async def list_order_payments(self, order_id: int) -> Dict[str, Any]:
        """Lista pagamenti + summary per ordine."""
        pass

    @abstractmethod
    async def create_order_payment(
        self, order_id: int, data: OrderPaymentCreateSchema
    ) -> OrderPayment:
        """Crea un nuovo pagamento sull'ordine."""
        pass

    @abstractmethod
    async def update_order_payment(
        self, order_id: int, id_order_payment: int, data: OrderPaymentUpdateSchema
    ) -> OrderPayment:
        """Aggiorna importo/metodo/nota di un pagamento."""
        pass

    @abstractmethod
    async def update_paid_status(
        self, order_id: int, id_order_payment: int, data: OrderPaymentPaidStatusSchema
    ) -> OrderPayment:
        """Segna un pagamento come pagato/non pagato."""
        pass

    @abstractmethod
    async def delete_order_payment(self, order_id: int, id_order_payment: int) -> bool:
        """Elimina un pagamento dall'ordine."""
        pass

    @abstractmethod
    def format_order_payment(self, payment: OrderPayment) -> Dict[str, Any]:
        """Formatta un OrderPayment per la response API."""
        pass
