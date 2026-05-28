"""
Tax Service rifattorizzato seguendo i principi SOLID
"""
import logging
from typing import Any, Dict, List, Optional

from src.core.cache import get_cache_manager
from src.core.exceptions import (
    BusinessRuleException,
    ErrorCode,
    NotFoundException,
    ValidationException,
)
from src.events.core.event import EventType
from src.events.decorators import emit_event_on_success
from src.models.tax import Tax
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.schemas.tax_schema import TaxCountryDefaultResponseSchema, TaxResponseSchema, TaxSchema
from src.services.interfaces.tax_service_interface import ITaxService

logger = logging.getLogger(__name__)


def _extract_tax_country_default_changed_data(*args, **kwargs) -> Dict[str, Any]:
    result = kwargs.get("result")
    if result is None:
        return {}
    return {
        "id_tax": getattr(result, "id_tax", None),
        "id_country": getattr(result, "id_country", None),
        "percentage": getattr(result, "percentage", None),
        "is_default": getattr(result, "is_default", None),
    }

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
            tax = Tax(**tax_data.model_dump())
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
            for field_name, value in tax_data.model_dump(exclude_unset=True).items():
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

    def _to_tax_response(self, tax: Tax) -> TaxResponseSchema:
        return TaxResponseSchema.model_validate(tax)

    def _to_country_default_response(self, tax: Tax) -> TaxCountryDefaultResponseSchema:
        country = getattr(tax, "country", None)
        payload = self._to_tax_response(tax).model_dump()
        if country is None and tax.id_country:
            from src.models.country import Country

            session = getattr(self._tax_repository, "_session", None)
            if session is not None:
                country = session.query(Country).filter(Country.id_country == tax.id_country).first()
        payload["country_iso_code"] = country.iso_code if country else None
        payload["country_name"] = country.name if country else None
        return TaxCountryDefaultResponseSchema(**payload)

    async def _invalidate_init_tax_cache(self) -> None:
        try:
            cache_manager = await get_cache_manager()
            await cache_manager.delete("init_data:static")
            await cache_manager.delete("init_data:full")
        except Exception as exc:
            logger.warning("Impossibile invalidare cache init dopo modifica tax: %s", exc)

    async def get_default_by_country(self, id_country: int) -> Optional[TaxResponseSchema]:
        tax = self._tax_repository.get_default_by_country(id_country)
        if not tax:
            return None
        return self._to_tax_response(tax)

    async def get_default_by_country_iso(self, iso_code: str) -> Optional[TaxResponseSchema]:
        if not iso_code or len(str(iso_code).strip()) != 2:
            raise BusinessRuleException(
                "country ISO code must be a 2-letter ISO 3166-1 alpha-2 value",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"iso_code": iso_code},
            )
        tax = self._tax_repository.get_default_by_country_iso(iso_code)
        if not tax:
            return None
        return self._to_tax_response(tax)

    async def list_country_defaults(self) -> List[TaxCountryDefaultResponseSchema]:
        taxes = self._tax_repository.list_country_defaults()
        return [self._to_country_default_response(t) for t in taxes]

    @emit_event_on_success(
        event_type=EventType.TAX_COUNTRY_DEFAULT_CHANGED,
        data_extractor=_extract_tax_country_default_changed_data,
        source="tax_service.set_country_default",
    )
    async def set_country_default(self, id_tax: int) -> Tax:
        tax = self._tax_repository.get_tax_by_id(id_tax)
        if not tax:
            raise NotFoundException("Tax", id_tax)

        if tax.id_country is None or tax.id_country <= 0:
            raise BusinessRuleException(
                "Tax must have id_country set before it can be a country default",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"id_tax": id_tax},
            )

        updated = self._tax_repository.set_country_default_atomic(id_tax, tax.id_country)
        await self._invalidate_init_tax_cache()
        return updated
