"""
Interfaccia per Order Detail Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.order_detail import OrderDetail

class IOrderDetailRepository(IRepository[OrderDetail, int]):
    """Interface per la repository degli order detail"""
    
    @abstractmethod
    def get_by_order_id(self, order_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli ordine per un ordine specifico"""
        pass
    
    @abstractmethod
    def get_by_order_document_id(self, order_document_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli ordine per un documento ordine specifico"""
        pass
    
    @abstractmethod
    def get_by_product_id(self, product_id: int) -> List[OrderDetail]:
        """Ottiene tutti i dettagli ordine per un prodotto specifico"""
        pass
