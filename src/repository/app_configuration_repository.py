"""
AppConfiguration Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.app_configuration import AppConfiguration
from src.repository.interfaces.app_configuration_repository_interface import IAppConfigurationRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils

class AppConfigurationRepository(BaseRepository[AppConfiguration, int], IAppConfigurationRepository):
    """AppConfiguration Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, AppConfiguration)
    
    def get_all(self, **filters) -> List[AppConfiguration]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(AppConfiguration.id_app_configuration))
            
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
    
    def get_by_name(self, name: str) -> Optional[AppConfiguration]:
        """Ottiene un app_configuration per nome (case insensitive)"""
        try:
            return self._session.query(AppConfiguration).filter(
                func.lower(AppConfiguration.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving app_configuration by name: {str(e)}")
    
    def get_by_name_and_category(self, name: str, category: str) -> Optional[AppConfiguration]:
        """Ottiene un app_configuration per nome e categoria (case insensitive)"""
        try:
            return self._session.query(AppConfiguration).filter(
                func.lower(AppConfiguration.name) == func.lower(name),
                func.lower(AppConfiguration.category) == func.lower(category)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving app_configuration by name and category: {str(e)}")
    
    def get_by_category(self, category: str) -> List[AppConfiguration]:
        """Ottiene tutte le configurazioni per categoria"""
        try:
            return self._session.query(AppConfiguration).filter(
                func.lower(AppConfiguration.category) == func.lower(category)
            ).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving app_configurations by category: {str(e)}")