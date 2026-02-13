"""
Interface per la repository dei documenti fiscali
"""
from abc import abstractmethod
from typing import List, Optional, Dict, Any
from src.core.interfaces import IRepository
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail


class IFiscalDocumentRepository(IRepository[FiscalDocument, int]):
    """Interface per la repository dei documenti fiscali"""
    
    @abstractmethod
    def create_invoice(self, id_order: int, is_electronic: bool = True) -> FiscalDocument:
        """Crea una fattura per un ordine"""
        pass
    
    @abstractmethod
    def get_invoice_by_order(self, id_order: int) -> Optional[FiscalDocument]:
        """Ottiene la fattura per un ordine"""
        pass
    
    @abstractmethod
    def get_invoices_by_order(self, id_order: int) -> List[FiscalDocument]:
        """Ottiene tutte le fatture per un ordine"""
        pass
    
    @abstractmethod
    def create_credit_note(self, id_invoice: int, reason: str, is_partial: bool = False,
                          items: Optional[List[Dict[str, Any]]] = None, is_electronic: bool = True,
                          include_shipping: bool = True) -> FiscalDocument:
        """Crea una nota di credito per una fattura"""
        pass
    
    @abstractmethod
    def get_credit_notes_by_invoice(self, id_invoice: int) -> List[FiscalDocument]:
        """Ottiene tutte le note di credito per una fattura"""
        pass
    
    @abstractmethod
    def get_fiscal_document_by_id(self, id_fiscal_document: int) -> Optional[FiscalDocument]:
        """Ottiene un documento fiscale per ID"""
        pass
    
    @abstractmethod
    def delete_fiscal_document(self, id_fiscal_document: int) -> bool:
        """Elimina un documento fiscale"""
        pass
    
    @abstractmethod
    def update_fiscal_document_detail(self, id_detail: int, quantity: Optional[int] = None, unit_price: Optional[float] = None, id_tax: Optional[int] = None) -> FiscalDocumentDetail:
        """Aggiorna un dettaglio di documento fiscale"""
        pass
    
    @abstractmethod
    def delete_fiscal_document_detail(self, id_detail: int) -> bool:
        """Elimina un dettaglio di documento fiscale"""
        pass
    
    @abstractmethod
    def get_next_document_number(self, document_type: str) -> int:
        """Ottiene il prossimo numero sequenziale per un tipo di documento"""
        pass
    
    @abstractmethod
    def get_by_order_id(self, id_order: int, document_type: Optional[str] = None) -> List[FiscalDocument]:
        """Ottiene tutti i documenti fiscali per un ordine"""
        pass
    
    @abstractmethod
    def get_by_document_type(self, document_type: str, page: int = 1, limit: int = 10) -> List[FiscalDocument]:
        """Ottiene documenti per tipo"""
        pass
    
    @abstractmethod
    def get_document_count_by_type(self, document_type: str) -> int:
        """Conta i documenti per tipo"""
        pass
    
    @abstractmethod
    def create_return(self, id_order: int, order_details: List[dict], includes_shipping: bool = False, note: Optional[str] = None) -> FiscalDocument:
        """Crea un documento di reso"""
        pass
    
    @abstractmethod
    def get_items_returned_by_order(self, id_order: int) -> List[Dict[str, Any]]:
        """Recupera gli articoli già resi per un ordine (righe reso con id_product, product_reference, quantity_returned)"""
        pass
    
    @abstractmethod
    def calculate_return_totals(self, order_details: List[dict], includes_shipping: bool, id_order: int) -> float:
        """Calcola il totale di un reso"""
        pass
    
    @abstractmethod
    def recalculate_fiscal_document_total(self, id_fiscal_document: int) -> None:
        """Ricalcola il totale di un documento fiscale basato sui suoi dettagli"""
        pass
