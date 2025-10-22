"""
Brand Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.brand_service_interface import IBrandService
from src.repository.interfaces.brand_repository_interface import IBrandRepository
from src.schemas.brand_schema import BrandSchema
from src.models.brand import Brand
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class BrandService(IBrandService):
    """Brand Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, brand_repository: IBrandRepository):
        self._brand_repository = brand_repository
    
    async def create_brand(self, brand_data: BrandSchema) -> Brand:
        """Crea un nuovo brand con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(brand_data, 'name') and brand_data.name:
            existing_brand = self._brand_repository.get_by_name(brand_data.name)
            if existing_brand:
                raise BusinessRuleException(
                    f"Brand con nome '{brand_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": brand_data.name}
                )
        
        # Crea il brand
        try:
            # Prepara i dati per la creazione, gestendo i valori None
            brand_dict = brand_data.model_dump()
            
            # Se id_origin è None, lo imposta a None (default del modello)
            # Il modello Brand ha default=None, quindi None è accettabile
            if brand_dict.get('id_origin') is None:
                brand_dict['id_origin'] = None
            
            brand = Brand(**brand_dict)
            brand = self._brand_repository.create(brand)
            return brand
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del brand: {str(e)}")
    
    async def update_brand(self, brand_id: int, brand_data: BrandSchema) -> Brand:
        """Aggiorna un brand esistente"""
        
        # Verifica esistenza
        brand = self._brand_repository.get_by_id_or_raise(brand_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(brand_data, 'name') and brand_data.name != brand.name:
            existing = self._brand_repository.get_by_name(brand_data.name)
            if existing and existing.id_brand != brand_id:
                raise BusinessRuleException(
                    f"Brand con nome '{brand_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": brand_data.name}
                )
        
        # Aggiorna il brand
        try:
            # Aggiorna i campi
            for field_name, value in brand_data.model_dump(exclude_unset=True).items():
                if hasattr(brand, field_name) and value is not None:
                    setattr(brand, field_name, value)
            
            updated_brand = self._brand_repository.update(brand)
            return updated_brand
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del brand: {str(e)}")
    
    async def get_brand(self, brand_id: int) -> Brand:
        """Ottiene un brand per ID"""
        brand = self._brand_repository.get_by_id_or_raise(brand_id)
        return brand
    
    async def get_brands(self, page: int = 1, limit: int = 10, **filters) -> List[Brand]:
        """Ottiene la lista dei brand con filtri"""
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
            brands = self._brand_repository.get_all(**filters)
            
            return brands
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei brand: {str(e)}")
    
    async def delete_brand(self, brand_id: int) -> bool:
        """Elimina un brand"""
        # Verifica esistenza
        self._brand_repository.get_by_id_or_raise(brand_id)
        
        try:
            return self._brand_repository.delete(brand_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del brand: {str(e)}")
    
    async def get_brands_count(self, **filters) -> int:
        """Ottiene il numero totale di brand con filtri"""
        try:
            # Usa il repository con i filtri
            return self._brand_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei brand: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Brand"""
        # Validazioni specifiche per Brand se necessarie
        pass
