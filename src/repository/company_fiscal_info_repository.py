"""
CompanyFiscalInfo Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from src.models.company_fiscal_info import CompanyFiscalInfo
from src.repository.interfaces.company_fiscal_info_repository_interface import ICompanyFiscalInfoRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException


class CompanyFiscalInfoRepository(BaseRepository[CompanyFiscalInfo, int], ICompanyFiscalInfoRepository):
    """CompanyFiscalInfo Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, CompanyFiscalInfo)
    
    def get_by_store_id(self, id_store: int) -> List[CompanyFiscalInfo]:
        """Ottiene tutte le informazioni fiscali per uno store"""
        try:
            return self._session.query(CompanyFiscalInfo).filter(
                CompanyFiscalInfo.id_store == id_store
            ).order_by(desc(CompanyFiscalInfo.is_default), desc(CompanyFiscalInfo.date_add)).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving company fiscal info by store: {str(e)}")
    
    def get_default_by_store_id(self, id_store: int) -> Optional[CompanyFiscalInfo]:
        """Ottiene l'informazione fiscale principale (is_default=True) per uno store"""
        try:
            return self._session.query(CompanyFiscalInfo).filter(
                CompanyFiscalInfo.id_store == id_store,
                CompanyFiscalInfo.is_default == True
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving default company fiscal info: {str(e)}")
    
    def get_by_vat_number(self, vat_number: str) -> Optional[CompanyFiscalInfo]:
        """Ottiene un'informazione fiscale per partita IVA"""
        try:
            return self._session.query(CompanyFiscalInfo).filter(
                CompanyFiscalInfo.vat_number == vat_number
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving company fiscal info by VAT number: {str(e)}")
