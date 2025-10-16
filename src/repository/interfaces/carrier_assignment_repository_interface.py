"""
Interfaccia per Carrier Assignment Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.carrier_assignment import CarrierAssignment

class ICarrierAssignmentRepository(IRepository[CarrierAssignment, int]):
    """Interface per la repository delle assegnazioni carrier"""
    
    @abstractmethod
    def get_by_carrier_api_id(self, carrier_api_id: int) -> List[CarrierAssignment]:
        """Ottiene tutte le assegnazioni per un carrier API specifico"""
        pass
    
    @abstractmethod
    def get_by_postal_code(self, postal_code: str) -> List[CarrierAssignment]:
        """Ottiene le assegnazioni per un codice postale specifico"""
        pass
    
    @abstractmethod
    def get_by_weight_range(self, weight: float) -> List[CarrierAssignment]:
        """Ottiene le assegnazioni per un peso specifico"""
        pass
