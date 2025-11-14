"""
Brand Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.brand import Brand
from src.repository.interfaces.brand_repository_interface import IBrandRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.brand_schema import BrandSchema

class BrandRepository(BaseRepository[Brand, int], IBrandRepository):
    """Brand Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Brand)
    
    def get_all(self, **filters) -> List[Brand]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Brand.id_brand))
            
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
    
    def get_by_name(self, name: str) -> Optional[Brand]:
        """Ottiene un brand per nome (case insensitive)"""
        try:
            return self._session.query(Brand).filter(
                func.lower(Brand.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving brand by name: {str(e)}")
    
    def get_by_origin_id(self, origin_id: str) -> Optional[Brand]:
        """Ottiene un brand per origin ID"""
        try:
            return self._session.query(Brand).filter(
                Brand.id_origin == origin_id
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving brand by origin ID: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[BrandSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert brands da CSV import.
        
        Args:
            data_list: Lista BrandSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero brands inseriti
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_brands = self._session.query(Brand.id_origin).filter(
                Brand.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {b.id_origin for b in existing_brands}
            
            # Filter new brands
            new_brands_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_brands_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_brands_data), batch_size):
                batch = new_brands_data[i:i + batch_size]
                brands = [Brand(**b.model_dump()) for b in batch]
                self._session.bulk_save_objects(brands)
                total_inserted += len(brands)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating brands: {str(e)}")