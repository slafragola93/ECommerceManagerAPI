"""
Interfaccia per Country Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.country_schema import CountrySchema, CountryResponseSchema
from src.models.country import Country

class ICountryService(IBaseService):
    """Interface per il servizio country"""
    
    @abstractmethod
    async def create_country(self, country_data: CountrySchema) -> Country:
        """Crea un nuovo country"""
        pass
    
    @abstractmethod
    async def update_country(self, country_id: int, country_data: CountrySchema) -> Country:
        """Aggiorna un country esistente"""
        pass
    
    @abstractmethod
    async def get_country(self, country_id: int) -> Country:
        """Ottiene un country per ID"""
        pass
    
    @abstractmethod
    async def get_countries(self, page: int = 1, limit: int = 10, **filters) -> List[Country]:
        """Ottiene la lista dei country con filtri"""
        pass
    
    @abstractmethod
    async def delete_country(self, country_id: int) -> bool:
        """Elimina un country"""
        pass
    
    @abstractmethod
    async def get_countries_count(self, **filters) -> int:
        """Ottiene il numero totale di country con filtri"""
        pass
