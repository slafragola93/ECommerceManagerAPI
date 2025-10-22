from typing import Optional
from sqlalchemy.orm import Session
from src.models.dhl_configuration import DhlConfiguration
from src.repository.interfaces.dhl_configuration_repository_interface import IDhlConfigurationRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException


class DhlConfigurationRepository(BaseRepository[DhlConfiguration, int], IDhlConfigurationRepository):
    def __init__(self, session: Session):
        super().__init__(session, DhlConfiguration)
    
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[DhlConfiguration]:
        try:
            return self._session.query(DhlConfiguration).filter(
                DhlConfiguration.id_carrier_api == id_carrier_api
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Error retrieving DHL configuration: {str(e)}")
    
    def get_all(self, **filters):
        query = self._session.query(DhlConfiguration)
        page = filters.get('page', 1)
        limit = filters.get('limit', 100)
        offset = self.get_offset(limit, page)
        return query.offset(offset).limit(limit).all()
    
    def get_count(self, **filters):
        return self._session.query(DhlConfiguration).count()
