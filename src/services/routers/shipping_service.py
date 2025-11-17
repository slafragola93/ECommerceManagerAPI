"""
Shipping Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any, Dict
from src.services.interfaces.shipping_service_interface import IShippingService
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.schemas.shipping_schema import ShippingSchema
from src.models.shipping import Shipping
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import extract_shipping_status_changed_data

class ShippingService(IShippingService):
    """Shipping Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, shipping_repository: IShippingRepository):
        self._shipping_repository = shipping_repository
    
    async def create_shipping(self, shipping_data: ShippingSchema) -> Shipping:
        """Crea un nuovo shipping con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(shipping_data, 'name') and shipping_data.name:
            existing_shipping = self._shipping_repository.get_by_name(shipping_data.name)
            if existing_shipping:
                raise BusinessRuleException(
                    f"Shipping with name '{shipping_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": shipping_data.name}
                )
        
        # Crea il shipping
        try:
            shipping = Shipping(**shipping_data.model_dump())
            shipping = self._shipping_repository.create(shipping)
            return shipping
        except Exception as e:
            raise ValidationException(f"Error creating shipping: {str(e)}")
    
    def _should_emit_shipping_status_event(*args, result=None, **kwargs) -> bool:
        """Verifica se l'evento di cambio stato shipping deve essere emesso."""
        if not isinstance(result, dict):
            return False
        old_state_id = result.get("old_state_id")
        new_state_id = result.get("new_state_id")
        return old_state_id is not None and new_state_id is not None and old_state_id != new_state_id
    
    def _extract_shipping_update_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
        """Estrae i dati dell'evento di cambio stato shipping da update_shipping."""
        if not isinstance(result, dict):
            return None
        return {
            "id_shipping": result.get("id_shipping"),
            "old_state_id": result.get("old_state_id"),
            "new_state_id": result.get("new_state_id"),
        }
    
    @emit_event_on_success(
        event_type=EventType.SHIPPING_STATUS_CHANGED,
        data_extractor=extract_shipping_status_changed_data,
        condition=_should_emit_shipping_status_event,
        source="shipping_service.update_shipping",
    )
    async def update_shipping(self, shipping_id: int, shipping_data: ShippingSchema) -> Dict[str, Any]:
        """Aggiorna un shipping esistente"""
        
        # Verifica esistenza
        shipping = self._shipping_repository.get_by_id_or_raise(shipping_id)
        
        # Salva vecchio stato prima dell'aggiornamento
        old_state_id = shipping.id_shipping_state
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(shipping_data, 'name') and shipping_data.name != shipping.name:
            existing = self._shipping_repository.get_by_name(shipping_data.name)
            if existing and existing.id_shipping != shipping_id:
                raise BusinessRuleException(
                    f"Shipping with name '{shipping_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": shipping_data.name}
                )
        
        # Aggiorna il shipping
        try:
            # Aggiorna i campi
            for field_name, value in shipping_data.model_dump(exclude_unset=True).items():
                if hasattr(shipping, field_name) and value is not None:
                    setattr(shipping, field_name, value)
            
            updated_shipping = self._shipping_repository.update(shipping)
            
            # Restituisce dict per evento se stato è cambiato
            new_state_id = updated_shipping.id_shipping_state
            if old_state_id != new_state_id:
                return {
                    "id_shipping": shipping_id,
                    "old_state_id": old_state_id,
                    "new_state_id": new_state_id,
                    "shipping": updated_shipping
                }
            
            return {
                "id_shipping": shipping_id,
                "shipping": updated_shipping
            }
        except Exception as e:
            raise ValidationException(f"Error updating shipping: {str(e)}")
    
    async def get_shipping(self, shipping_id: int) -> Shipping:
        """Ottiene un shipping per ID"""
        shipping = self._shipping_repository.get_by_id_or_raise(shipping_id)
        return shipping
    
    async def get_shippings(self, page: int = 1, limit: int = 10, **filters) -> List[Shipping]:
        """Ottiene la lista dei shipping con filtri"""
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
            shippings = self._shipping_repository.get_all(**filters)
            
            return shippings
        except Exception as e:
            raise ValidationException(f"Error retrieving shippings: {str(e)}")
    
    async def delete_shipping(self, shipping_id: int) -> bool:
        """Elimina un shipping"""
        # Verifica esistenza
        self._shipping_repository.get_by_id_or_raise(shipping_id)
        
        try:
            return self._shipping_repository.delete(shipping_id)
        except Exception as e:
            raise ValidationException(f"Error deleting shipping: {str(e)}")
    
    async def get_shippings_count(self, **filters) -> int:
        """Ottiene il numero totale di shipping con filtri"""
        try:
            # Usa il repository con i filtri
            return self._shipping_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting shippings: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Shipping"""
        # Validazioni specifiche per Shipping se necessarie
        pass
