from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from src.models.order_document import OrderDocument
from src.models.order_detail import OrderDetail
from src.models.order import Order
from src.models.customer import Customer
from src.models.address import Address
from src.models.shipping import Shipping
from src.models.sectional import Sectional
from src.models.tax import Tax
from src.models.order_package import OrderPackage
from src.services.order_document_service import OrderDocumentService


class DDTRepository:
    """Repository per la gestione dei DDT (Documenti di Trasporto)"""
    
    def __init__(self, db: Session):
        self.db = db
        self.order_doc_service = OrderDocumentService(db)
    
    def create_ddt_from_order(self, id_order: int, user_id: int) -> Optional[OrderDocument]:
        """
        Crea un DDT a partire da un ordine
        
        Args:
            id_order: ID dell'ordine da cui creare il DDT
            user_id: ID dell'utente che crea il DDT
            
        Returns:
            OrderDocument: Il nuovo DDT creato, None se l'ordine non esiste
        """
        # Verifica che il DDT sia modificabile
        if not self.order_doc_service.is_ddt_modifiable(id_order):
            raise ValueError("Impossibile creare DDT: l'ordine è già stato fatturato o spedito")
        
        # Recupera l'ordine originale
        original_order = self.db.query(Order).filter(Order.id_order == id_order).first()
        if not original_order:
            return None
        
        # Genera nuovo numero documento DDT
        new_document_number = self.order_doc_service.get_next_document_number("DDT")
        
        # Crea nuovo OrderDocument (DDT) copiando i dati dell'ordine
        new_ddt = OrderDocument(
            type_document="DDT",
            document_number=new_document_number,
            id_customer=original_order.id_customer,
            id_address_delivery=original_order.id_address_delivery,
            id_address_invoice=original_order.id_address_invoice,
            id_sectional=original_order.id_sectional,
            id_tax=None,
            id_shipping=original_order.id_shipping,
            is_invoice_requested=original_order.is_invoice_requested,
            note=f"DDT generato da ordine {original_order.reference}",
            total_weight=original_order.total_weight,
            total_price_with_tax=original_order.total_paid,  # Usa total_paid invece di total_price_tax_excl
            id_order=id_order,  # Collegamento all'ordine originale
            date_add=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.db.add(new_ddt)
        self.db.flush()  # Per ottenere l'ID
        
        # Copia tutti gli OrderDetail dell'ordine collegandoli al DDT
        original_details = self.db.query(OrderDetail).filter(
            OrderDetail.id_order == id_order
        ).all()
        
        for detail in original_details:
            new_detail = OrderDetail(
                id_origin=0,
                id_order=0,  # Per distinguere dalle righe ordine
                id_order_document=new_ddt.id_order_document,
                id_product=detail.id_product,
                product_name=detail.product_name,
                product_reference=detail.product_reference,
                product_qty=detail.product_qty,
                product_weight=detail.product_weight,
                product_price=detail.product_price,
                id_tax=detail.id_tax,
                reduction_percent=detail.reduction_percent,
                reduction_amount=detail.reduction_amount
            )
            self.db.add(new_detail)
        
        self.db.commit()
        return new_ddt
    
    def get_ddt_by_id(self, id_order_document: int) -> Optional[OrderDocument]:
        """Recupera DDT per ID"""
        return self.db.query(OrderDocument).filter(
            and_(
                OrderDocument.id_order_document == id_order_document,
                OrderDocument.type_document == "DDT"
            )
        ).first()
    
    def get_ddt_with_details(self, id_order_document: int) -> Optional[OrderDocument]:
        """Recupera DDT con tutti i dettagli e relazioni"""
        ddt = self.get_ddt_by_id(id_order_document)
        if not ddt:
            return None
        
        # Carica le relazioni
        self.db.refresh(ddt)
        return ddt
    
    def get_ddt_details(self, id_order_document: int) -> List[OrderDetail]:
        """Recupera i dettagli (articoli) di un DDT"""
        return self.db.query(OrderDetail).filter(
            and_(
                OrderDetail.id_order_document == id_order_document,
                OrderDetail.id_order == 0  # Solo righe DDT, non ordine
            )
        ).all()
    
    def get_ddt_packages(self, id_order: int) -> List[OrderPackage]:
        """Recupera i pacchi collegati all'ordine del DDT"""
        return self.db.query(OrderPackage).filter(
            OrderPackage.id_order == id_order
        ).all()
    
    def is_ddt_modifiable(self, id_order_document: int) -> bool:
        """Verifica se un DDT può essere modificato"""
        ddt = self.get_ddt_by_id(id_order_document)
        if not ddt or not ddt.id_order:
            return False
        
        return self.order_doc_service.is_ddt_modifiable(ddt.id_order)
    
    def update_ddt_detail(self, id_order_detail: int, **kwargs) -> Optional[OrderDetail]:
        """Aggiorna un dettaglio del DDT"""
        # Verifica che il DDT sia modificabile
        detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not detail or not detail.id_order_document:
            return None
        
        if not self.is_ddt_modifiable(detail.id_order_document):
            raise ValueError("Il DDT non può essere modificato: l'ordine è già stato fatturato o spedito")
        
        # Aggiorna i campi
        for key, value in kwargs.items():
            if hasattr(detail, key):
                setattr(detail, key, value)
        
        # Aggiorna timestamp
        ddt = self.get_ddt_by_id(detail.id_order_document)
        if ddt:
            ddt.updated_at = datetime.now()
        
        self.db.commit()
        return detail
    
    def delete_ddt_detail(self, id_order_detail: int) -> bool:
        """Elimina un dettaglio del DDT"""
        # Verifica che il DDT sia modificabile
        detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not detail or not detail.id_order_document:
            return False
        
        if not self.is_ddt_modifiable(detail.id_order_document):
            raise ValueError("Il DDT non può essere modificato: l'ordine è già stato fatturato o spedito")
        
        self.db.delete(detail)
        
        # Aggiorna timestamp
        ddt = self.get_ddt_by_id(detail.id_order_document)
        if ddt:
            ddt.updated_at = datetime.now()
        
        self.db.commit()
        return True
