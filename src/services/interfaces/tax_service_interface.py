"""
Interfaccia per Tax Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List, Optional
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

    @abstractmethod
    async def get_default_by_country(self, id_country: int) -> Optional[TaxResponseSchema]:
        """Default IVA per id_country."""
        pass

    @abstractmethod
    async def get_default_by_country_iso(self, iso_code: str) -> Optional[TaxResponseSchema]:
        """Default IVA per codice ISO paese."""
        pass

    @abstractmethod
    async def list_country_defaults(self) -> List[TaxResponseSchema]:
        """Lista di tutti i Tax default per paese."""
        pass

    @abstractmethod
    async def set_country_default(self, id_tax: int) -> Tax:
        """Imposta il Tax come unico default per il suo id_country."""
        pass
