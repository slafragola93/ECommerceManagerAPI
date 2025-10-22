"""
Lang Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.lang_service_interface import ILangService
from src.repository.interfaces.lang_repository_interface import ILangRepository
from src.schemas.lang_schema import LangSchema
from src.models.lang import Lang
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class LangService(ILangService):
    """Lang Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, lang_repository: ILangRepository):
        self._lang_repository = lang_repository
    
    async def create_lang(self, lang_data: LangSchema) -> Lang:
        """Crea un nuovo lang con validazioni business"""
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(lang_data, 'name') and lang_data.name:
            existing_lang = self._lang_repository.get_by_name(lang_data.name)
            if existing_lang:
                raise BusinessRuleException(
                    f"Lingua '{lang_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": lang_data.name}
                )
        
        # Crea il lang
        try:
            lang = Lang(**lang_data.model_dump())
            lang = self._lang_repository.create(lang)
            return lang
        except Exception as e:
            raise ValidationException(f"Errore nella creazione della lingua: {str(e)}")
    
    async def update_lang(self, lang_id: int, lang_data: LangSchema) -> Lang:
        """Aggiorna un lang esistente"""
        
        # Verifica esistenza
        lang = self._lang_repository.get_by_id_or_raise(lang_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(lang_data, 'name') and lang_data.name != lang.name:
            existing = self._lang_repository.get_by_name(lang_data.name)
            if existing and existing.id_lang != lang_id:
                raise BusinessRuleException(
                    f"Lingua '{lang_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": lang_data.name}
                )
        
        # Aggiorna il lang
        try:
            # Aggiorna i campi
            for field_name, value in lang_data.model_dump(exclude_unset=True).items():
                if hasattr(lang, field_name) and value is not None:
                    setattr(lang, field_name, value)
            
            updated_lang = self._lang_repository.update(lang)
            return updated_lang
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento della lingua: {str(e)}")
    
    async def get_lang(self, lang_id: int) -> Lang:
        """Ottiene un lang per ID"""
        lang = self._lang_repository.get_by_id_or_raise(lang_id)
        return lang
    
    async def get_langs(self, page: int = 1, limit: int = 10, **filters) -> List[Lang]:
        """Ottiene la lista dei lang con filtri"""
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
            langs = self._lang_repository.get_all(**filters)
            
            return langs
        except Exception as e:
            raise ValidationException(f"Errore nella ricerca delle lingue: {str(e)}")
    
    async def delete_lang(self, lang_id: int) -> bool:
        """Elimina un lang"""
        # Verifica esistenza
        self._lang_repository.get_by_id_or_raise(lang_id)
        
        try:
            return self._lang_repository.delete(lang_id)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione della lingua: {str(e)}")
    
    async def get_langs_count(self, **filters) -> int:
        """Ottiene il numero totale di lang con filtri"""
        try:
            # Usa il repository con i filtri
            return self._lang_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nella ricerca del numero di lingue: {str(e)}")
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Lang"""
        # Validazioni specifiche per Lang se necessarie
        pass
