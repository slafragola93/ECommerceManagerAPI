from typing import Optional
from src.repository.interfaces.dhl_configuration_repository_interface import IDhlConfigurationRepository
from src.services.interfaces.dhl_configuration_service_interface import IDhlConfigurationService
from src.schemas.dhl_configuration_schema import (
    DhlConfigurationSchema,
    DhlConfigurationResponseSchema,
    DhlConfigurationUpdateSchema
)
from src.core.exceptions import BusinessRuleException, InfrastructureException


class DhlConfigurationService(IDhlConfigurationService):
    def __init__(self, dhl_configuration_repository: IDhlConfigurationRepository):
        self._dhl_configuration_repository = dhl_configuration_repository

    async def create_configuration(self, id_carrier_api: int, config_data: DhlConfigurationSchema) -> DhlConfigurationResponseSchema:
        try:
            # Verifica se esiste già una configurazione per questo carrier_api
            existing_config = self._dhl_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if existing_config:
                raise BusinessRuleException(f"DHL configuration already exists for carrier_api {id_carrier_api}")
            
            # Crea la configurazione
            config_dict = config_data.model_dump()
            config_dict['id_carrier_api'] = id_carrier_api
            
            created_config = self._dhl_configuration_repository.create(config_dict)
            return DhlConfigurationResponseSchema.model_validate(created_config)
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error creating DHL configuration: {str(e)}")

    async def get_configuration_by_carrier(self, id_carrier_api: int) -> Optional[DhlConfigurationResponseSchema]:
        try:
            config = self._dhl_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not config:
                return None
            return DhlConfigurationResponseSchema.model_validate(config)
        except Exception as e:
            raise InfrastructureException(f"Error retrieving DHL configuration: {str(e)}")

    async def update_configuration(self, id_carrier_api: int, config_data: DhlConfigurationUpdateSchema) -> DhlConfigurationResponseSchema:
        try:
            # Verifica se esiste la configurazione
            existing_config = self._dhl_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not existing_config:
                raise BusinessRuleException(f"DHL configuration not found for carrier_api {id_carrier_api}")
            
            # Aggiorna solo i campi forniti
            update_data = config_data.model_dump(exclude_unset=True)
            if not update_data:
                return DhlConfigurationResponseSchema.model_validate(existing_config)
            
            updated_config = self._dhl_configuration_repository.update(existing_config, update_data)
            return DhlConfigurationResponseSchema.model_validate(updated_config)
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error updating DHL configuration: {str(e)}")

    async def delete_configuration(self, id_carrier_api: int) -> bool:
        try:
            # Verifica se esiste la configurazione
            existing_config = self._dhl_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not existing_config:
                raise BusinessRuleException(f"DHL configuration not found for carrier_api {id_carrier_api}")
            
            self._dhl_configuration_repository.delete(existing_config)
            return True
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error deleting DHL configuration: {str(e)}")
