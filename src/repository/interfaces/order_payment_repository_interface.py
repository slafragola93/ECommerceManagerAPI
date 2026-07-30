"""
Interfaccia per OrderPayment Repository
"""
from abc import abstractmethod
from typing import List, Optional

from src.core.interfaces import IRepository
from src.models.order_payment import OrderPayment


class IOrderPaymentRepository(IRepository[OrderPayment, int]):
    """Interface per la repository dei pagamenti ordine."""

    @abstractmethod
    def get_by_order_id(self, id_order: int) -> List[OrderPayment]:
        """Restituisce i pagamenti di un ordine ordinati per id."""
        pass

    @abstractmethod
    def get_by_id_and_order(self, id_order_payment: int, id_order: int) -> Optional[OrderPayment]:
        """Restituisce un pagamento se appartiene all'ordine."""
        pass

    @abstractmethod
    def sum_amounts_by_order(self, id_order: int, only_paid: bool = False) -> float:
        """Somma gli importi dei pagamenti dell'ordine."""
        pass
