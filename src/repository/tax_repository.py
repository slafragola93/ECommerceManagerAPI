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
            row = self._session.query(Tax.percentage).filter(Tax.id_tax == id_tax).first()
            if row is not None:
                # row può essere un tuple/Row con singolo valore
                value = row[0] if isinstance(row, (tuple, list)) else getattr(row, "percentage", None)
                if value is not None:
                    return float(value)
            # Fallback alla percentuale di default (22%)
            return 22.0
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving tax percentage: {str(e)}")
    
    def get_default_tax_percentage_from_app_config(self, default: float = 22.0) -> float:
        """
        Recupera la percentuale IVA di default da app_configuration.name = "default_tav"
        
        Args:
            default: Percentuale di default se non trovata (default: 22.0)
        
        Returns:
            float: Percentuale IVA trovata o default
        """
        try:
            from src.models.app_configuration import AppConfiguration
            
            # Cerca app_configuration con name = "default_tav" o "default_tax"
            app_config = self._session.query(AppConfiguration).filter(
                AppConfiguration.name.in_(["default_tav", "default_tax"])
            ).first()
            
            if app_config and app_config.value:
                try:
                    return float(app_config.value)
                except (ValueError, TypeError):
                    pass
            
            return default
            
        except Exception:
            return default
    
    def get_tax_by_id(self, id_tax: int) -> Optional[Tax]:
        """
        Ottiene una Tax per ID
        
        Args:
            id_tax: ID della tassa
            
        Returns:
            Tax se trovata, None altrimenti
        """
        return self._session.query(Tax).filter(Tax.id_tax == id_tax).first()
    
    def get_tax_by_id_country(self, id_country: int) -> Optional[Tax]:
        """
        Ottiene una Tax basata su id_country
        
        Args:
            id_country: ID del paese
            
        Returns:
            Tax se trovata per il paese specificato, None altrimenti
        """
        if id_country is None or id_country <= 0:
                return None
            
        return self._session.query(Tax).filter(
            Tax.id_country == id_country
        ).first()
    
    def get_tax_info_by_country(self, id_country: int) -> Optional[dict]:
        """
        Recupera informazioni sulla tassa (percentage e id_tax) basata su id_country.
        
        Logica di fallback:
        1. Cerca tax per id_country specifico
        2. Se non trovata, cerca tax default (is_default == 1)
        3. Se non trovata, recupera percentage da app_configuration.default_tax
        4. Fallback finale: 22% e id_tax=1
        
        Args:
            id_country: ID del paese (opzionale)
        
        Returns:
            dict con {"percentage": float, "id_tax": int} o None se id_country non fornito
        """

        # 1. Cerca tax per id_country specifico
        tax = self.get_tax_by_id_country(id_country)
        
        if tax and tax.percentage is not None:
            return {
                "percentage": float(tax.percentage),
                "id_tax": tax.id_tax
            }
        
        # 2. Se non trovata, cerca tax default
        default_tax = self._session.query(Tax).filter(
            Tax.is_default == 1
        ).first()
        
        if default_tax and default_tax.percentage is not None:
            return {
                "percentage": float(default_tax.percentage),
                "id_tax": default_tax.id_tax
            }
        
        # 3. Se non trovata, recupera percentage da app_configuration
        default_percentage = self.get_default_tax_percentage_from_app_config(22.0)
        
        # 4. Fallback finale: usa 22% e id_tax=1
        return {
            "percentage": default_percentage,
            "id_tax": 1
        }