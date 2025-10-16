"""
Address Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.address import Address
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils

class AddressRepository(BaseRepository[Address, int], IAddressRepository):
    """Address Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Address)
    
    def get_by_id(self, id: int) -> Optional[Address]:
        """Ottiene un address per ID con relazioni caricate"""
        try:
            from sqlalchemy.orm import joinedload
            
            id_field = self._get_id_field()
            return self._session.query(self._model_class).filter(
                getattr(self._model_class, id_field) == id
            ).options(
                joinedload(Address.customer),
                joinedload(Address.country)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__}: {str(e)}")
    
    def get_all(self, **filters) -> List[Address]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            from sqlalchemy.orm import joinedload
            
            query = self._session.query(self._model_class).order_by(desc(Address.id_address))
            
            # Carica sempre le relazioni customer e country per lo schema di risposta
            query = query.options(
                joinedload(Address.customer),
                joinedload(Address.country)
            )
            
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
    
    def get_by_name(self, name: str) -> Optional[Address]:
        """Ottiene un address per nome (case insensitive)"""
        try:
            return self._session.query(Address).filter(
                func.lower(Address.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving address by name: {str(e)}")
