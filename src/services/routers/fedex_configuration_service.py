from typing import Optional
from src.repository.interfaces.fedex_configuration_repository_interface import IFedexConfigurationRepository
from src.services.interfaces.fedex_configuration_service_interface import IFedexConfigurationService
from src.schemas.fedex_configuration_schema import (
    FedexConfigurationSchema,
    FedexConfigurationResponseSchema,
    FedexConfigurationUpdateSchema
)
from src.core.exceptions import BusinessRuleException, InfrastructureException
from src.models.fedex_configuration import FedexScopeEnum


class FedexConfigurationService(IFedexConfigurationService):
    def __init__(self, fedex_configuration_repository: IFedexConfigurationRepository):
        self._fedex_configuration_repository = fedex_configuration_repository

    async def create_configuration(self, id_carrier_api: int, config_data: FedexConfigurationSchema) -> FedexConfigurationResponseSchema:
        try:
            # Verifica se esiste già una configurazione per questo carrier_api e scope
            scope = config_data.scope
            existing_config = self._fedex_configuration_repository.get_by_carrier_api_id_and_scope(id_carrier_api, scope)
            if existing_config:
                raise BusinessRuleException(f"Fedex configuration already exists for carrier_api {id_carrier_api} with scope {scope.value}")
            
            # Crea la configurazione
            config_dict = config_data.model_dump()
            config_dict['id_carrier_api'] = id_carrier_api
            
            created_config = self._fedex_configuration_repository.create(config_dict)
            return FedexConfigurationResponseSchema.model_validate(created_config)
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error creating Fedex configuration: {str(e)}")

    async def get_configuration_by_carrier(self, id_carrier_api: int) -> Optional[FedexConfigurationResponseSchema]:
        try:
            config = self._fedex_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not config:
                return None
            return FedexConfigurationResponseSchema.model_validate(config)
        except Exception as e:
            raise InfrastructureException(f"Error retrieving Fedex configuration: {str(e)}")

    async def update_configuration(self, id_carrier_api: int, config_data: FedexConfigurationUpdateSchema) -> FedexConfigurationResponseSchema:
        try:
            # Determina lo scope: se fornito nell'update, usalo; altrimenti cerca la prima configurazione esistente
            update_data = config_data.model_dump(exclude_unset=True)
            scope = update_data.get('scope')
            
            if scope:
                # Se lo scope è fornito, cerca la configurazione con quello scope
                scope_enum = FedexScopeEnum(scope) if isinstance(scope, str) else scope
                existing_config = self._fedex_configuration_repository.get_by_carrier_api_id_and_scope(id_carrier_api, scope_enum)
            else:
                # Altrimenti, cerca la prima configurazione esistente (per retrocompatibilità)
                existing_config = self._fedex_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            
            if not existing_config:
                raise BusinessRuleException(f"Fedex configuration not found for carrier_api {id_carrier_api}" + (f" with scope {scope}" if scope else ""))
            
            # Se lo scope viene cambiato, verifica che non esista già una configurazione con il nuovo scope
            if 'scope' in update_data:
                new_scope = FedexScopeEnum(update_data['scope']) if isinstance(update_data['scope'], str) else update_data['scope']
                if existing_config.scope != new_scope:
                    # Verifica che non esista già una configurazione con il nuovo scope
                    conflicting_config = self._fedex_configuration_repository.get_by_carrier_api_id_and_scope(id_carrier_api, new_scope)
                    if conflicting_config:
                        raise BusinessRuleException(f"Fedex configuration already exists for carrier_api {id_carrier_api} with scope {new_scope.value}")
            
            # Aggiorna solo i campi forniti
            if not update_data:
                return FedexConfigurationResponseSchema.model_validate(existing_config)
            
            updated_config = self._fedex_configuration_repository.update(existing_config, update_data)
            return FedexConfigurationResponseSchema.model_validate(updated_config)
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error updating Fedex configuration: {str(e)}")

    async def delete_configuration(self, id_carrier_api: int) -> bool:
        try:
            # Verifica se esiste la configurazione
            existing_config = self._fedex_configuration_repository.get_by_carrier_api_id(id_carrier_api)
            if not existing_config:
                raise BusinessRuleException(f"Fedex configuration not found for carrier_api {id_carrier_api}")
            
            self._fedex_configuration_repository.delete(existing_config)
            return True
            
        except BusinessRuleException:
            raise
        except Exception as e:
            raise InfrastructureException(f"Error deleting Fedex configuration: {str(e)}")
