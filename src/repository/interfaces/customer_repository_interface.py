"""
Interfaccia specifica per Customer Repository seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from src.models.customer import Customer
from src.core.interfaces import IRepository

class ICustomerRepository(IRepository[Customer, int], ABC):
    """Interfaccia specifica per Customer Repository"""
    
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Customer]:
        """Ottiene un cliente per email"""
        pass
    
    @abstractmethod
    def get_by_origin_id(self, origin_id: str) -> Optional[Customer]:
        """Ottiene un cliente per origin ID"""
        pass
    
    @abstractmethod
    def search_by_name(self, name: str) -> List[Customer]:
        """Cerca clienti per nome"""
        pass
    
    @abstractmethod
    def get_customers_with_addresses(self, page: int = 1, limit: int = 10) -> List[Customer]:
        """Ottiene clienti con indirizzi"""
        pass
