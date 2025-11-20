from typing import Optional
from sqlalchemy.orm import Session
from src.models.fedex_configuration import FedexConfiguration
from src.repository.interfaces.fedex_configuration_repository_interface import IFedexConfigurationRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException


class FedexConfigurationRepository(BaseRepository[FedexConfiguration, int], IFedexConfigurationRepository):
    def __init__(self, session: Session):
        super().__init__(session, FedexConfiguration)
    
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[FedexConfiguration]:
        try:
            return self._session.query(FedexConfiguration).filter(
                FedexConfiguration.id_carrier_api == id_carrier_api
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Error retrieving FedEx configuration: {str(e)}")
    
    def get_all(self, **filters):
        query = self._session.query(FedexConfiguration)
        page = filters.get('page', 1)
        limit = filters.get('limit', 100)
        offset = self.get_offset(limit, page)
        return query.offset(offset).limit(limit).all()
    
    def get_count(self, **filters):
        return self._session.query(FedexConfiguration).count()
