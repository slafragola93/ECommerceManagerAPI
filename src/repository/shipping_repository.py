"""
Shipping Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List, Union
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc, select, update
from sqlalchemy.engine import Row
from src.models.shipping import Shipping
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.shipping_schema import ShippingSchema

class ShippingRepository(BaseRepository[Shipping, int], IShippingRepository):
    """Shipping Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Shipping)
    
    def get_all(self, **filters) -> List[Shipping]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Shipping.id_shipping))
            
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
    
    def get_by_name(self, name: str) -> Optional[Shipping]:
        """Ottiene un shipping per nome (case insensitive)"""
        try:
            return self._session.query(Shipping).filter(
                func.lower(Shipping.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving shipping by name: {str(e)}")
    
    def create_and_get_id(self, data: Union[ShippingSchema, dict]) -> int:
        """Crea un shipping e restituisce l'ID"""
        try:
            # Converti ShippingSchema in dict se necessario
            if isinstance(data, ShippingSchema):
                shipping_data = data.model_dump()
            else:
                shipping_data = data
            
            # Crea l'istanza del modello
            shipping = Shipping(**shipping_data)
            
            # Salva nel database
            self._session.add(shipping)
            self._session.commit()
            self._session.refresh(shipping)
            
            return shipping.id_shipping
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error creating shipping: {str(e)}")
    
    def get_carrier_info(self, id_shipping: int) -> Row:
        """Get id_carrier_api from shipping"""
        try:
            stmt = select(
                Shipping.id_shipping,
                Shipping.id_carrier_api,
                Shipping.tracking
            ).where(Shipping.id_shipping == id_shipping)
            
            result = self._session.execute(stmt).first()
            if not result:
                raise InfrastructureException(f"Shipping {id_shipping} not found")
            return result
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier info: {str(e)}")
    
    def update_tracking(self, id_shipping: int, tracking: str) -> None:
        """Update tracking field"""
        try:
            stmt = update(Shipping).where(
                Shipping.id_shipping == id_shipping
            ).values(tracking=tracking)
            
            self._session.execute(stmt)
            self._session.commit()
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating tracking number: {str(e)}")
    