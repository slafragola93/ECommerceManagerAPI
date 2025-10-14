from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from src.repository.preventivo_repository import PreventivoRepository
from src.repository.customer_repository import CustomerRepository
from src.repository.tax_repository import TaxRepository
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema,
    PreventivoUpdateSchema,
    PreventivoResponseSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema
)
from src.models.customer import Customer
from src.models.tax import Tax


class PreventivoService:
    """Servizio per gestione preventivi"""
    
    def __init__(self, db: Session):
        self.db = db
        self.preventivo_repo = PreventivoRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.tax_repo = TaxRepository(db)
    
    def create_preventivo(self, preventivo_data: PreventivoCreateSchema, user_id: int) -> PreventivoResponseSchema:
        """Crea nuovo preventivo"""
        # Valida articoli
        self._validate_articoli(preventivo_data.articoli)
        
        # Crea preventivo (il repository gestisce customer e address)
        order_document = self.preventivo_repo.create_preventivo(preventivo_data, user_id)
        
        # Recupera customer per nome
        customer = self.customer_repo.get_by_id(order_document.id_customer)
        customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
        
        # Calcola totali
        totals = self.preventivo_repo.calculate_totals(order_document.id_order_document)
        
        # Recupera articoli
        articoli = self.preventivo_repo.get_articoli_preventivo(order_document.id_order_document)
        articoli_data = [self._format_articolo(articolo) for articolo in articoli]
        
        return PreventivoResponseSchema(
            id_order_document=order_document.id_order_document,
            document_number=order_document.document_number,
            id_customer=order_document.id_customer,
            customer_name=customer_name,
            reference=None,  # OrderDocument non ha campo reference
            note=order_document.note,
            status=None,  # OrderDocument non ha campo status
            type_document=order_document.type_document,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=totals["total_finale"],
            date_add=order_document.date_add,
            updated_at=order_document.updated_at,
            articoli=articoli_data
        )
    
    def get_preventivo(self, id_order_document: int) -> Optional[PreventivoResponseSchema]:
        """Recupera preventivo per ID"""
        order_document = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if not order_document:
            return None
        
        # Recupera cliente
        customer = self.customer_repo.get_by_id(order_document.id_customer)
        customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
        
        # Calcola totali
        totals = self.preventivo_repo.calculate_totals(id_order_document)
        
        # Recupera articoli
        articoli = self.preventivo_repo.get_articoli_preventivo(id_order_document)
        articoli_data = [self._format_articolo(articolo) for articolo in articoli]
        
        return PreventivoResponseSchema(
            id_order_document=order_document.id_order_document,
            document_number=order_document.document_number,
            id_customer=order_document.id_customer,
            customer_name=customer_name,
            note=order_document.note,
            type_document=order_document.type_document,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=totals["total_finale"],
            date_add=order_document.date_add,
            updated_at=order_document.updated_at,
            articoli=articoli_data
        )
    
    def get_preventivi(self, skip: int = 0, limit: int = 100, search: Optional[str] = None, show_details: bool = False) -> List[PreventivoResponseSchema]:
        """Recupera lista preventivi"""
        order_documents = self.preventivo_repo.get_preventivi(skip, limit, search)
        
        result = []
        for order_document in order_documents:
            # Recupera cliente
            customer = self.customer_repo.get_by_id(order_document.id_customer)
            customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
            
            # Calcola totali
            totals = self.preventivo_repo.calculate_totals(order_document.id_order_document)
            
            # Recupera articoli solo se show_details è True
            articoli_data = []
            if show_details:
                articoli = self.preventivo_repo.get_articoli_preventivo(order_document.id_order_document)
                articoli_data = [self._format_articolo(articolo) for articolo in articoli]
            result.append(PreventivoResponseSchema(
                id_order_document=order_document.id_order_document,
                document_number=order_document.document_number,
                id_customer=order_document.id_customer,
                customer_name=customer_name,
                reference=None,  # OrderDocument non ha campo reference
                note=order_document.note,
                status=None,  # OrderDocument non ha campo status
                type_document=order_document.type_document,
                total_imponibile=totals["total_imponibile"],
                total_iva=totals["total_iva"],
                total_finale=totals["total_finale"],
                date_add=order_document.date_add,
                updated_at=order_document.updated_at,
                articoli=articoli_data
            ))
        
        return result
    
    def update_preventivo(self, id_order_document: int, preventivo_data: PreventivoUpdateSchema, user_id: int) -> Optional[PreventivoResponseSchema]:
        """Aggiorna preventivo"""
        order_document = self.preventivo_repo.update_preventivo(id_order_document, preventivo_data, user_id)
        if not order_document:
            return None
        
        return self.get_preventivo(id_order_document)
    
    def add_articolo(self, id_order_document: int, articolo: ArticoloPreventivoSchema) -> Optional[ArticoloPreventivoSchema]:
        """Aggiunge articolo a preventivo"""
        # Valida articolo
        self._validate_single_articolo(articolo)
        
        order_detail = self.preventivo_repo.add_articolo(id_order_document, articolo)
        if not order_detail:
            return None
        
        return self._format_articolo(order_detail)
    
    def update_articolo(self, id_order_detail: int, articolo_data: ArticoloPreventivoUpdateSchema) -> Optional[ArticoloPreventivoSchema]:
        """Aggiorna articolo in preventivo"""
        # Valida articolo se necessario
        if articolo_data.id_tax is not None:
            tax = self.tax_repo.get_by_id(articolo_data.id_tax)
            if not tax:
                raise ValueError(f"Tassa con ID {articolo_data.id_tax} non trovata")
        
        order_detail = self.preventivo_repo.update_articolo(id_order_detail, articolo_data)
        if not order_detail:
            return None
        
        return self._format_articolo(order_detail)
    
    def remove_articolo(self, id_order_detail: int) -> bool:
        """Rimuove articolo da preventivo"""
        return self.preventivo_repo.remove_articolo(id_order_detail)
    
    def convert_to_order(self, id_order_document: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Converte preventivo in ordine"""
        # Verifica che il preventivo esista
        preventivo = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if not preventivo:
            raise ValueError("Preventivo non trovato")
        
        # Controlla se esiste già un ordine collegato a questo preventivo
        existing_order = self.preventivo_repo.check_if_already_converted(id_order_document)
        if existing_order:
            raise ValueError(f"Preventivo già convertito in ordine ID {existing_order.id_order}")
        
        # Converte in ordine
        order = self.preventivo_repo.convert_to_order(id_order_document, user_id)
        if not order:
            raise ValueError("Errore durante la conversione")
        
        return {
            "id_order": order.id_order,
            "id_order_document": id_order_document,
            "message": "Preventivo convertito in ordine con successo"
        }
    
    def get_totals(self, id_order_document: int) -> Dict[str, float]:
        """Recupera totali calcolati del preventivo"""
        return self.preventivo_repo.calculate_totals(id_order_document)
    
    def _validate_articoli(self, articoli: List[ArticoloPreventivoSchema]) -> None:
        """Valida lista articoli"""
        for articolo in articoli:
            self._validate_single_articolo(articolo)
    
    def _validate_single_articolo(self, articolo: ArticoloPreventivoSchema) -> None:
        """Valida singolo articolo"""
        # Verifica che la tassa esista
        tax = self.tax_repo.get_by_id(articolo.id_tax)
        if not tax:
            raise ValueError(f"Tassa con ID {articolo.id_tax} non trovata")
        
        # Se è un prodotto esistente, verifica che esista
        if articolo.id_product is not None:
            # Qui potresti aggiungere validazione per prodotti esistenti
            pass
    
    def _format_articolo(self, order_detail) -> ArticoloPreventivoSchema:
        """Formatta articolo per risposta"""
        return ArticoloPreventivoSchema(
            id_product=order_detail.id_product,
            product_name=order_detail.product_name,
            product_reference=order_detail.product_reference,
            product_price=order_detail.product_price,
            product_qty=order_detail.product_qty,
            product_weight=order_detail.product_weight,
            id_tax=order_detail.id_tax,
            reduction_percent=order_detail.reduction_percent,
            reduction_amount=order_detail.reduction_amount,
            rda=order_detail.rda
        )
    
    def delete_preventivo(self, id_order_document: int) -> bool:
        """
        Elimina un preventivo
        
        Args:
            id_order_document: ID del preventivo da eliminare
            
        Returns:
            bool: True se eliminato con successo, False se non trovato
        """
        return self.preventivo_repo.delete_preventivo(id_order_document)
    
    def duplicate_preventivo(self, id_order_document: int, user_id: int) -> Optional[PreventivoResponseSchema]:
        """
        Duplica un preventivo esistente
        
        Args:
            id_order_document: ID del preventivo da duplicare
            user_id: ID dell'utente che esegue la duplicazione
            
        Returns:
            PreventivoResponseSchema: Il nuovo preventivo duplicato, None se il preventivo originale non esiste
        """
        # Verifica che il preventivo originale esista
        original_preventivo = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if not original_preventivo:
            return None
        
        # Duplica il preventivo
        new_preventivo = self.preventivo_repo.duplicate_preventivo(id_order_document, user_id)
        if not new_preventivo:
            return None
        
        # Restituisce il preventivo duplicato usando la logica esistente
        return self.get_preventivo(new_preventivo.id_order_document)