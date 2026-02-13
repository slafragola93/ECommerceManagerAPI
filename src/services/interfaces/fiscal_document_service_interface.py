"""
Interface per il servizio dei documenti fiscali
"""
from abc import abstractmethod
from typing import List, Optional
from src.core.interfaces import IBaseService
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.schemas.return_schema import ReturnCreateSchema, ReturnUpdateSchema, ReturnDetailUpdateSchema


class IFiscalDocumentService(IBaseService):
    """Interface per il servizio dei documenti fiscali"""
    
    @abstractmethod
    async def create_invoice(self, id_order: int, is_electronic: bool = True) -> FiscalDocument:
        """Crea una fattura per un ordine"""
        pass
    
    @abstractmethod
    async def create_credit_note(self, id_invoice: int, reason: str, is_partial: bool = False, 
                               items: Optional[List[dict]] = None, is_electronic: bool = True, 
                               include_shipping: bool = True) -> FiscalDocument:
        """Crea una nota di credito per una fattura"""
        pass

    @abstractmethod
    async def validate_return_items(self, items_to_return: List[dict], items_already_returned: List[dict]) -> dict:
        """Valida gli articoli per un reso"""
        pass
    
    @abstractmethod
    async def create_return(self, id_order: int, return_data: ReturnCreateSchema) -> FiscalDocument:
        """Crea un reso per un ordine"""
        pass
    
    @abstractmethod
    async def update_fiscal_document(self, id_fiscal_document: int, update_data: ReturnUpdateSchema) -> FiscalDocument:
        """Aggiorna un documento fiscale"""
        pass
    
    @abstractmethod
    async def delete_fiscal_document(self, id_fiscal_document: int) -> bool:
        """Elimina un documento fiscale"""
        pass
    
    @abstractmethod
    async def update_fiscal_document_detail(self, id_detail: int, update_data: ReturnDetailUpdateSchema) -> FiscalDocumentDetail:
        """Aggiorna un dettaglio di documento fiscale"""
        pass
    
    @abstractmethod
    async def delete_fiscal_document_detail(self, id_detail: int) -> bool:
        """Elimina un dettaglio di documento fiscale"""
        pass
    
    @abstractmethod
    async def get_fiscal_documents_by_order(self, id_order: int, document_type: Optional[str] = None) -> List[FiscalDocument]:
        """Ottiene i documenti fiscali per un ordine"""
        pass
    
    @abstractmethod
    async def get_fiscal_documents_by_type(self, document_type: str, page: int = 1, limit: int = 10) -> List[FiscalDocument]:
        """Ottiene i documenti fiscali per tipo"""
        pass
    
    @abstractmethod
    async def get_fiscal_document_count_by_type(self, document_type: str) -> int:
        """Conta i documenti fiscali per tipo"""
        pass
