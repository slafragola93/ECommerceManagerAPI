from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.company_fiscal_info import CompanyFiscalInfo


class ICompanyFiscalInfoRepository(IRepository[CompanyFiscalInfo, int]):
    """Interface per la repository delle informazioni fiscali aziendali"""
    
    @abstractmethod
    def get_by_store_id(self, id_store: int) -> List[CompanyFiscalInfo]:
        """Ottiene tutte le informazioni fiscali per uno store"""
        pass
    
    @abstractmethod
    def get_default_by_store_id(self, id_store: int) -> Optional[CompanyFiscalInfo]:
        """Ottiene l'informazione fiscale principale (is_default=True) per uno store"""
        pass
    
    @abstractmethod
    def get_by_vat_number(self, vat_number: str) -> Optional[CompanyFiscalInfo]:
        """Ottiene un'informazione fiscale per partita IVA"""
        pass
