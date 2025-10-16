"""
Carrier Assignment Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_, and_
from src.models.carrier_assignment import CarrierAssignment
from src.repository.interfaces.carrier_assignment_repository_interface import ICarrierAssignmentRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException

class CarrierAssignmentRepository(BaseRepository[CarrierAssignment, int], ICarrierAssignmentRepository):
    """Carrier Assignment Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, CarrierAssignment)
    
    def get_all(self, **filters) -> List[CarrierAssignment]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(CarrierAssignment.id_carrier_assignment))
            
            # Filtri specifici per Carrier Assignment
            if 'carrier_assignments_ids' in filters and filters['carrier_assignments_ids']:
                ids = [int(x.strip()) for x in filters['carrier_assignments_ids'].split(',') if x.strip().isdigit()]
                if ids:
                    query = query.filter(CarrierAssignment.id_carrier_assignment.in_(ids))
            
            if 'carrier_apis_ids' in filters and filters['carrier_apis_ids']:
                api_ids = [int(x.strip()) for x in filters['carrier_apis_ids'].split(',') if x.strip().isdigit()]
                if api_ids:
                    query = query.filter(CarrierAssignment.id_carrier_api.in_(api_ids))
            
            # Carica la relazione con CarrierApi
            query = query.options(joinedload(CarrierAssignment.carrier_api))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_by_id(self, entity_id: int) -> Optional[CarrierAssignment]:
        """Ottiene un'entità per ID con relazione carrier_api"""
        try:
            return self._session.query(CarrierAssignment).options(
                joinedload(CarrierAssignment.carrier_api)
            ).filter(CarrierAssignment.id_carrier_assignment == entity_id).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} by ID: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            
            # Applica gli stessi filtri di get_all
            if 'carrier_assignments_ids' in filters and filters['carrier_assignments_ids']:
                ids = [int(x.strip()) for x in filters['carrier_assignments_ids'].split(',') if x.strip().isdigit()]
                if ids:
                    query = query.filter(CarrierAssignment.id_carrier_assignment.in_(ids))
            
            if 'carrier_apis_ids' in filters and filters['carrier_apis_ids']:
                api_ids = [int(x.strip()) for x in filters['carrier_apis_ids'].split(',') if x.strip().isdigit()]
                if api_ids:
                    query = query.filter(CarrierAssignment.id_carrier_api.in_(api_ids))
            
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_carrier_api_id(self, carrier_api_id: int) -> List[CarrierAssignment]:
        """Ottiene tutte le assegnazioni per un carrier API specifico"""
        try:
            return self._session.query(CarrierAssignment).options(
                joinedload(CarrierAssignment.carrier_api)
            ).filter(CarrierAssignment.id_carrier_api == carrier_api_id).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier assignments by API ID: {str(e)}")
    
    def get_by_postal_code(self, postal_code: str) -> List[CarrierAssignment]:
        """Ottiene le assegnazioni per un codice postale specifico"""
        try:
            return self._session.query(CarrierAssignment).options(
                joinedload(CarrierAssignment.carrier_api)
            ).filter(
                or_(
                    CarrierAssignment.postal_codes.like(f"%{postal_code}%"),
                    CarrierAssignment.postal_codes.is_(None)
                )
            ).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier assignments by postal code: {str(e)}")
    
    def get_by_weight_range(self, weight: float) -> List[CarrierAssignment]:
        """Ottiene le assegnazioni per un peso specifico"""
        try:
            return self._session.query(CarrierAssignment).options(
                joinedload(CarrierAssignment.carrier_api)
            ).filter(
                and_(
                    or_(CarrierAssignment.min_weight.is_(None), CarrierAssignment.min_weight <= weight),
                    or_(CarrierAssignment.max_weight.is_(None), CarrierAssignment.max_weight >= weight)
                )
            ).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier assignments by weight: {str(e)}")