"""
Interfaccia per OrderPackage Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.order_package_schema import OrderPackageSchema, OrderPackageResponseSchema
from src.models.order_package import OrderPackage

class IOrderPackageService(IBaseService):
    """Interface per il servizio order_package"""
    
    @abstractmethod
    async def create_order_package(self, order_package_data: OrderPackageSchema) -> OrderPackage:
        """Crea un nuovo order_package"""
        pass
    
    @abstractmethod
    async def update_order_package(self, order_package_id: int, order_package_data: OrderPackageSchema) -> OrderPackage:
        """Aggiorna un order_package esistente"""
        pass
    
    @abstractmethod
    async def get_order_package(self, order_package_id: int) -> OrderPackage:
        """Ottiene un order_package per ID"""
        pass
    
    @abstractmethod
    async def get_order_packages(self, page: int = 1, limit: int = 10, **filters) -> List[OrderPackage]:
        """Ottiene la lista dei order_package con filtri"""
        pass
    
    @abstractmethod
    async def delete_order_package(self, order_package_id: int) -> bool:
        """Elimina un order_package"""
        pass
    
    @abstractmethod
    async def get_order_packages_count(self, **filters) -> int:
        """Ottiene il numero totale di order_package con filtri"""
        pass
