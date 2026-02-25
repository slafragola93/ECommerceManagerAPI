"""
AppConfiguration Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.app_configuration_service_interface import IAppConfigurationService
from src.repository.interfaces.app_configuration_repository_interface import IAppConfigurationRepository
from src.schemas.app_configuration_schema import AppConfigurationSchema
from src.models.app_configuration import AppConfiguration
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class AppConfigurationService(IAppConfigurationService):
    """AppConfiguration Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, app_configuration_repository: IAppConfigurationRepository):
        self._app_configuration_repository = app_configuration_repository
    
    async def create_app_configuration(self, app_configuration_data: AppConfigurationSchema) -> AppConfiguration:
        """Crea un nuovo app_configuration con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(app_configuration_data, 'name') and app_configuration_data.name:
            existing_app_configuration = self._app_configuration_repository.get_by_name(app_configuration_data.name)
            if existing_app_configuration:
                raise BusinessRuleException(
                    f"AppConfiguration with name '{app_configuration_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": app_configuration_data.name}
                )
        
        # Crea il app_configuration
        try:
            app_configuration = AppConfiguration(**app_configuration_data.model_dump())
            app_configuration = self._app_configuration_repository.create(app_configuration)
            return app_configuration
        except Exception as e:
            raise ValidationException(f"Error creating app_configuration: {str(e)}")
    
    async def update_app_configuration(self, app_configuration_id: int, app_configuration_data: AppConfigurationSchema) -> AppConfiguration:
        """Aggiorna un app_configuration esistente"""
        
        # Verifica esistenza
        app_configuration = self._app_configuration_repository.get_by_id_or_raise(app_configuration_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(app_configuration_data, 'name') and app_configuration_data.name != app_configuration.name:
            existing = self._app_configuration_repository.get_by_name(app_configuration_data.name)
            if existing and existing.id_app_configuration != app_configuration_id:
                raise BusinessRuleException(
                    f"AppConfiguration with name '{app_configuration_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": app_configuration_data.name}
                )
        
        # Aggiorna il app_configuration
        try:
            # Aggiorna i campi
            for field_name, value in app_configuration_data.model_dump(exclude_unset=True).items():
                if hasattr(app_configuration, field_name) and value is not None:
                    setattr(app_configuration, field_name, value)
            
            updated_app_configuration = self._app_configuration_repository.update(app_configuration)
            return updated_app_configuration
        except Exception as e:
            raise ValidationException(f"Error updating app_configuration: {str(e)}")
    
    async def get_app_configuration(self, app_configuration_id: int) -> AppConfiguration:
        """Ottiene un app_configuration per ID"""
        app_configuration = self._app_configuration_repository.get_by_id_or_raise(app_configuration_id)
        return app_configuration
    
    async def get_app_configurations(self, page: int = 1, limit: int = 10, **filters) -> List[AppConfiguration]:
        """Ottiene la lista dei app_configuration con filtri"""
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
            app_configurations = self._app_configuration_repository.get_all(**filters)
            
            return app_configurations
        except Exception as e:
            raise ValidationException(f"Error retrieving app_configurations: {str(e)}")
    
    async def delete_app_configuration(self, app_configuration_id: int) -> bool:
        """Elimina un app_configuration"""
        # Verifica esistenza
        self._app_configuration_repository.get_by_id_or_raise(app_configuration_id)
        
        try:
            return self._app_configuration_repository.delete(app_configuration_id)
        except Exception as e:
            raise ValidationException(f"Error deleting app_configuration: {str(e)}")
    
    async def get_app_configurations_count(self, **filters) -> int:
        """Ottiene il numero totale di app_configuration con filtri"""
        try:
            # Usa il repository con i filtri
            return self._app_configuration_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting app_configurations: {str(e)}")

    async def get_app_configurations_by_category(self, category: str) -> List[AppConfiguration]:
        """Ottiene tutte le configurazioni per categoria (case insensitive)."""
        if not category or not str(category).strip():
            return []
        try:
            return self._app_configuration_repository.get_by_category(str(category).strip())
        except Exception as e:
            raise ValidationException(f"Error retrieving app_configurations by category: {str(e)}")

    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per AppConfiguration"""
        # Validazioni specifiche per AppConfiguration se necessarie
        pass
