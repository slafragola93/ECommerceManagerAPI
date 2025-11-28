"""
Carrier Price Repository rifattorizzato seguendo SOLID
"""
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from src.models.carrier_price import CarrierPrice
from src.repository.interfaces.carrier_price_repository_interface import ICarrierPriceRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException

class CarrierPriceRepository(BaseRepository[CarrierPrice, int], ICarrierPriceRepository):
    """Carrier Price Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, CarrierPrice)

