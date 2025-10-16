"""
Country Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.country_service_interface import ICountryService
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.schemas.country_schema import CountrySchema
from src.models.country import Country
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class CountryService(ICountryService):
    """Country Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, country_repository: ICountryRepository):
        self._country_repository = country_repository
    
    async def create_country(self, country_data: CountrySchema) -> Country:
        """Crea un nuovo country con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(country_data, 'name') and country_data.name:
            existing_country = self._country_repository.get_by_name(country_data.name)
            if existing_country:
                raise BusinessRuleException(
                    f"Country with name '{country_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": country_data.name}
                )
        
        # Crea il country
        try:
            country = Country(**country_data.dict())
            country = self._country_repository.create(country)
            return country
        except Exception as e:
            raise ValidationException(f"Error creating country: {str(e)}")
    
    async def update_country(self, country_id: int, country_data: CountrySchema) -> Country:
        """Aggiorna un country esistente"""
        
        # Verifica esistenza
        country = self._country_repository.get_by_id_or_raise(country_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(country_data, 'name') and country_data.name != country.name:
            existing = self._country_repository.get_by_name(country_data.name)
            if existing and existing.id_country != country_id:
                raise BusinessRuleException(
                    f"Country with name '{country_data.name}' already exists",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": country_data.name}
                )
        
        # Aggiorna il country
        try:
            # Aggiorna i campi
            for field_name, value in country_data.dict(exclude_unset=True).items():
                if hasattr(country, field_name) and value is not None:
                    setattr(country, field_name, value)
            
            updated_country = self._country_repository.update(country)
            return updated_country
        except Exception as e:
            raise ValidationException(f"Error updating country: {str(e)}")
    
    async def get_country(self, country_id: int) -> Country:
        """Ottiene un country per ID"""
        country = self._country_repository.get_by_id_or_raise(country_id)
        return country
    
    async def get_countries(self, page: int = 1, limit: int = 10, **filters) -> List[Country]:
        """Ottiene la lista dei country con filtri"""
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
            countries = self._country_repository.get_all(**filters)
            
            return countries
        except Exception as e:
            raise ValidationException(f"Error retrieving countries: {str(e)}")
    
    async def delete_country(self, country_id: int) -> bool:
        """Elimina un country"""
        # Verifica esistenza
        self._country_repository.get_by_id_or_raise(country_id)
        
        try:
            return self._country_repository.delete(country_id)
        except Exception as e:
            raise ValidationException(f"Error deleting country: {str(e)}")
    
    async def get_countries_count(self, **filters) -> int:
        """Ottiene il numero totale di country con filtri"""
        try:
            # Usa il repository con i filtri
            return self._country_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Error counting countries: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Country"""
        # Validazioni specifiche per Country se necessarie
        pass
