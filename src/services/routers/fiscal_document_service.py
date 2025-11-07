"""
Servizio centralizzato per la gestione dei documenti fiscali
"""
from typing import List, Optional
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.repository.interfaces.fiscal_document_repository_interface import IFiscalDocumentRepository
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.schemas.return_schema import ReturnCreateSchema, ReturnUpdateSchema, ReturnDetailUpdateSchema
from src.core.exceptions import ValidationException, NotFoundException, BusinessRuleException
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import (
    extract_invoice_created_data,
    extract_credit_note_created_data
)


class FiscalDocumentService(IFiscalDocumentService):
    """Servizio centralizzato per la gestione dei documenti fiscali"""
    
    def __init__(self, fiscal_document_repository: IFiscalDocumentRepository):
        self._fiscal_document_repository = fiscal_document_repository
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_CREATED,
        data_extractor=extract_invoice_created_data,
        source="fiscal_document_service.create_invoice"
    )
    async def create_invoice(self, id_order: int, is_electronic: bool = True, user: dict = None) -> FiscalDocument:
        """
        Crea una fattura per un ordine.
        
        Args:
            id_order: ID dell'ordine per cui creare la fattura
            is_electronic: Se True, genera fattura elettronica
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            FiscalDocument (fattura) creata
        """
        try:
            return self._fiscal_document_repository.create_invoice(id_order, is_electronic)
        except Exception as e:
            raise ValidationException(f"Errore nella creazione della fattura: {str(e)}")
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_CREATED,
        data_extractor=extract_credit_note_created_data,
        source="fiscal_document_service.create_credit_note"
    )
    async def create_credit_note(self, id_invoice: int, reason: str, is_partial: bool = False, 
                               items: Optional[List[dict]] = None, is_electronic: bool = True, 
                               include_shipping: bool = True, user: dict = None) -> FiscalDocument:
        """
        Crea una nota di credito per una fattura.
        
        Args:
            id_invoice: ID della fattura di riferimento
            reason: Motivo della nota di credito
            is_partial: Se True, nota parziale
            items: Lista articoli da includere (per note parziali)
            is_electronic: Se True, genera nota elettronica
            include_shipping: Se True, include spese di spedizione
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            FiscalDocument (nota di credito) creata
        """
        try:
            return self._fiscal_document_repository.create_credit_note(
                id_invoice, reason, is_partial, items, is_electronic, include_shipping
            )
        except Exception as e:
            raise ValidationException(f"Errore nella creazione della nota di credito: {str(e)}")
    
    async def create_return(self, id_order: int, return_data: ReturnCreateSchema) -> FiscalDocument:
        """Crea un reso per un ordine"""
        try:
            # Converte i dati dello schema in formato dict
            order_details = []
            for item in return_data.order_details:
                order_details.append({
                    'id_order_detail': item.id_order_detail,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'id_tax': item.id_tax
                })
            
            return self._fiscal_document_repository.create_return(
                id_order,
                order_details,
                return_data.includes_shipping,
                return_data.note
            )
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del reso: {str(e)}")
    
    async def update_fiscal_document(self, id_fiscal_document: int, update_data: ReturnUpdateSchema) -> FiscalDocument:
        """Aggiorna un documento fiscale"""
        try:
            # Recupera il documento esistente
            fiscal_doc = self._fiscal_document_repository.get_by_id(id_fiscal_document)
            if not fiscal_doc:
                raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
            
            # Aggiorna i campi se forniti
            if update_data.includes_shipping is not None:
                fiscal_doc.includes_shipping = update_data.includes_shipping
            
            if update_data.note is not None:
                fiscal_doc.credit_note_reason = update_data.note
            
            if update_data.status is not None:
                if update_data.status not in ['pending', 'processed', 'cancelled']:
                    raise ValidationException("Status non valido. Valori ammessi: pending, processed, cancelled")
                fiscal_doc.status = update_data.status
            
            # Ricalcola il totale se necessario
            if update_data.includes_shipping is not None:
                self._fiscal_document_repository.recalculate_fiscal_document_total(id_fiscal_document)
            
            return self._fiscal_document_repository.update(fiscal_doc)
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del documento fiscale: {str(e)}")
    
    async def delete_fiscal_document(self, id_fiscal_document: int) -> bool:
        """Elimina un documento fiscale"""
        try:
            # Verifica che il documento esista
            fiscal_doc = self._fiscal_document_repository.get_by_id(id_fiscal_document)
            if not fiscal_doc:
                raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
            
            # Solo i documenti in stato 'pending' possono essere eliminati, eccetto i resi
            if fiscal_doc.status != 'pending' and fiscal_doc.document_type != 'return':
                raise BusinessRuleException("Solo i documenti in stato 'pending' possono essere eliminati (eccetto i resi)")
            
            return self._fiscal_document_repository.delete_fiscal_document(id_fiscal_document)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del documento fiscale: {str(e)}")
    
    async def update_fiscal_document_detail(self, id_detail: int, update_data: ReturnDetailUpdateSchema) -> FiscalDocumentDetail:
        """Aggiorna un dettaglio di documento fiscale"""
        try:
            return self._fiscal_document_repository.update_fiscal_document_detail(
                id_detail,
                update_data.quantity,
                update_data.unit_price,
                update_data.id_tax
            )
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del dettaglio: {str(e)}")
    
    async def delete_fiscal_document_detail(self, id_detail: int) -> bool:
        """Elimina un dettaglio di documento fiscale"""
        try:
            return self._fiscal_document_repository.delete_fiscal_document_detail(id_detail)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del dettaglio: {str(e)}")
    
    async def get_fiscal_documents_by_order(self, id_order: int, document_type: Optional[str] = None) -> List[FiscalDocument]:
        """Ottiene i documenti fiscali per un ordine"""
        try:
            return self._fiscal_document_repository.get_by_order_id(id_order, document_type)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei documenti fiscali: {str(e)}")
    
    async def get_fiscal_documents_by_type(self, document_type: str, page: int = 1, limit: int = 10) -> List[FiscalDocument]:
        """Ottiene i documenti fiscali per tipo"""
        try:
            return self._fiscal_document_repository.get_by_document_type(document_type, page, limit)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei documenti fiscali per tipo: {str(e)}")
    
    async def get_fiscal_document_count_by_type(self, document_type: str) -> int:
        """Conta i documenti fiscali per tipo"""
        try:
            return self._fiscal_document_repository.get_document_count_by_type(document_type)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei documenti fiscali: {str(e)}")
    
    # Metodi di utilità per la numerazione sequenziale
    async def get_next_document_number(self, document_type: str) -> int:
        """Ottiene il prossimo numero sequenziale per un tipo di documento"""
        try:
            return self._fiscal_document_repository.get_next_document_number(document_type)
        except Exception as e:
            raise ValidationException(f"Errore nella generazione del numero sequenziale: {str(e)}")
    
    # Metodi per validazione
    async def validate_return_items(self, id_order: int, return_items: List[dict]) -> None:
        """Valida gli articoli per un reso"""
        try:
            self._fiscal_document_repository.validate_return_items(id_order, return_items)
        except Exception as e:
            raise ValidationException(f"Errore nella validazione degli articoli: {str(e)}")
    
    async def get_returned_quantities(self, id_order: int) -> dict:
        """Ottiene le quantità già restituite per ogni order_detail"""
        try:
            return self._fiscal_document_repository.get_returned_quantities(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero delle quantità restituite: {str(e)}")
    
    # ==================== METODI CENTRALIZZATI PER FATTURE E NOTE DI CREDITO ====================
    
    async def get_next_electronic_number(self, doc_type: str) -> str:
        """Ottiene il prossimo numero sequenziale elettronico per un tipo di documento"""
        try:
            return self._fiscal_document_repository._get_next_electronic_number(doc_type)
        except Exception as e:
            raise ValidationException(f"Errore nella generazione del numero elettronico: {str(e)}")
    
    async def get_invoice_by_order(self, id_order: int):
        """Recupera la prima fattura di un ordine (deprecato, usare get_invoices_by_order)"""
        try:
            return self._fiscal_document_repository.get_invoice_by_order(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero della fattura: {str(e)}")
    
    async def get_invoices_by_order(self, id_order: int):
        """Recupera tutte le fatture di un ordine"""
        try:
            return self._fiscal_document_repository.get_invoices_by_order(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero delle fatture: {str(e)}")
    
    async def get_credit_notes_by_invoice(self, id_invoice: int):
        """Recupera tutte le note di credito di una fattura"""
        try:
            return self._fiscal_document_repository.get_credit_notes_by_invoice(id_invoice)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero delle note di credito: {str(e)}")
    
    async def get_fiscal_document_by_id(self, id_fiscal_document: int):
        """Recupera documento fiscale per ID"""
        try:
            return self._fiscal_document_repository.get_fiscal_document_by_id(id_fiscal_document)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero del documento fiscale: {str(e)}")
    
    async def get_fiscal_documents(self, skip: int = 0, limit: int = 100, 
                                 document_type: Optional[str] = None,
                                 is_electronic: Optional[bool] = None,
                                 status: Optional[str] = None):
        """Recupera lista documenti fiscali con filtri"""
        try:
            return self._fiscal_document_repository.get_fiscal_documents(skip, limit, document_type, is_electronic, status)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei documenti fiscali: {str(e)}")
    
    async def update_fiscal_document_status(self, id_fiscal_document: int, status: str, upload_result: Optional[str] = None):
        """Aggiorna status di un documento fiscale"""
        try:
            return self._fiscal_document_repository.update_fiscal_document_status(id_fiscal_document, status, upload_result)
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dello status: {str(e)}")
    
    async def update_fiscal_document_xml(self, id_fiscal_document: int, filename: str, xml_content: str):
        """Aggiorna XML di un documento fiscale"""
        try:
            return self._fiscal_document_repository.update_fiscal_document_xml(id_fiscal_document, filename, xml_content)
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dell'XML: {str(e)}")
    
    async def delete_fiscal_document_legacy(self, id_fiscal_document: int) -> bool:
        """Elimina documento fiscale (versione legacy per compatibilità)"""
        try:
            return self._fiscal_document_repository.delete_fiscal_document(id_fiscal_document)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del documento fiscale: {str(e)}")
    
    async def validate_business_rules(self, entity_data: dict) -> None:
        """Valida le regole di business per i documenti fiscali"""
        # Implementazione delle regole di business specifiche per i documenti fiscali
        # Per ora, implementazione vuota - può essere estesa in futuro
        pass
