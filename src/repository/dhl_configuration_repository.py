from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.base_repository import BaseRepository
from src.models.dhl_configuration import DhlConfiguration
from src.repository.interfaces.dhl_configuration_repository_interface import IDhlConfigurationRepository


class DhlConfigurationRepository(BaseRepository[DhlConfiguration, int], IDhlConfigurationRepository):
    """Repository for DhlConfiguration operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, DhlConfiguration)
    
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[DhlConfiguration]:
        """Retrieve DHL configuration by carrier_api_id"""
        stmt = select(DhlConfiguration).where(DhlConfiguration.id_carrier_api == id_carrier_api)
        return self._session.execute(stmt).scalar_one_or_none()