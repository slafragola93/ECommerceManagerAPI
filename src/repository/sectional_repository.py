"""
Sectional Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List, Union
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.sectional import Sectional
from src.repository.interfaces.sectional_repository_interface import ISectionalRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.sectional_schema import SectionalSchema

class SectionalRepository(BaseRepository[Sectional, int], ISectionalRepository):
    """Sectional Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Sectional)
    
    def get_all(self, **filters) -> List[Sectional]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Sectional.id_sectional))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Sectional]:
        """Ottiene un sectional per nome (case insensitive)"""
        try:
            return self._session.query(Sectional).filter(
                func.lower(Sectional.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving sectional by name: {str(e)}")
    
    def create_and_get_id(self, data: Union[SectionalSchema, dict]) -> int:
        """
        Crea un sectional e restituisce l'ID.
        Se esiste già uno con lo stesso nome (case insensitive), restituisce l'ID esistente.
        Query idratata: recupera solo id_sectional.
        """
        try:
            # Converti SectionalSchema in dict se necessario
            if isinstance(data, SectionalSchema):
                sectional_data = data.model_dump()
            else:
                sectional_data = data
            
            name = sectional_data.get('name')
            if not name:
                raise ValueError("Sectional name is required")
            
            # Cerca sectional esistente per nome (query idratata - solo id_sectional)
            existing_id = self._session.query(Sectional.id_sectional).filter(
                func.lower(Sectional.name) == func.lower(name)
            ).scalar()
            
            if existing_id:
                return existing_id
            
            # Crea nuovo sectional
            sectional = Sectional(name=name)
            self._session.add(sectional)
            self._session.flush()
            return sectional.id_sectional
        except Exception as e:
            raise InfrastructureException(f"Database error creating sectional: {str(e)}")
