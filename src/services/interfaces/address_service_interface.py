"""
Interfaccia per Address Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.address_schema import AddressSchema, AddressResponseSchema
from src.models.address import Address

class IAddressService(IBaseService):
    """Interface per il servizio address"""
    
    @abstractmethod
    async def create_address(self, address_data: AddressSchema) -> Address:
        """Crea un nuovo address"""
        pass
    
    @abstractmethod
    async def update_address(self, address_id: int, address_data: AddressSchema) -> Address:
        """Aggiorna un address esistente"""
        pass
    
    @abstractmethod
    async def get_address(self, address_id: int) -> Address:
        """Ottiene un address per ID"""
        pass
    
    @abstractmethod
    async def get_addresses(self, page: int = 1, limit: int = 10, **filters) -> List[Address]:
        """Ottiene la lista dei address con filtri"""
        pass
    
    @abstractmethod
    async def delete_address(self, address_id: int) -> bool:
        """Elimina un address"""
        pass
    
    @abstractmethod
    async def get_addresses_count(self, **filters) -> int:
        """Ottiene il numero totale di address con filtri"""
        pass
