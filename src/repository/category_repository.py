"""
Category Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.category import Category
from src.repository.interfaces.category_repository_interface import ICategoryRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.category_schema import CategorySchema

class CategoryRepository(BaseRepository[Category, int], ICategoryRepository):
    """Category Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Category)
    
    def get_all(self, **filters) -> List[Category]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Category.id_category))
            
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
    
    def get_by_name(self, name: str) -> Optional[Category]:
        """Ottiene un category per nome (case insensitive)"""
        try:
            return self._session.query(Category).filter(
                func.lower(Category.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving category by name: {str(e)}")
    
    def get_by_origin_id(self, origin_id: str) -> Optional[Category]:
        """Ottiene una categoria per origin ID"""
        try:
            return self._session.query(Category).filter(
                Category.id_origin == origin_id
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving category by origin ID: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[CategorySchema], batch_size: int = 1000) -> int:
        """
        Bulk insert categories da CSV import.
        
        Args:
            data_list: Lista CategorySchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero categories inserite
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_categories = self._session.query(Category.id_origin).filter(
                Category.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {c.id_origin for c in existing_categories}
            
            # Filter new categories
            new_categories_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_categories_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_categories_data), batch_size):
                batch = new_categories_data[i:i + batch_size]
                categories = [Category(**c.model_dump()) for c in batch]
                self._session.bulk_save_objects(categories)
                total_inserted += len(categories)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating categories: {str(e)}")