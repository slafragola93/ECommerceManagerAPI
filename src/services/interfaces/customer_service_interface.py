"""
Interfaccia per Customer Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from src.schemas.customer_schema import CustomerSchema, CustomerResponseSchema
from src.models.customer import Customer

class ICustomerService(ABC):
    """Interfaccia per Customer Service"""
    
    @abstractmethod
    async def create_customer(self, customer_data: CustomerSchema) -> Tuple[Customer, bool]:
        """
        Crea un nuovo cliente o restituisce quello esistente se l'email è già presente.
        
        Returns:
            Tuple[Customer, bool]: (customer, is_created) dove is_created è True se creato, False se esistente
        """
        pass
    
    @abstractmethod
    async def update_customer(self, customer_id: int, customer_data: CustomerSchema) -> Customer:
        """Aggiorna un cliente esistente"""
        pass
    
    @abstractmethod
    async def get_customer(self, customer_id: int) -> Customer:
        """Ottiene un cliente per ID"""
        pass
    
    @abstractmethod
    async def get_customers(self, page: int = 1, limit: int = 10, **filters) -> List[Customer]:
        """Ottiene la lista dei clienti con filtri"""
        pass
    
    @abstractmethod
    async def delete_customer(self, customer_id: int) -> bool:
        """Elimina un cliente"""
        pass
    
    @abstractmethod
    async def search_customers(self, search_term: str) -> List[Customer]:
        """Cerca clienti per termine di ricerca"""
        pass
    
    @abstractmethod
    async def get_customers_count(self, **filters) -> int:
        """Ottiene il numero totale di clienti con filtri"""
        pass
