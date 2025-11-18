"""
Interfaccia per Payment Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.payment import Payment

class IPaymentRepository(IRepository[Payment, int]):
    """Interface per la repository dei payment"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Payment]:
        """Ottiene un payment per nome"""
        pass
    
    @abstractmethod
    def is_complete_payment(self, id_payment: int) -> Optional[bool]:
        """
        Query idratata: recupera solo is_complete_payment per un payment.
        
        Returns:
            True se is_complete_payment=True, False se is_complete_payment=False, None se payment non esiste
        """
        pass