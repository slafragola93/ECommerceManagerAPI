"""
Interfaccia per Shipping Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.core.interfaces import IBaseService
from src.schemas.shipping_schema import ShippingSchema, ShippingResponseSchema
from src.models.shipping import Shipping

class IShippingService(IBaseService):
    """Interface per il servizio shipping"""
    
    @abstractmethod
    async def create_shipping(self, shipping_data: ShippingSchema) -> Shipping:
        """Crea un nuovo shipping"""
        pass
    
    @abstractmethod
    async def update_shipping(self, shipping_id: int, shipping_data: ShippingSchema) -> Dict[str, Any]:
        """Aggiorna un shipping esistente. Restituisce dict con shipping e dati evento se stato cambia."""
        pass
    
    @abstractmethod
    async def get_shipping(self, shipping_id: int) -> Shipping:
        """Ottiene un shipping per ID"""
        pass
    
    @abstractmethod
    async def get_shippings(self, page: int = 1, limit: int = 10, **filters) -> List[Shipping]:
        """Ottiene la lista dei shipping con filtri"""
        pass
    
    @abstractmethod
    async def delete_shipping(self, shipping_id: int) -> bool:
        """Elimina un shipping"""
        pass
    
    @abstractmethod
    async def get_shippings_count(self, **filters) -> int:
        """Ottiene il numero totale di shipping con filtri"""
        pass
