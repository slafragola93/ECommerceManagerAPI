from typing import Optional
from sqlalchemy.orm import Session
from src.models.brt_configuration import BrtConfiguration
from src.repository.interfaces.brt_configuration_repository_interface import IBrtConfigurationRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException


class BrtConfigurationRepository(BaseRepository[BrtConfiguration, int], IBrtConfigurationRepository):
    def __init__(self, session: Session):
        super().__init__(session, BrtConfiguration)
    
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[BrtConfiguration]:
        try:
            return self._session.query(BrtConfiguration).filter(
                BrtConfiguration.id_carrier_api == id_carrier_api
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Error retrieving BRT configuration: {str(e)}")
    
    def get_all(self, **filters):
        query = self._session.query(BrtConfiguration)
        page = filters.get('page', 1)
        limit = filters.get('limit', 100)
        offset = self.get_offset(limit, page)
        return query.offset(offset).limit(limit).all()
    
    def get_count(self, **filters):
        return self._session.query(BrtConfiguration).count()
