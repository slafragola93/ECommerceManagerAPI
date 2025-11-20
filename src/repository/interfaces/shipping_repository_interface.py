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
    def update_tracking(self, id_shipping: int, tracking: str) -> None:
        """Update tracking field"""
        pass

    @abstractmethod
    def update_tracking_and_state(self, id_shipping: int, tracking: str, state_id: int) -> None:
        """Update tracking and id_shipping_state in one shot"""
        pass

    @abstractmethod
    def update_state_by_tracking(self, tracking: str, state_id: int) -> int:
        """Update id_shipping_state by tracking. Returns affected rows count."""
        pass

    @abstractmethod
    def update_weight(self, id_shipping: int, weight: float) -> None:
        """Aggiorna il peso della spedizione"""
        pass

    @abstractmethod
    def update_weight(self, id_shipping: int, weight: float) -> None:
        """Aggiorna il peso della spedizione."""
        pass
    
    @abstractmethod
    def get_message_shipping(self, id_shipping: int) -> Optional[str]:
        """Recupera shipping_message dalla spedizione"""
        pass
    
    @abstractmethod
    def update_shipping_to_cancelled_state(self, id_shipping: int) -> None:
        """Imposta lo stato della shipping a 11 (Annullato)"""
        pass
    