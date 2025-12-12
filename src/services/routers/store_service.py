"""
Store Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.store_service_interface import IStoreService
from src.repository.interfaces.store_repository_interface import IStoreRepository
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.store_schema import StoreCreateSchema, StoreUpdateSchema
from src.models.store import Store
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class StoreService(IStoreService):
    """Store Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, store_repository: IStoreRepository, platform_repository: IPlatformRepository):
        self._store_repository = store_repository
        self._platform_repository = platform_repository
    
    async def create_store(self, store_data: StoreCreateSchema) -> Store:
        """Crea un nuovo store con validazioni business"""
        
        # Business Rule 1: Verifica che la piattaforma esista
        platform = self._platform_repository.get_by_id(store_data.id_platform)
        if not platform:
            raise NotFoundException(
                f"Platform with ID {store_data.id_platform} not found",
                ErrorCode.NOT_FOUND,
                {"id_platform": store_data.id_platform}
            )
        
        # Business Rule 2: Nome deve essere unico
        if store_data.name:
            existing_store = self._store_repository.get_by_name(store_data.name)
            if existing_store:
                raise BusinessRuleException(
                    f"Store with name '{store_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": store_data.name}
                )
        
        # Business Rule 3: Se is_default=True, rimuovi default da altri store
        if store_data.is_default:
            existing_default = self._store_repository.get_default()
            if existing_default:
                existing_default.is_default = False
                self._store_repository.update(existing_default)
        
        # Crea lo store
        try:
            store = Store(**store_data.model_dump())
            store = self._store_repository.create(store)
            return store
        except Exception as e:
            raise ValidationException(f"Error creating store: {str(e)}")
    
    async def update_store(self, store_id: int, store_data: StoreUpdateSchema) -> Store:
        """Aggiorna uno store esistente"""
        
        # Verifica esistenza
        store = self._store_repository.get_by_id_or_raise(store_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if store_data.name and store_data.name != store.name:
            existing = self._store_repository.get_by_name(store_data.name)
            if existing and existing.id_store != store_id:
                raise BusinessRuleException(
                    f"Store with name '{store_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": store_data.name}
                )
        
        # Business Rule: Se id_platform cambia, verifica che esista
        if store_data.id_platform and store_data.id_platform != store.id_platform:
            platform = self._platform_repository.get_by_id(store_data.id_platform)
            if not platform:
                raise NotFoundException(
                    f"Platform with ID {store_data.id_platform} not found",
                    ErrorCode.NOT_FOUND,
                    {"id_platform": store_data.id_platform}
                )
        
        # Business Rule: Se is_default=True, rimuovi default da altri store
        if store_data.is_default is not None and store_data.is_default and not store.is_default:
            existing_default = self._store_repository.get_default()
            if existing_default and existing_default.id_store != store_id:
                existing_default.is_default = False
                self._store_repository.update(existing_default)
        
        # Aggiorna lo store
        try:
            # Aggiorna i campi
            for field_name, value in store_data.model_dump(exclude_unset=True).items():
                if hasattr(store, field_name) and value is not None:
                    setattr(store, field_name, value)
            
            updated_store = self._store_repository.update(store)
            return updated_store
        except Exception as e:
            raise ValidationException(f"Error updating store: {str(e)}")
    
    async def get_store(self, store_id: int) -> Store:
        """Ottiene uno store per ID"""
        store = self._store_repository.get_by_id_or_raise(store_id)
        return store
    
    async def get_stores(self, page: int = 1, limit: int = 10, **filters) -> List[Store]:
        """Ottiene la lista degli store con filtri"""
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
            stores = self._store_repository.get_all(**filters)
            
            return stores
        except Exception as e:
            raise ValidationException(f"Error retrieving stores: {str(e)}")
    
    async def delete_store(self, store_id: int) -> bool:
        """Elimina uno store"""
        # Verifica esistenza
        self._store_repository.get_by_id_or_raise(store_id)
        
        try:
            return self._store_repository.delete(store_id)
        except Exception as e:
            raise ValidationException(f"Error deleting store: {str(e)}")
    
    async def get_stores_count(self, **filters) -> int:
        """Ottiene il numero totale di store con filtri"""
        try:
            # Usa il repository con i filtri
            return self._store_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting stores: {str(e)}")
    
    async def get_default_store(self) -> Store:
        """Ottiene lo store di default"""
        store = self._store_repository.get_default()
        if not store:
            raise NotFoundException(
                "No default store found",
                ErrorCode.NOT_FOUND,
                {}
            )
        return store
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Store"""
        # Validazioni specifiche per Store se necessarie
        pass

