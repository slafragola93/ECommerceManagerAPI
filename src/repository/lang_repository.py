"""
Lang Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.lang import Lang
from src.repository.interfaces.lang_repository_interface import ILangRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils
from src.schemas.lang_schema import LangSchema

class LangRepository(BaseRepository[Lang, int], ILangRepository):
    """Lang Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Lang)
    
    def get_all(self, **filters) -> List[Lang]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Lang.id_lang))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Lang]:
        """Ottiene un lang per nome (case insensitive)"""
        try:
            return self._session.query(Lang).filter(
                func.lower(Lang.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving lang by name: {str(e)}")
    
    def get_by_iso_code(self, iso_code: str) -> Optional[Lang]:
        """Ottiene un lang per codice ISO (case insensitive)"""
        try:
            return self._session.query(Lang).filter(
                func.lower(Lang.iso_code) == func.lower(iso_code)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving lang by iso_code: {str(e)}")
    
    def bulk_create_csv_import(self, data_list: List[LangSchema], batch_size: int = 1000) -> int:
        """
        Bulk insert languages da CSV import.
        
        Args:
            data_list: Lista LangSchema da inserire
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero languages inserite
        """
        if not data_list:
            return 0
        
        try:
            # Get existing id_origin to avoid duplicates
            origin_ids = [data.id_origin for data in data_list if data.id_origin]
            existing_langs = self._session.query(Lang.id_origin).filter(
                Lang.id_origin.in_(origin_ids)
            ).all()
            existing_origins = {l.id_origin for l in existing_langs}
            
            # Filter new languages
            new_langs_data = [data for data in data_list if data.id_origin not in existing_origins]
            
            if not new_langs_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_langs_data), batch_size):
                batch = new_langs_data[i:i + batch_size]
                langs = [Lang(**l.model_dump()) for l in batch]
                self._session.bulk_save_objects(langs)
                total_inserted += len(langs)
            
            self._session.commit()
            return total_inserted
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error bulk creating languages: {str(e)}")
    
    def get_all_for_init(self) -> List[dict]:
        """
        Query idratata: recupera solo id_lang, name, iso_code per tutte le lingue.
        Utilizzato per endpoint init.
        
        Returns:
            Lista di dict con id_lang, name, iso_code
        """
        try:
            from sqlalchemy import text
            result = self._session.execute(
                text("""
                    SELECT id_lang, name, iso_code 
                    FROM languages 
                    ORDER BY id_lang
                """)
            ).fetchall()
            return [
                {
                    "id_lang": row.id_lang,
                    "name": row.name,
                    "iso_code": row.iso_code
                }
                for row in result
            ]
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving languages for init: {str(e)}")
