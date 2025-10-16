"""
Category Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.category_service_interface import ICategoryService
from src.repository.interfaces.category_repository_interface import ICategoryRepository
from src.schemas.category_schema import CategorySchema
from src.models.category import Category
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class CategoryService(ICategoryService):
    """Category Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, category_repository: ICategoryRepository):
        self._category_repository = category_repository
    
    async def create_category(self, category_data: CategorySchema) -> Category:
        """Crea un nuovo category con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(category_data, 'name') and category_data.name:
            existing_category = self._category_repository.get_by_name(category_data.name)
            if existing_category:
                raise BusinessRuleException(
                    f"Category with name '{category_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": category_data.name}
                )
        
        # Crea il category
        try:
            category = Category(**category_data.dict())
            category = self._category_repository.create(category)
            return category
        except Exception as e:
            raise ValidationException(f"Error creating category: {str(e)}")
    
    async def update_category(self, category_id: int, category_data: CategorySchema) -> Category:
        """Aggiorna un category esistente"""
        
        # Verifica esistenza
        category = self._category_repository.get_by_id_or_raise(category_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(category_data, 'name') and category_data.name != category.name:
            existing = self._category_repository.get_by_name(category_data.name)
            if existing and existing.id_category != category_id:
                raise BusinessRuleException(
                    f"Category with name '{category_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": category_data.name}
                )
        
        # Aggiorna il category
        try:
            # Aggiorna i campi
            for field_name, value in category_data.dict(exclude_unset=True).items():
                if hasattr(category, field_name) and value is not None:
                    setattr(category, field_name, value)
            
            updated_category = self._category_repository.update(category)
            return updated_category
        except Exception as e:
            raise ValidationException(f"Error updating category: {str(e)}")
    
    async def get_category(self, category_id: int) -> Category:
        """Ottiene un category per ID"""
        category = self._category_repository.get_by_id_or_raise(category_id)
        return category
    
    async def get_categories(self, page: int = 1, limit: int = 10, **filters) -> List[Category]:
        """Ottiene la lista dei category con filtri"""
        try:
            # Validazione parametri
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10
            
            # Aggiungi page e limit ai filtri
            filters['page'] = page
            filters['limit'] = limit
            
            # Usa il repository con i filtri
            categories = self._category_repository.get_all(**filters)
            
            return categories
        except Exception as e:
            raise ValidationException(f"Error retrieving categories: {str(e)}")
    
    async def delete_category(self, category_id: int) -> bool:
        """Elimina un category"""
        # Verifica esistenza
        self._category_repository.get_by_id_or_raise(category_id)
        
        try:
            return self._category_repository.delete(category_id)
        except Exception as e:
            raise ValidationException(f"Error deleting category: {str(e)}")
    
    async def get_categories_count(self, **filters) -> int:
        """Ottiene il numero totale di category con filtri"""
        try:
            # Usa il repository con i filtri
            return self._category_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting categories: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Category"""
        # Validazioni specifiche per Category se necessarie
        pass
