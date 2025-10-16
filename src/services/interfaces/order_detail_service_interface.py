"""
Interfaccia per Order Detail Service seguendo ISP
"""
from abc import abstractmethod
from typing import List
from src.schemas.order_detail_schema import OrderDetailSchema
from src.models.order_detail import OrderDetail
from src.core.interfaces import IBaseService

class IOrderDetailService(IBaseService):
    """Interface per il servizio order detail"""
    
    @abstractmethod
    async def create_order_detail(self, order_detail_data: OrderDetailSchema) -> OrderDetail:
        pass
    
    @abstractmethod
    async def update_order_detail(self, order_detail_id: int, order_detail_data: OrderDetailSchema) -> OrderDetail:
        pass
    
    @abstractmethod
    async def get_order_detail(self, order_detail_id: int) -> OrderDetail:
        pass
    
    @abstractmethod
    async def get_order_details(self, page: int = 1, limit: int = 10, **filters) -> List[OrderDetail]:
        pass
    
    @abstractmethod
    async def delete_order_detail(self, order_detail_id: int) -> bool:
        pass
    
    @abstractmethod
    async def get_order_details_count(self, **filters) -> int:
        pass
    
    @abstractmethod
    async def get_order_details_by_order_id(self, order_id: int) -> List[OrderDetail]:
        pass
    
    @abstractmethod
    async def get_order_details_by_order_document_id(self, order_document_id: int) -> List[OrderDetail]:
        pass
