"""
ShippingState Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.shipping_state_service_interface import IShippingStateService
from src.repository.interfaces.shipping_state_repository_interface import IShippingStateRepository
from src.schemas.shipping_state_schema import ShippingStateSchema
from src.models.shipping_state import ShippingState
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class ShippingStateService(IShippingStateService):
    """ShippingState Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, shipping_state_repository: IShippingStateRepository):
        self._shipping_state_repository = shipping_state_repository
    
    async def create_shipping_state(self, shipping_state_data: ShippingStateSchema) -> ShippingState:
        """Crea un nuovo shipping_state con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(shipping_state_data, 'name') and shipping_state_data.name:
            existing_shipping_state = self._shipping_state_repository.get_by_name(shipping_state_data.name)
            if existing_shipping_state:
                raise BusinessRuleException(
                    f"ShippingState with name '{shipping_state_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": shipping_state_data.name}
                )
        
        # Crea il shipping_state
        try:
            shipping_state = ShippingState(**shipping_state_data.dict())
            shipping_state = self._shipping_state_repository.create(shipping_state)
            return shipping_state
        except Exception as e:
            raise ValidationException(f"Error creating shipping_state: {str(e)}")
    
    async def update_shipping_state(self, shipping_state_id: int, shipping_state_data: ShippingStateSchema) -> ShippingState:
        """Aggiorna un shipping_state esistente"""
        
        # Verifica esistenza
        shipping_state = self._shipping_state_repository.get_by_id_or_raise(shipping_state_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(shipping_state_data, 'name') and shipping_state_data.name != shipping_state.name:
            existing = self._shipping_state_repository.get_by_name(shipping_state_data.name)
            if existing and existing.id_shipping_state != shipping_state_id:
                raise BusinessRuleException(
                    f"ShippingState with name '{shipping_state_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": shipping_state_data.name}
                )
        
        # Aggiorna il shipping_state
        try:
            # Aggiorna i campi
            for field_name, value in shipping_state_data.dict(exclude_unset=True).items():
                if hasattr(shipping_state, field_name) and value is not None:
                    setattr(shipping_state, field_name, value)
            
            updated_shipping_state = self._shipping_state_repository.update(shipping_state)
            return updated_shipping_state
        except Exception as e:
            raise ValidationException(f"Error updating shipping_state: {str(e)}")
    
    async def get_shipping_state(self, shipping_state_id: int) -> ShippingState:
        """Ottiene un shipping_state per ID"""
        shipping_state = self._shipping_state_repository.get_by_id_or_raise(shipping_state_id)
        return shipping_state
    
    async def get_shipping_states(self, page: int = 1, limit: int = 10, **filters) -> List[ShippingState]:
        """Ottiene la lista dei shipping_state con filtri"""
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
            shipping_states = self._shipping_state_repository.get_all(**filters)
            
            return shipping_states
        except Exception as e:
            raise ValidationException(f"Error retrieving shipping_states: {str(e)}")
    
    async def delete_shipping_state(self, shipping_state_id: int) -> bool:
        """Elimina un shipping_state"""
        # Verifica esistenza
        self._shipping_state_repository.get_by_id_or_raise(shipping_state_id)
        
        try:
            return self._shipping_state_repository.delete(shipping_state_id)
        except Exception as e:
            raise ValidationException(f"Error deleting shipping_state: {str(e)}")
    
    async def get_shipping_states_count(self, **filters) -> int:
        """Ottiene il numero totale di shipping_state con filtri"""
        try:
            # Usa il repository con i filtri
            return self._shipping_state_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting shipping_states: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per ShippingState"""
        # Validazioni specifiche per ShippingState se necessarie
        pass
