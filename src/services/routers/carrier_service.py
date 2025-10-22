"""
Carrier Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.carrier_service_interface import ICarrierService
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.schemas.carrier_schema import CarrierSchema
from src.models.carrier import Carrier
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class CarrierService(ICarrierService):
    """Carrier Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, carrier_repository: ICarrierRepository):
        self._carrier_repository = carrier_repository
    
    async def create_carrier(self, carrier_data: CarrierSchema) -> Carrier:
        """Crea un nuovo carrier con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(carrier_data, 'name') and carrier_data.name:
            existing_carrier = self._carrier_repository.get_by_name(carrier_data.name)
            if existing_carrier:
                raise BusinessRuleException(
                    f"Corriere con nome '{carrier_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": carrier_data.name}
                )
        
        # Crea il carrier
        try:
            carrier = Carrier(**carrier_data.model_dump())
            carrier = self._carrier_repository.create(carrier)
            return carrier
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del corriere: {str(e)}")
    
    async def update_carrier(self, carrier_id: int, carrier_data: CarrierSchema) -> Carrier:
        """Aggiorna un carrier esistente"""
        
        # Verifica esistenza
        carrier = self._carrier_repository.get_by_id_or_raise(carrier_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(carrier_data, 'name') and carrier_data.name != carrier.name:
            existing = self._carrier_repository.get_by_name(carrier_data.name)
            if existing and existing.id_carrier != carrier_id:
                raise BusinessRuleException(
                    f"Corriere con nome '{carrier_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": carrier_data.name}
                )
        
        # Aggiorna il carrier
        try:
            # Aggiorna i campi
            for field_name, value in carrier_data.model_dump(exclude_unset=True).items():
                if hasattr(carrier, field_name) and value is not None:
                    setattr(carrier, field_name, value)
            
            updated_carrier = self._carrier_repository.update(carrier)
            return updated_carrier
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del corriere: {str(e)}")
    
    async def get_carrier(self, carrier_id: int) -> Carrier:
        """Ottiene un carrier per ID"""
        carrier = self._carrier_repository.get_by_id_or_raise(carrier_id)
        return carrier
    
    async def get_carriers(self, page: int = 1, limit: int = 10, **filters) -> List[Carrier]:
        """Ottiene la lista dei carrier con filtri"""
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
            carriers = self._carrier_repository.get_all(**filters)
            
            return carriers
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei corrieri: {str(e)}")
    
    async def delete_carrier(self, carrier_id: int) -> bool:
        """Elimina un carrier"""
        # Verifica esistenza
        self._carrier_repository.get_by_id_or_raise(carrier_id)
        
        try:
            return self._carrier_repository.delete(carrier_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del corriere: {str(e)}")
    
    async def get_carriers_count(self, **filters) -> int:
        """Ottiene il numero totale di carrier con filtri"""
        try:
            # Usa il repository con i filtri
            return self._carrier_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei corrieri: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Carrier"""
        # Validazioni specifiche per Carrier se necessarie
        pass
