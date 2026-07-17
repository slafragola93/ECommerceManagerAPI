"""
Tax Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from src.models.tax import Tax
from src.models.country import Country
from src.models.order_detail import OrderDetail
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.repository.tax_usages import TaxUsages
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException, NotFoundException
from src.services import QueryUtils
from src.vies.vies_app_configuration import get_reverse_charge_id_tax

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
        """Definisce id_tax da applicare in base al paese di consegna (default paese → globale)."""
        try:
            info = self.get_tax_info_by_country(country_id)
            if info:
                return int(info["id_tax"])
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
        
        # 2. Default per paese (is_default=1 sullo stesso id_country)
        country_default = self.get_default_by_country(id_country)
        if country_default and country_default.percentage is not None:
            return {
                "percentage": float(country_default.percentage),
                "id_tax": country_default.id_tax,
            }

        # 3. Fallback globale (id_country IS NULL, is_default=1)
        global_default = self.get_global_default()
        if global_default and global_default.percentage is not None:
            return {
                "percentage": float(global_default.percentage),
                "id_tax": global_default.id_tax,
            }
        
        # 4. Percentuale da app_configuration
        default_percentage = self.get_default_tax_percentage_from_app_config(22.0)

        # 5. Fallback finale: usa 22% e id_tax=1
        return {
            "percentage": default_percentage,
            "id_tax": 1
        }

    def get_default_by_country(self, id_country: int) -> Optional[Tax]:
        """Restituisce il Tax con is_default=1 per il paese."""
        if id_country is None or id_country <= 0:
            return None
        try:
            return (
                self._session.query(Tax)
                .filter(Tax.id_country == id_country, Tax.is_default == 1)
                .first()
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving default tax for country {id_country}: {str(e)}"
            )

    def get_default_by_country_iso(self, iso_code: str) -> Optional[Tax]:
        """Restituisce il Tax default per codice ISO paese."""
        if not iso_code or not str(iso_code).strip():
            return None
        try:
            normalized = str(iso_code).strip().upper()
            return (
                self._session.query(Tax)
                .join(Country, Tax.id_country == Country.id_country)
                .filter(
                    func.upper(Country.iso_code) == normalized,
                    Tax.is_default == 1,
                )
                .first()
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving default tax for ISO {iso_code}: {str(e)}"
            )

    def list_country_defaults(self) -> List[Tax]:
        """Tutti i Tax con is_default=1 e id_country valorizzato."""
        try:
            return (
                self._session.query(Tax)
                .options(joinedload(Tax.country))
                .filter(Tax.is_default == 1, Tax.id_country.isnot(None))
                .order_by(Tax.id_country, Tax.id_tax)
                .all()
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error listing country default taxes: {str(e)}"
            )

    def get_global_default(self) -> Optional[Tax]:
        """Tax con id_country IS NULL e is_default=1 (fallback globale)."""
        try:
            return (
                self._session.query(Tax)
                .filter(Tax.id_country.is_(None), Tax.is_default == 1)
                .first()
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving global default tax: {str(e)}"
            )

    def set_country_default_atomic(self, id_tax: int, id_country: int) -> Tax:
        """Imposta un Tax come unico default per il paese (transazione atomica)."""
        try:
            tax = self.get_tax_by_id(id_tax)
            if not tax:
                raise NotFoundException("Tax", id_tax)

            self._session.query(Tax).filter(
                Tax.id_country == id_country,
                Tax.id_tax != id_tax,
            ).update({Tax.is_default: 0}, synchronize_session=False)

            tax.is_default = 1
            if tax.id_country is None:
                tax.id_country = id_country

            self._session.commit()
            self._session.refresh(tax)
            return tax
        except NotFoundException:
            raise
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(
                f"Database error setting country default tax: {str(e)}"
            )

    def set_global_default_atomic(self, id_tax: int) -> Tax:
        """Imposta un Tax come unico default globale (id_country IS NULL)."""
        try:
            tax = self.get_tax_by_id(id_tax)
            if not tax:
                raise NotFoundException("Tax", id_tax)

            self._session.query(Tax).filter(
                Tax.id_country.is_(None),
                Tax.is_default == 1,
                Tax.id_tax != id_tax,
            ).update({Tax.is_default: 0}, synchronize_session=False)

            tax.id_country = None
            tax.is_default = 1
            self._session.commit()
            self._session.refresh(tax)
            return tax
        except NotFoundException:
            raise
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(
                f"Database error setting global default tax: {str(e)}"
            )

    def find_usages(self, id_tax: int) -> TaxUsages:
        """Conta riferimenti a id_tax su order_details, fiscal_document_details e reverse charge."""
        try:
            order_count = (
                self._session.query(func.count())
                .select_from(OrderDetail)
                .filter(OrderDetail.id_tax == id_tax)
                .scalar()
            ) or 0
            document_count = (
                self._session.query(func.count())
                .select_from(FiscalDocumentDetail)
                .filter(FiscalDocumentDetail.id_tax == id_tax)
                .scalar()
            ) or 0
            reverse_charge_id = get_reverse_charge_id_tax(self._session)
            return TaxUsages(
                order_count=int(order_count),
                document_count=int(document_count),
                is_reverse_charge=reverse_charge_id == id_tax,
            )
        except Exception as e:
            raise InfrastructureException(
                f"Database error checking tax usages for id {id_tax}: {str(e)}"
            )