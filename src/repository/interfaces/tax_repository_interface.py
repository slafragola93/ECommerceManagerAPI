"""
Interfaccia per Tax Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.tax import Tax
from src.repository.tax_usages import TaxUsages

class ITaxRepository(IRepository[Tax, int]):
    """Interface per la repository dei tax"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Tax]:
        """Ottiene un tax per nome"""
        pass
    
    @abstractmethod
    def define_tax(self, country_id: int) -> int:
        """Definisce la tassa da applicare basata sul paese"""
        pass
    
    @abstractmethod
    def get_percentage_by_id(self, id_tax: int) -> float:
        """Ottiene la percentuale di una tassa per ID"""
        pass
    
    @abstractmethod
    def get_tax_by_id(self, id_tax: int) -> Optional[Tax]:
        """Ottiene una Tax per ID"""
        pass
    
    @abstractmethod
    def get_tax_by_id_country(self, id_country: int) -> Optional[Tax]:
        """Ottiene una Tax basata su id_country"""
        pass

    @abstractmethod
    def get_default_by_country(self, id_country: int) -> Optional[Tax]:
        """Restituisce il Tax con is_default=1 per il paese. None se non esiste."""
        pass

    @abstractmethod
    def get_default_by_country_iso(self, iso_code: str) -> Optional[Tax]:
        """Restituisce il Tax default per ISO 3166-1 alpha-2."""
        pass

    @abstractmethod
    def list_country_defaults(self) -> List[Tax]:
        """Tutti i Tax con is_default=1 e id_country valorizzato."""
        pass

    @abstractmethod
    def get_global_default(self) -> Optional[Tax]:
        """Tax fallback globale (id_country IS NULL, is_default=1)."""
        pass

    @abstractmethod
    def set_country_default_atomic(self, id_tax: int, id_country: int) -> Tax:
        """Imposta un Tax come unico default per il paese (transazione atomica)."""
        pass

    @abstractmethod
    def set_global_default_atomic(self, id_tax: int) -> Tax:
        """Imposta un Tax come unico default globale (id_country IS NULL)."""
        pass

    @abstractmethod
    def find_usages(self, id_tax: int) -> TaxUsages:
        """Conta riferimenti a id_tax su ordini, documenti fiscali e reverse charge."""
        pass