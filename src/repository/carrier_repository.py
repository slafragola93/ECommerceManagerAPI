"""
Carrier Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.carrier import Carrier
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.carrier_schema import CarrierSchema

class CarrierRepository(BaseRepository[Carrier, int], ICarrierRepository):
    """Carrier Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Carrier)
    
    def get_all(self, **filters) -> List[Carrier]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Carrier.id_carrier))
            
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
    
    def get_by_name(self, name: str) -> Optional[Carrier]:
        """Ottiene un carrier per nome (case insensitive)"""
        try:
            return self._session.query(Carrier).filter(
                func.lower(Carrier.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving carrier by name: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[CarrierSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert carriers da CSV import.
        
        Args:
            data_list: Lista CarrierSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero carriers inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_carriers = self._session.query(Carrier.id_origin).filter(
                Carrier.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {c.id_origin for c in existing_carriers}
            
            # Filter new carriers
            new_carriers_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_carriers_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_carriers_data), batch_size):
                batch = new_carriers_data[i:i + batch_size]
                carriers = [Carrier(**c.model_dump()) for c in batch]
                self._session.bulk_save_objects(carriers)
                total_inserted += len(carriers)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating carriers: {str(e)}")
