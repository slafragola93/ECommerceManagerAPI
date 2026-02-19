"""
API Carrier Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.api_carrier_service_interface import IApiCarrierService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.schemas.carrier_api_schema import CarrierApiSchema
from src.models.carrier_api import CarrierApi
from src.core.exceptions import (
    ValidationException, 
    BusinessRuleException,
    ErrorCode
)

class ApiCarrierService(IApiCarrierService):
    """API Carrier Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, api_carrier_repository: IApiCarrierRepository):
        self._api_carrier_repository = api_carrier_repository
    
    async def create_api_carrier(self, api_carrier_data: CarrierApiSchema) -> CarrierApi:
        """Crea un nuovo API carrier con validazioni business"""
        
        # Business Rule 1: Validazione nome
        await self._validate_name(api_carrier_data.name)
        
        # Business Rule 2: Nome deve essere unico
        existing_carrier = self._api_carrier_repository.get_by_name(api_carrier_data.name)
        if existing_carrier:
            raise BusinessRuleException(
                f"API Carrier with name '{api_carrier_data.name}' already exists",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"name": api_carrier_data.name}
            )
        
        # Business Rule 3: Account number deve essere unico
        existing_account = self._api_carrier_repository.get_by_account_number(api_carrier_data.account_number)
        if existing_account:
            raise BusinessRuleException(
                f"API Carrier with account number '{api_carrier_data.account_number}' already exists",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"account_number": api_carrier_data.account_number}
            )
        
        # Crea l'API carrier
        try:
            api_carrier = CarrierApi(**api_carrier_data.model_dump())
            api_carrier = self._api_carrier_repository.create(api_carrier)
            return api_carrier
        except Exception as e:
            raise ValidationException(f"Error creating API carrier: {str(e)}")
    
    async def update_api_carrier(self, api_carrier_id: int, api_carrier_data: CarrierApiSchema) -> CarrierApi:
        """Aggiorna un API carrier esistente"""
        
        # Verifica esistenza
        api_carrier = self._api_carrier_repository.get_by_id_or_raise(api_carrier_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if api_carrier_data.name != api_carrier.name:
            await self._validate_name(api_carrier_data.name)
            existing = self._api_carrier_repository.get_by_name(api_carrier_data.name)
            if existing and existing.id_carrier_api != api_carrier_id:
                raise BusinessRuleException(
                    f"API Carrier with name '{api_carrier_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": api_carrier_data.name}
                )
        
        # Business Rule: Se account number cambia, deve essere unico
        if api_carrier_data.account_number != api_carrier.account_number:
            existing = self._api_carrier_repository.get_by_account_number(api_carrier_data.account_number)
            if existing and existing.id_carrier_api != api_carrier_id:
                raise BusinessRuleException(
                    f"API Carrier with account number '{api_carrier_data.account_number}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"account_number": api_carrier_data.account_number}
                )
        
        # Aggiorna l'API carrier
        try:
            # Aggiorna i campi
            for field_name, value in api_carrier_data.model_dump(exclude_unset=True).items():
                if hasattr(api_carrier, field_name) and value is not None:
                    setattr(api_carrier, field_name, value)
            
            updated_api_carrier = self._api_carrier_repository.update(api_carrier)
            return updated_api_carrier
        except Exception as e:
            raise ValidationException(f"Error updating API carrier: {str(e)}")
    
    async def get_api_carrier(self, api_carrier_id: int) -> CarrierApi:
        """Ottiene un API carrier per ID"""
        api_carrier = self._api_carrier_repository.get_by_id_or_raise(api_carrier_id)
        return api_carrier
    
    async def get_api_carriers(self, page: int = 1, limit: int = 10, **filters) -> List[CarrierApi]:
        """Ottiene la lista degli API carriers con filtri"""
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
            api_carriers = self._api_carrier_repository.get_all(**filters)
            
            return api_carriers
        except Exception as e:
            raise ValidationException(f"Error retrieving API carriers: {str(e)}")
    
    async def delete_api_carrier(self, api_carrier_id: int) -> bool:
        """Elimina un API carrier"""
        # Verifica esistenza
        self._api_carrier_repository.get_by_id_or_raise(api_carrier_id)
        
        try:
            return self._api_carrier_repository.delete(api_carrier_id)
        except Exception as e:
            raise ValidationException(f"Error deleting API carrier: {str(e)}")
    
    async def get_api_carriers_count(self, **filters) -> int:
        """Ottiene il numero totale di API carriers con filtri"""
        try:
            return self._api_carrier_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting API carriers: {str(e)}")
    
    async def _validate_name(self, name: str) -> None:
        """Valida il nome dell'API carrier"""
        if not name or not name.strip():
            raise ValidationException("Name is required")
        
        if len(name.strip()) < 2:
            raise ValidationException("Name must be at least 2 characters long")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per API Carrier"""
        if hasattr(data, 'name'):
            await self._validate_name(data.name)
