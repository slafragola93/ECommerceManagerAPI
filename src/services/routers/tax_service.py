"""
Tax Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.tax_service_interface import ITaxService
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.schemas.tax_schema import TaxSchema
from src.models.tax import Tax
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class TaxService(ITaxService):
    """Tax Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, tax_repository: ITaxRepository):
        self._tax_repository = tax_repository
    
    async def create_tax(self, tax_data: TaxSchema) -> Tax:
        """Crea un nuovo tax con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(tax_data, 'name') and tax_data.name:
            existing_tax = self._tax_repository.get_by_name(tax_data.name)
            if existing_tax:
                raise BusinessRuleException(
                    f"Tax with name '{tax_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": tax_data.name}
                )
        
        # Crea il tax
        try:
            tax = Tax(**tax_data.dict())
            tax = self._tax_repository.create(tax)
            return tax
        except Exception as e:
            raise ValidationException(f"Error creating tax: {str(e)}")
    
    async def update_tax(self, tax_id: int, tax_data: TaxSchema) -> Tax:
        """Aggiorna un tax esistente"""
        
        # Verifica esistenza
        tax = self._tax_repository.get_by_id_or_raise(tax_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(tax_data, 'name') and tax_data.name != tax.name:
            existing = self._tax_repository.get_by_name(tax_data.name)
            if existing and existing.id_tax != tax_id:
                raise BusinessRuleException(
                    f"Tax with name '{tax_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": tax_data.name}
                )
        
        # Aggiorna il tax
        try:
            # Aggiorna i campi
            for field_name, value in tax_data.dict(exclude_unset=True).items():
                if hasattr(tax, field_name) and value is not None:
                    setattr(tax, field_name, value)
            
            updated_tax = self._tax_repository.update(tax)
            return updated_tax
        except Exception as e:
            raise ValidationException(f"Error updating tax: {str(e)}")
    
    async def get_tax(self, tax_id: int) -> Tax:
        """Ottiene un tax per ID"""
        tax = self._tax_repository.get_by_id_or_raise(tax_id)
        return tax
    
    async def get_taxes(self, page: int = 1, limit: int = 10, **filters) -> List[Tax]:
        """Ottiene la lista dei tax con filtri"""
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
            taxes = self._tax_repository.get_all(**filters)
            
            return taxes
        except Exception as e:
            raise ValidationException(f"Error retrieving taxes: {str(e)}")
    
    async def delete_tax(self, tax_id: int) -> bool:
        """Elimina un tax"""
        # Verifica esistenza
        self._tax_repository.get_by_id_or_raise(tax_id)
        
        try:
            return self._tax_repository.delete(tax_id)
        except Exception as e:
            raise ValidationException(f"Error deleting tax: {str(e)}")
    
    async def get_taxes_count(self, **filters) -> int:
        """Ottiene il numero totale di tax con filtri"""
        try:
            # Usa il repository con i filtri
            return self._tax_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting taxes: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Tax"""
        # Validazioni specifiche per Tax se necessarie
        pass
