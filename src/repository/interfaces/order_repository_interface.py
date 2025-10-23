from abc import ABC, abstractmethod
from sqlalchemy.engine import Row


class IOrderRepository(ABC):
    """Interface for Order repository operations"""
    
    @abstractmethod
    def get_shipment_data(self, order_id: int) -> Row:
        """Retrieve only fields needed for shipment creation"""
        pass
