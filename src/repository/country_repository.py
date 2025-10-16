"""
Country Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.country import Country
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils

class CountryRepository(BaseRepository[Country, int], ICountryRepository):
    """Country Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Country)
    
    def get_all(self, **filters) -> List[Country]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Country.id_country))
            
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
    
    def get_by_name(self, name: str) -> Optional[Country]:
        """Ottiene un country per nome (case insensitive)"""
        try:
            return self._session.query(Country).filter(
                func.lower(Country.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving country by name: {str(e)}")
