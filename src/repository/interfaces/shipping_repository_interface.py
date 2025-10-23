"""
Interfaccia per Shipping Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List, Union
from sqlalchemy.engine import Row
from src.core.interfaces import IRepository
from src.models.shipping import Shipping
from src.schemas.shipping_schema import ShippingSchema

class IShippingRepository(IRepository[Shipping, int]):
    """Interface per la repository dei shipping"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Shipping]:
        """Ottiene un shipping per nome"""
        pass
    
    @abstractmethod
    def create_and_get_id(self, data: Union[ShippingSchema, dict]) -> int:
        """Crea un shipping e restituisce l'ID"""
        pass
    
    @abstractmethod
    def get_carrier_info(self, id_shipping: int) -> Row:
        """Get id_carrier_api from shipping"""
        pass
    
    @abstractmethod  
    def update_tracking(self, id_shipping: int, tracking_number: str) -> None:
        """Update tracking_number field"""
        pass
