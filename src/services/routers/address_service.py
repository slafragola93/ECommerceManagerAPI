"""
Address Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.address_service_interface import IAddressService
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.schemas.address_schema import AddressSchema
from src.models.address import Address
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class AddressService(IAddressService):
    """Address Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, address_repository: IAddressRepository):
        self._address_repository = address_repository
    
    async def create_address(self, address_data: AddressSchema) -> Address:
        """Crea un nuovo address con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(address_data, 'name') and address_data.name:
            existing_address = self._address_repository.get_by_name(address_data.name)
            if existing_address:
                raise BusinessRuleException(
                    f"Indirizzo con nome '{address_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": address_data.name}
                )
        
        # Crea il address
        try:
            address = Address(**address_data.model_dump())
            address = self._address_repository.create(address)
            return address
        except Exception as e:
            raise ValidationException(f"Errore nella creazione dell'indirizzo: {str(e)}")
    
    async def update_address(self, address_id: int, address_data: AddressSchema) -> Address:
        """Aggiorna un address esistente"""
        
        # Verifica esistenza
        address = self._address_repository.get_by_id_or_raise(address_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(address_data, 'name') and address_data.name != address.name:
            existing = self._address_repository.get_by_name(address_data.name)
            if existing and existing.id_address != address_id:
                raise BusinessRuleException(
                    f"Indirizzo con nome '{address_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": address_data.name}
                )
        
        # Aggiorna il address
        try:
            # Aggiorna i campi
            for field_name, value in address_data.model_dump(exclude_unset=True).items():
                if hasattr(address, field_name) and value is not None:
                    setattr(address, field_name, value)
            
            updated_address = self._address_repository.update(address)
            return updated_address
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dell'indirizzo: {str(e)}")
    
    async def get_address(self, address_id: int) -> Address:
        """Ottiene un address per ID"""
        address = self._address_repository.get_by_id_or_raise(address_id)
        return address
    
    async def get_addresses(self, page: int = 1, limit: int = 10, **filters) -> List[Address]:
        """Ottiene la lista dei address con filtri"""
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
            addresses = self._address_repository.get_all(**filters)
            
            return addresses
        except Exception as e:
            raise ValidationException(f"Errore nel recupero degli indirizzi: {str(e)}")
    
    async def delete_address(self, address_id: int) -> bool:
        """Elimina un address"""
        # Verifica esistenza
        self._address_repository.get_by_id_or_raise(address_id)
        
        try:
            return self._address_repository.delete(address_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione dell'indirizzo: {str(e)}")
    
    async def get_addresses_count(self, **filters) -> int:
        """Ottiene il numero totale di address con filtri"""
        try:
            # Usa il repository con i filtri
            return self._address_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio degli indirizzi: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Address"""
        # Validazioni specifiche per Address se necessarie
        pass
