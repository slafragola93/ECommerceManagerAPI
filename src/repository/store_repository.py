"""
Store Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from src.models.store import Store
from src.repository.interfaces.store_repository_interface import IStoreRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException

class StoreRepository(BaseRepository[Store, int], IStoreRepository):
    """Store Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Store)
    
    def get_all(self, **filters) -> List[Store]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Store.id_store))
            
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
    
    def get_by_name(self, name: str) -> Optional[Store]:
        """Ottiene uno store per nome (case insensitive)"""
        try:
            return self._session.query(Store).filter(
                func.lower(Store.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving store by name: {str(e)}")
    
    def get_default(self) -> Optional[Store]:
        """Ottiene lo store di default (is_default = True)"""
        try:
            return self._session.query(Store).filter(
                Store.is_default == True
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving default store: {str(e)}")
    
    def get_by_platform(self, id_platform: int) -> List[Store]:
        """Ottiene tutti gli store per una piattaforma"""
        try:
            return self._session.query(Store).filter(
                Store.id_platform == id_platform
            ).order_by(desc(Store.id_store)).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving stores by platform: {str(e)}")
    
    def get_by_vat_number(self, vat_number: str) -> Optional[Store]:
        """Ottiene uno store per partita IVA"""
        try:
            return self._session.query(Store).filter(
                Store.vat_number == vat_number
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving store by VAT number: {str(e)}")
    
    def get_active_stores(self) -> List[Store]:
        """Ottiene tutti gli store attivi"""
        try:
            query = self._session.query(Store).filter(
                Store.is_active == True
            ).order_by(desc(Store.id_store))
            
            stores = query.all()
            return stores
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving active stores: {str(e)}")

