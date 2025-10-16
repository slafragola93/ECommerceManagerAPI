"""
Interfaccia per Carrier Assignment Service seguendo ISP
"""
from abc import abstractmethod
from typing import List, Optional
from src.schemas.carrier_assignment_schema import CarrierAssignmentSchema, CarrierAssignmentUpdateSchema
from src.models.carrier_assignment import CarrierAssignment
from src.core.interfaces import IBaseService

class ICarrierAssignmentService(IBaseService):
    """Interface per il servizio carrier assignment"""
    
    @abstractmethod
    async def create_carrier_assignment(self, assignment_data: CarrierAssignmentSchema) -> CarrierAssignment:
        pass
    
    @abstractmethod
    async def update_carrier_assignment(self, assignment_id: int, assignment_data: CarrierAssignmentUpdateSchema) -> CarrierAssignment:
        pass
    
    @abstractmethod
    async def get_carrier_assignment(self, assignment_id: int) -> CarrierAssignment:
        pass
    
    @abstractmethod
    async def get_carrier_assignments(self, page: int = 1, limit: int = 10, **filters) -> List[CarrierAssignment]:
        pass
    
    @abstractmethod
    async def delete_carrier_assignment(self, assignment_id: int) -> bool:
        pass
    
    @abstractmethod
    async def get_carrier_assignments_count(self, **filters) -> int:
        pass
    
    @abstractmethod
    async def get_assignments_by_carrier_api(self, carrier_api_id: int) -> List[CarrierAssignment]:
        pass
    
    @abstractmethod
    async def find_matching_assignment(self, postal_code: Optional[str] = None, 
                                     country_id: Optional[int] = None,
                                     origin_carrier_id: Optional[int] = None,
                                     weight: Optional[float] = None) -> Optional[CarrierAssignment]:
        pass
