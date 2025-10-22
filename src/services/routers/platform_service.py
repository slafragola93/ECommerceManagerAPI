"""
Platform Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.platform_service_interface import IPlatformService
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.platform_schema import PlatformSchema
from src.models.platform import Platform
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class PlatformService(IPlatformService):
    """Platform Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, platform_repository: IPlatformRepository):
        self._platform_repository = platform_repository
    
    async def create_platform(self, platform_data: PlatformSchema) -> Platform:
        """Crea un nuovo platform con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(platform_data, 'name') and platform_data.name:
            existing_platform = self._platform_repository.get_by_name(platform_data.name)
            if existing_platform:
                raise BusinessRuleException(
                    f"Platform with name '{platform_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": platform_data.name}
                )
        
        # Crea il platform
        try:
            platform = Platform(**platform_data.model_dump())
            platform = self._platform_repository.create(platform)
            return platform
        except Exception as e:
            raise ValidationException(f"Error creating platform: {str(e)}")
    
    async def update_platform(self, platform_id: int, platform_data: PlatformSchema) -> Platform:
        """Aggiorna un platform esistente"""
        
        # Verifica esistenza
        platform = self._platform_repository.get_by_id_or_raise(platform_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(platform_data, 'name') and platform_data.name != platform.name:
            existing = self._platform_repository.get_by_name(platform_data.name)
            if existing and existing.id_platform != platform_id:
                raise BusinessRuleException(
                    f"Platform with name '{platform_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": platform_data.name}
                )
        
        # Aggiorna il platform
        try:
            # Aggiorna i campi
            for field_name, value in platform_data.model_dump(exclude_unset=True).items():
                if hasattr(platform, field_name) and value is not None:
                    setattr(platform, field_name, value)
            
            updated_platform = self._platform_repository.update(platform)
            return updated_platform
        except Exception as e:
            raise ValidationException(f"Error updating platform: {str(e)}")
    
    async def get_platform(self, platform_id: int) -> Platform:
        """Ottiene un platform per ID"""
        platform = self._platform_repository.get_by_id_or_raise(platform_id)
        return platform
    
    async def get_platforms(self, page: int = 1, limit: int = 10, **filters) -> List[Platform]:
        """Ottiene la lista dei platform con filtri"""
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
            platforms = self._platform_repository.get_all(**filters)
            
            return platforms
        except Exception as e:
            raise ValidationException(f"Error retrieving platforms: {str(e)}")
    
    async def delete_platform(self, platform_id: int) -> bool:
        """Elimina un platform"""
        # Verifica esistenza
        self._platform_repository.get_by_id_or_raise(platform_id)
        
        try:
            return self._platform_repository.delete(platform_id)
        except Exception as e:
            raise ValidationException(f"Error deleting platform: {str(e)}")
    
    async def get_platforms_count(self, **filters) -> int:
        """Ottiene il numero totale di platform con filtri"""
        try:
            # Usa il repository con i filtri
            return self._platform_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting platforms: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Platform"""
        # Validazioni specifiche per Platform se necessarie
        pass
