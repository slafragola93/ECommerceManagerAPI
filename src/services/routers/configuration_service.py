"""
Configuration Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.configuration_service_interface import IConfigurationService
from src.repository.interfaces.configuration_repository_interface import IConfigurationRepository
from src.schemas.configuration_schema import ConfigurationSchema
from src.models.configuration import Configuration
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class ConfigurationService(IConfigurationService):
    """Configuration Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, configuration_repository: IConfigurationRepository):
        self._configuration_repository = configuration_repository
    
    async def create_configuration(self, configuration_data: ConfigurationSchema) -> Configuration:
        """Crea un nuovo configuration con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(configuration_data, 'name') and configuration_data.name:
            existing_configuration = self._configuration_repository.get_by_name(configuration_data.name)
            if existing_configuration:
                raise BusinessRuleException(
                    f"Configuration with name '{configuration_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": configuration_data.name}
                )
        
        # Crea il configuration
        try:
            configuration = Configuration(**configuration_data.model_dump())
            configuration = self._configuration_repository.create(configuration)
            return configuration
        except Exception as e:
            raise ValidationException(f"Error creating configuration: {str(e)}")
    
    async def update_configuration(self, configuration_id: int, configuration_data: ConfigurationSchema) -> Configuration:
        """Aggiorna un configuration esistente"""
        
        # Verifica esistenza
        configuration = self._configuration_repository.get_by_id_or_raise(configuration_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(configuration_data, 'name') and configuration_data.name != configuration.name:
            existing = self._configuration_repository.get_by_name(configuration_data.name)
            if existing and existing.id_configuration != configuration_id:
                raise BusinessRuleException(
                    f"Configuration with name '{configuration_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": configuration_data.name}
                )
        
        # Aggiorna il configuration
        try:
            # Aggiorna i campi
            for field_name, value in configuration_data.model_dump(exclude_unset=True).items():
                if hasattr(configuration, field_name) and value is not None:
                    setattr(configuration, field_name, value)
            
            updated_configuration = self._configuration_repository.update(configuration)
            return updated_configuration
        except Exception as e:
            raise ValidationException(f"Error updating configuration: {str(e)}")
    
    async def get_configuration(self, configuration_id: int) -> Configuration:
        """Ottiene un configuration per ID"""
        configuration = self._configuration_repository.get_by_id_or_raise(configuration_id)
        return configuration
    
    async def get_configurations(self, page: int = 1, limit: int = 10, **filters) -> List[Configuration]:
        """Ottiene la lista dei configuration con filtri"""
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
            configurations = self._configuration_repository.get_all(**filters)
            
            return configurations
        except Exception as e:
            raise ValidationException(f"Error retrieving configurations: {str(e)}")
    
    async def delete_configuration(self, configuration_id: int) -> bool:
        """Elimina un configuration"""
        # Verifica esistenza
        self._configuration_repository.get_by_id_or_raise(configuration_id)
        
        try:
            return self._configuration_repository.delete(configuration_id)
        except Exception as e:
            raise ValidationException(f"Error deleting configuration: {str(e)}")
    
    async def get_configurations_count(self, **filters) -> int:
        """Ottiene il numero totale di configuration con filtri"""
        try:
            # Usa il repository con i filtri
            return self._configuration_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting configurations: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Configuration"""
        # Validazioni specifiche per Configuration se necessarie
        pass
