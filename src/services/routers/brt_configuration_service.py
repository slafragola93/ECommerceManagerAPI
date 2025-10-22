from typing import Optional
from src.repository.interfaces.brt_configuration_repository_interface import IBrtConfigurationRepository
from src.services.interfaces.brt_configuration_service_interface import IBrtConfigurationService
from src.schemas.brt_configuration_schema import (
    BrtConfigurationSchema,
    BrtConfigurationResponseSchema,
    BrtConfigurationUpdateSchema
)
from src.core.exceptions import BusinessRuleException, InfrastructureException


class BrtConfigurationService(IBrtConfigurationService):
    def __init__(self, brt_configuration_repository: IBrtConfigurationRepository):
        self._brt_configuration_repository = brt_configuration_repository

    async def create_configuration(self, id_carrier_api: int, config_data: BrtConfigurationSchema) -> BrtConfigurationResponseSchema:
        try:
            # Verifica se esiste già una configurazione per questo carrier_api
            existing_config = self._brt_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if existing_config:
                raise BusinessRuleException(f"BRT configuration already exists for carrier_api {id_carrier_api}")
            
            # Crea la configurazione
            config_dict = config_data.model_dump()
            config_dict['id_carrier_api'] = id_carrier_api
            
            created_config = self._brt_configuration_repository.create(config_dict)
            return BrtConfigurationResponseSchema.model_validate(created_config)
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error creating BRT configuration: {str(e)}")

    async def get_configuration_by_carrier(self, id_carrier_api: int) -> Optional[BrtConfigurationResponseSchema]:
        try:
            config = self._brt_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not config:
                return None
            return BrtConfigurationResponseSchema.model_validate(config)
        except Exception as e:
            raise InfrastructureException(f"Error retrieving BRT configuration: {str(e)}")

    async def update_configuration(self, id_carrier_api: int, config_data: BrtConfigurationUpdateSchema) -> BrtConfigurationResponseSchema:
        try:
            # Verifica se esiste la configurazione
            existing_config = self._brt_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not existing_config:
                raise BusinessRuleException(f"BRT configuration not found for carrier_api {id_carrier_api}")
            
            # Aggiorna solo i campi forniti
            update_data = config_data.model_dump(exclude_unset=True)
            if not update_data:
                return BrtConfigurationResponseSchema.model_validate(existing_config)
            
            updated_config = self._brt_configuration_repository.update(existing_config, update_data)
            return BrtConfigurationResponseSchema.model_validate(updated_config)
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error updating BRT configuration: {str(e)}")

    async def delete_configuration(self, id_carrier_api: int) -> bool:
        try:
            # Verifica se esiste la configurazione
            existing_config = self._brt_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not existing_config:
                raise BusinessRuleException(f"BRT configuration not found for carrier_api {id_carrier_api}")
            
            self._brt_configuration_repository.delete(existing_config)
            return True
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error deleting BRT configuration: {str(e)}")
