"""
Interfaccia per Tax Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.tax_schema import TaxSchema, TaxResponseSchema
from src.models.tax import Tax

class ITaxService(IBaseService):
    """Interface per il servizio tax"""
    
    @abstractmethod
    async def create_tax(self, tax_data: TaxSchema) -> Tax:
        """Crea un nuovo tax"""
        pass
    
    @abstractmethod
    async def update_tax(self, tax_id: int, tax_data: TaxSchema) -> Tax:
        """Aggiorna un tax esistente"""
        pass
    
    @abstractmethod
    async def get_tax(self, tax_id: int) -> Tax:
        """Ottiene un tax per ID"""
        pass
    
    @abstractmethod
    async def get_taxes(self, page: int = 1, limit: int = 10, **filters) -> List[Tax]:
        """Ottiene la lista dei tax con filtri"""
        pass
    
    @abstractmethod
    async def delete_tax(self, tax_id: int) -> bool:
        """Elimina un tax"""
        pass
    
    @abstractmethod
    async def get_taxes_count(self, **filters) -> int:
        """Ottiene il numero totale di tax con filtri"""
        pass
