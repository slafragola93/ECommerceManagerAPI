"""
Sectional Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.sectional_service_interface import ISectionalService
from src.repository.interfaces.sectional_repository_interface import ISectionalRepository
from src.schemas.sectional_schema import SectionalSchema
from src.models.sectional import Sectional
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class SectionalService(ISectionalService):
    """Sectional Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, sectional_repository: ISectionalRepository):
        self._sectional_repository = sectional_repository
    
    async def create_sectional(self, sectional_data: SectionalSchema) -> Sectional:
        """Crea un nuovo sectional con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(sectional_data, 'name') and sectional_data.name:
            existing_sectional = self._sectional_repository.get_by_name(sectional_data.name)
            if existing_sectional:
                raise BusinessRuleException(
                    f"Sectional with name '{sectional_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": sectional_data.name}
                )
        
        # Crea il sectional
        try:
            sectional = Sectional(**sectional_data.model_dump())
            sectional = self._sectional_repository.create(sectional)
            return sectional
        except Exception as e:
            raise ValidationException(f"Error creating sectional: {str(e)}")
    
    async def update_sectional(self, sectional_id: int, sectional_data: SectionalSchema) -> Sectional:
        """Aggiorna un sectional esistente"""
        
        # Verifica esistenza
        sectional = self._sectional_repository.get_by_id_or_raise(sectional_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(sectional_data, 'name') and sectional_data.name != sectional.name:
            existing = self._sectional_repository.get_by_name(sectional_data.name)
            if existing and existing.id_sectional != sectional_id:
                raise BusinessRuleException(
                    f"Sectional with name '{sectional_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": sectional_data.name}
                )
        
        # Aggiorna il sectional
        try:
            # Aggiorna i campi
            for field_name, value in sectional_data.model_dump(exclude_unset=True).items():
                if hasattr(sectional, field_name) and value is not None:
                    setattr(sectional, field_name, value)
            
            updated_sectional = self._sectional_repository.update(sectional)
            return updated_sectional
        except Exception as e:
            raise ValidationException(f"Error updating sectional: {str(e)}")
    
    async def get_sectional(self, sectional_id: int) -> Sectional:
        """Ottiene un sectional per ID"""
        sectional = self._sectional_repository.get_by_id_or_raise(sectional_id)
        return sectional
    
    async def get_sectionals(self, page: int = 1, limit: int = 10, **filters) -> List[Sectional]:
        """Ottiene la lista dei sectional con filtri"""
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
            sectionals = self._sectional_repository.get_all(**filters)
            
            return sectionals
        except Exception as e:
            raise ValidationException(f"Error retrieving sectionals: {str(e)}")
    
    async def delete_sectional(self, sectional_id: int) -> bool:
        """Elimina un sectional"""
        # Verifica esistenza
        self._sectional_repository.get_by_id_or_raise(sectional_id)
        
        try:
            return self._sectional_repository.delete(sectional_id)
        except Exception as e:
            raise ValidationException(f"Error deleting sectional: {str(e)}")
    
    async def get_sectionals_count(self, **filters) -> int:
        """Ottiene il numero totale di sectional con filtri"""
        try:
            # Usa il repository con i filtri
            return self._sectional_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting sectionals: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Sectional"""
        # Validazioni specifiche per Sectional se necessarie
        pass
