"""
Interfaccia per Payment Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.payment_schema import PaymentSchema, PaymentResponseSchema
from src.models.payment import Payment

class IPaymentService(IBaseService):
    """Interface per il servizio payment"""
    
    @abstractmethod
    async def create_payment(self, payment_data: PaymentSchema) -> Payment:
        """Crea un nuovo payment"""
        pass
    
    @abstractmethod
    async def update_payment(self, payment_id: int, payment_data: PaymentSchema) -> Payment:
        """Aggiorna un payment esistente"""
        pass
    
    @abstractmethod
    async def get_payment(self, payment_id: int) -> Payment:
        """Ottiene un payment per ID"""
        pass
    
    @abstractmethod
    async def get_payments(self, page: int = 1, limit: int = 10, **filters) -> List[Payment]:
        """Ottiene la lista dei payment con filtri"""
        pass
    
    @abstractmethod
    async def delete_payment(self, payment_id: int) -> bool:
        """Elimina un payment"""
        pass
    
    @abstractmethod
    async def get_payments_count(self, **filters) -> int:
        """Ottiene il numero totale di payment con filtri"""
        pass
