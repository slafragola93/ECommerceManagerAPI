"""
OrderState Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.order_state_service_interface import IOrderStateService
from src.repository.interfaces.order_state_repository_interface import IOrderStateRepository
from src.schemas.order_state_schema import OrderStateSchema
from src.models.order_state import OrderState
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class OrderStateService(IOrderStateService):
    """OrderState Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, order_state_repository: IOrderStateRepository):
        self._order_state_repository = order_state_repository
    
    async def create_order_state(self, order_state_data: OrderStateSchema) -> OrderState:
        """Crea un nuovo order_state con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(order_state_data, 'name') and order_state_data.name:
            existing_order_state = self._order_state_repository.get_by_name(order_state_data.name)
            if existing_order_state:
                raise BusinessRuleException(
                    f"Stato ordine con nome '{order_state_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": order_state_data.name}
                )
        
        # Crea il order_state
        try:
            order_state = OrderState(**order_state_data.model_dump())
            order_state = self._order_state_repository.create(order_state)
            return order_state
        except Exception as e:
            raise ValidationException(f"Errore nella creazione dello stato ordine: {str(e)}")
    
    async def update_order_state(self, order_state_id: int, order_state_data: OrderStateSchema) -> OrderState:
        """Aggiorna un order_state esistente"""
        
        # Verifica esistenza
        order_state = self._order_state_repository.get_by_id_or_raise(order_state_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(order_state_data, 'name') and order_state_data.name != order_state.name:
            existing = self._order_state_repository.get_by_name(order_state_data.name)
            if existing and existing.id_order_state != order_state_id:
                raise BusinessRuleException(
                    f"Stato ordine con nome '{order_state_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": order_state_data.name}
                )
        
        # Aggiorna il order_state
        try:
            # Aggiorna i campi
            for field_name, value in order_state_data.model_dump(exclude_unset=True).items():
                if hasattr(order_state, field_name) and value is not None:
                    setattr(order_state, field_name, value)
            
            updated_order_state = self._order_state_repository.update(order_state)
            return updated_order_state
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dello stato ordine: {str(e)}")
    
    async def get_order_state(self, order_state_id: int) -> OrderState:
        """Ottiene un order_state per ID"""
        order_state = self._order_state_repository.get_by_id_or_raise(order_state_id)
        return order_state
    
    async def get_order_states(self, page: int = 1, limit: int = 10, **filters) -> List[OrderState]:
        """Ottiene la lista dei order_state con filtri"""
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
            order_states = self._order_state_repository.get_all(**filters)
            
            return order_states
        except Exception as e:
            raise ValidationException(f"Errore nel recupero degli stati ordine: {str(e)}")
    
    async def delete_order_state(self, order_state_id: int) -> bool:
        """Elimina un order_state"""
        # Verifica esistenza
        self._order_state_repository.get_by_id_or_raise(order_state_id)
        
        try:
            return self._order_state_repository.delete(order_state_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione dello stato ordine: {str(e)}")
    
    async def get_order_states_count(self, **filters) -> int:
        """Ottiene il numero totale di order_state con filtri"""
        try:
            # Usa il repository con i filtri
            return self._order_state_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio degli stati ordine: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per OrderState"""
        # Validazioni specifiche per OrderState se necessarie
        pass
