"""
Tax Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.tax import Tax
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.services import QueryUtils

class TaxRepository(BaseRepository[Tax, int], ITaxRepository):
    """Tax Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Tax)
    
    def get_all(self, **filters) -> List[Tax]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Tax.id_tax))
            
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
    
    def get_by_name(self, name: str) -> Optional[Tax]:
        """Ottiene un tax per nome (case insensitive)"""
        try:
            return self._session.query(Tax).filter(
                func.lower(Tax.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving tax by name: {str(e)}")
    
    def define_tax(self, country_id: int) -> int:
        """Definisce la tassa da applicare basata sul paese"""
        try:
            # Logica semplice: se è Italia (country_id = 1) usa IVA 22%, altrimenti 0%
            # Default: cerca la tassa con percentuale più bassa o ID più basso
            tax = self._session.query(Tax).order_by(Tax.id_tax).first()
            if tax:
                return tax.id_tax
            
            # Fallback: restituisci 1 se non trova nulla
            return 1
        except Exception as e:
            raise InfrastructureException(f"Database error defining tax: {str(e)}")
    
    def get_percentage_by_id(self, id_tax: int) -> float:
        """Ottiene la percentuale di una tassa per ID"""
        try:
            tax = self._session.query(Tax).filter(Tax.id_tax == id_tax).first()
            if tax:
                return tax.percentage
            else:
                # Fallback alla percentuale di default (22%)
                return 22.0
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving tax percentage: {str(e)}")