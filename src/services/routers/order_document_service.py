from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime
from src.models.order_document import OrderDocument
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.models.shipping import Shipping
from src.models.app_configuration import AppConfiguration
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.schemas.preventivo_schema import ArticoloPreventivoSchema, ArticoloPreventivoUpdateSchema
from src.services.core.tool import calculate_amount_with_percentage


class OrderDocumentService:
    """Service centralizzato per funzioni comuni tra Preventivi e DDT"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_next_document_number(self, type_document: str) -> int:
        """
        Genera il prossimo numero sequenziale per un tipo di documento
        
        Args:
            type_document: Tipo di documento ("preventivo", "DDT", "fattura", etc.)
            
        Returns:
            int: Prossimo numero sequenziale
        """
        current_year = datetime.now().year
        
        # Trova il numero più alto per il tipo di documento nell'anno corrente
        max_number = self.db.query(func.max(OrderDocument.document_number)).filter(
            and_(
                OrderDocument.type_document == type_document,
                func.year(OrderDocument.date_add) == current_year
            )
        ).scalar()
        
        if max_number is None:
            return 1
        
        try:
            return int(max_number) + 1
        except (ValueError, TypeError):
            return 1
    
    def get_sender_config(self) -> Dict[str, Any]:
        """
        Recupera la configurazione del mittente per DDT da AppConfiguration
        
        Returns:
            Dict con i dati del mittente
        """
        configs = self.db.query(AppConfiguration).filter(
            AppConfiguration.category == "ddt_sender"
        ).all()
        
        sender_config = {}
        for config in configs:
            sender_config[config.name] = config.value
        
        return sender_config

    def recalculate_totals_for_order(self, id_order: int) -> None:
        """Ricalcola e salva i totali dell'ordine, includendo la spedizione se presente."""
        from src.services.core.tool import calculate_order_totals
        from src.models.order_detail import OrderDetail

        order = self.db.query(Order).filter(Order.id_order == id_order).first()
        if not order:
            return

        # Recupera righe ordine
        order_details: list[OrderDetail] = self.db.query(OrderDetail).filter(OrderDetail.id_order == id_order).all()

        # Recupera percentuali tasse
        tax_ids = {d.id_tax for d in order_details if getattr(d, 'id_tax', None)}
        tax_percentages = {}
        if tax_ids:
            taxes = self.db.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
            tax_percentages = {t.id_tax: t.percentage for t in taxes}

        # Calcolo totali articoli
        totals = calculate_order_totals(order_details, tax_percentages)

        # Spedizione
        shipping_cost_with_tax = 0.0
        if order.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping and shipping.price_tax_incl:
                shipping_cost_with_tax = shipping.price_tax_incl

        # Peso totale articoli
        total_weight = sum((d.product_weight or 0.0) * (d.product_qty or 0) for d in order_details)

        # Sconti
        discount = order.total_discounts if order.total_discounts else 0.0

        # Persistenza
        order.total_weight = totals.get('total_weight', total_weight)
        order.total_price_tax_excl = totals.get('total_price', 0.0)
        order.total_paid = totals.get('total_price_with_tax', 0.0) + shipping_cost_with_tax - discount

        self.db.add(order)
        self.db.commit()

    def recalculate_totals_for_order_document(self, id_order_document: int, document_type: str) -> None:
        """Ricalcola e salva i totali del documento (preventivo/DDT)."""
        self.update_document_totals(id_order_document, document_type)
    
    def check_order_invoiced(self, id_order: int) -> bool:
        """
        Verifica se un ordine è stato fatturato
        
        Args:
            id_order: ID dell'ordine
            
        Returns:
            bool: True se l'ordine è stato fatturato
        """
        invoice_exists = self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_order == id_order,
                FiscalDocument.document_type == "invoice"
            )
        ).first()
        
        return invoice_exists is not None
    
    def check_order_shipped(self, id_order: int) -> bool:
        """
        Verifica se un ordine è stato spedito controllando la cronologia
        
        Args:
            id_order: ID dell'ordine
            
        Returns:
            bool: True se l'ordine è stato spedito
        """
        # Recupera l'ID dello stato "spedito" dalla configurazione
        shipped_state_config = self.db.query(AppConfiguration).filter(
            and_(
                AppConfiguration.category == "order_states",
                AppConfiguration.name == "is_delivered"
            )
        ).first()
        
        if not shipped_state_config:
            # Fallback: usa ID 2 se non configurato
            shipped_state_id = 2
        else:
            try:
                shipped_state_id = int(shipped_state_config.value)
            except (ValueError, TypeError):
                shipped_state_id = 2
        
        # Verifica se l'ordine ha avuto lo stato "spedito" nella cronologia
        from src.models.relations.relations import orders_history
        shipped_history = self.db.query(orders_history).filter(
            and_(
                orders_history.c.id_order == id_order,
                orders_history.c.id_order_state == shipped_state_id
            )
        ).first()
        
        return shipped_history is not None
    
    def is_ddt_modifiable(self, id_order: int) -> bool:
        """
        Verifica se un DDT può essere modificato per un ordine
        
        Args:
            id_order: ID dell'ordine
            
        Returns:
            bool: True se il DDT può essere modificato
        """
        # Un DDT è modificabile solo se:
        # 1. L'ordine non è stato fatturato
        # 2. L'ordine non è stato spedito
        
        is_invoiced = self.check_order_invoiced(id_order)
        is_shipped = self.check_order_shipped(id_order)
        
        return not is_invoiced and not is_shipped
    
    def get_articoli_order_document(self, id_order_document: int, document_type: str) -> List[OrderDetail]:
        """
        Recupera articoli di un documento (preventivo o DDT)
        
        Args:
            id_order_document: ID del documento
            document_type: Tipo documento ("preventivo" o "DDT")
            
        Returns:
            List[OrderDetail]: Lista degli articoli
        """
        if document_type == "preventivo":
            # Per preventivi: articoli con id_order = 0
            return self.db.query(OrderDetail).filter(
                and_(
                    OrderDetail.id_order_document == id_order_document,
                    OrderDetail.id_order == 0
                )
            ).all()
        elif document_type == "DDT":
            # Per DDT: articoli con id_order > 0 (collegati all'ordine)
            return self.db.query(OrderDetail).filter(
                and_(
                    OrderDetail.id_order_document == id_order_document,
                    OrderDetail.id_order > 0
                )
            ).all()
        else:
            return []
    
    def calculate_totals(self, id_order_document: int, document_type: str) -> Dict[str, float]:
        """
        Calcola totali di un documento (preventivo o DDT)
        
        Args:
            id_order_document: ID del documento
            document_type: Tipo documento ("preventivo" o "DDT")
            
        Returns:
            Dict[str, float]: Dizionario con i totali calcolati
        """
        from src.services.core.tool import calculate_order_totals
        
        articoli = self.get_articoli_order_document(id_order_document, document_type)
        
        if not articoli:
            return {
                "total_imponibile": 0.0,
                "total_iva": 0.0,
                "total_articoli": 0.0,
                "shipping_cost": 0.0,
                "total_finale": 0.0
            }
        
        # Recupera le percentuali delle tasse
        tax_ids = set()
        for articolo in articoli:
            if hasattr(articolo, 'id_tax') and articolo.id_tax:
                tax_ids.add(articolo.id_tax)
        
        tax_percentages = {}
        if tax_ids:
            taxes = self.db.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
            tax_percentages = {tax.id_tax: tax.percentage for tax in taxes}
        
        # Usa la funzione standard per calcolare i totali (include sconti)
        totals = calculate_order_totals(articoli, tax_percentages)
        
        # Aggiungi spese di spedizione se presente
        shipping_cost = 0.0
        document = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        if document and document.id_shipping:
            shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == document.id_shipping
            ).first()
            if shipping and shipping.price_tax_incl:
                shipping_cost = shipping.price_tax_incl
        
        total_finale = totals['total_price_with_tax'] + shipping_cost
        
        return {
            "total_imponibile": round(totals['total_price'], 2),
            "total_iva": round(totals['total_price_with_tax'] - totals['total_price'], 2),
            "total_articoli": round(totals['total_price_with_tax'], 2),
            "shipping_cost": round(shipping_cost, 2),
            "total_finale": round(total_finale, 2)
        }
    
    def update_document_totals(self, id_order_document: int, document_type: str) -> None:
        """
        Aggiorna i totali del documento nel database
        
        Args:
            id_order_document: ID del documento
            document_type: Tipo documento ("preventivo" o "DDT")
        """
        totals = self.calculate_totals(id_order_document, document_type)
        
        # Recupera il documento
        document = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        if document:
            # Aggiorna i totali
            document.total_price_with_tax = totals["total_finale"]
            
            # Calcola peso totale
            articoli = self.get_articoli_order_document(id_order_document, document_type)
            total_weight = sum(articolo.product_weight * articolo.product_qty for articolo in articoli)
            document.total_weight = round(total_weight, 2)
            
            # Aggiorna timestamp
            document.updated_at = datetime.now()
            
            self.db.commit()

    # ----------------- Nuovi metodi di ricalcolo leggeri -----------------
    def recalculate_totals_for_order_document(self, id_order_document: int, document_type: str) -> None:
        """Ricalcola e persiste i totali di un documento (includendo spedizione)."""
        # Log leggero
        try:
            import logging
            logging.getLogger(__name__).info(f"Ricalcolo totali documento {id_order_document} ({document_type})")
        except Exception:
            pass
        self.update_document_totals(id_order_document, document_type)

    def recalculate_totals_for_order(self, id_order: int) -> None:
        """Ricalcola i totali dell'ordine e allinea il peso della shipment se presente."""

        from src.services.core.tool import calculate_order_totals
        from src.models.tax import Tax

        order = self.db.query(Order).filter(Order.id_order == id_order).first()
        if not order:
            return

        # Carica righe dell'ordine
        order_details = self.db.query(OrderDetail).filter(OrderDetail.id_order == id_order).all()

        # Se non ci sono righe, azzera i totali
        if not order_details:
            order.total_weight = 0.0
            order.total_paid = 0.0
            self.db.commit()
            return

        # Percentuali tasse
        tax_ids = set()
        for od in order_details:
            if getattr(od, 'id_tax', None):
                tax_ids.add(od.id_tax)
        tax_percentages = {}
        if tax_ids:
            taxes = self.db.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
            tax_percentages = {t.id_tax: t.percentage for t in taxes}

        # Calcolo totali (articoli)
        totals = calculate_order_totals(order_details, tax_percentages)
        order.total_weight = sum(od.product_weight * od.product_qty for od in order_details)

        # Spedizione (se presente)
        shipping_cost_incl = 0.0
        shipping_cost_excl = 0.0
        if order.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping:
                if getattr(shipping, 'price_tax_incl', None):
                    shipping_cost_incl = shipping.price_tax_incl or 0.0
                if getattr(shipping, 'price_tax_excl', None):
                    shipping_cost_excl = shipping.price_tax_excl or 0.0

        # Sconti ordine (se presenti)
        discount = getattr(order, 'total_discounts', 0.0) or 0.0

        # Totali ordine: imponibile ed ivato
        order.total_price_tax_excl = (totals['total_price'] + shipping_cost_excl)
        order.total_paid = (totals['total_price_with_tax'] + shipping_cost_incl) - discount

        # Persisti
        self.db.commit()

        # Allinea peso shipment se esiste
        if order.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping:
                shipping.weight = order.total_weight
                self.db.commit()
    
    def add_articolo(self, id_order_document: int, articolo: ArticoloPreventivoSchema, document_type: str) -> Optional[OrderDetail]:
        """
        Aggiunge articolo a un documento (preventivo o DDT)
        
        Args:
            id_order_document: ID del documento
            articolo: Dati dell'articolo
            document_type: Tipo documento ("preventivo" o "DDT")
            
        Returns:
            OrderDetail: L'articolo creato
        """
        # Determina id_order basato sul tipo di documento
        if document_type == "preventivo":
            id_order = 0  # Preventivi non sono collegati a ordini
        elif document_type == "DDT":
            # Per DDT, recupera l'id_order dal documento
            document = self.db.query(OrderDocument).filter(
                OrderDocument.id_order_document == id_order_document
            ).first()
            id_order = document.id_order if document else 0
        else:
            raise ValueError(f"Tipo documento non supportato: {document_type}")
        
        # Crea l'articolo
        order_detail = OrderDetail(
            id_origin=0,
            id_order=id_order,
            id_order_document=id_order_document,
            id_product=articolo.id_product or 0,
            product_name=articolo.product_name or "",
            product_reference=articolo.product_reference or "",
            product_qty=articolo.product_qty,
            product_weight=articolo.product_weight or 0.0,
            product_price=articolo.product_price or 0.0,
            id_tax=articolo.id_tax,
            reduction_percent=articolo.reduction_percent or 0.0,
            reduction_amount=articolo.reduction_amount or 0.0
        )
        
        self.db.add(order_detail)
        self.db.commit()
        
        # Ricalcola i totali
        self.update_document_totals(id_order_document, document_type)
        
        return order_detail
    
    def update_articolo(self, id_order_detail: int, articolo_data: ArticoloPreventivoUpdateSchema, document_type: str) -> Optional[OrderDetail]:
        """
        Aggiorna articolo in un documento (preventivo o DDT)
        
        Args:
            id_order_detail: ID dell'articolo
            articolo_data: Dati aggiornati dell'articolo
            document_type: Tipo documento ("preventivo" o "DDT")
            
        Returns:
            OrderDetail: L'articolo aggiornato
        """
        # Recupera l'articolo
        order_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not order_detail:
            return None
        
        # Aggiorna i campi forniti
        update_data = articolo_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(order_detail, key) and value is not None:
                setattr(order_detail, key, value)
        
        self.db.commit()
        
        # Ricalcola i totali del documento
        self.update_document_totals(order_detail.id_order_document, document_type)
        
        return order_detail
    
    def remove_articolo(self, id_order_detail: int, document_type: str) -> bool:
        """
        Rimuove articolo da un documento (preventivo o DDT)
        
        Args:
            id_order_detail: ID dell'articolo
            document_type: Tipo documento ("preventivo" o "DDT")
            
        Returns:
            bool: True se rimosso con successo
        """
        # Recupera l'articolo
        order_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not order_detail:
            return False
        
        # Salva l'ID del documento per ricalcolare i totali
        id_order_document = order_detail.id_order_document
        
        # Rimuovi l'articolo
        self.db.delete(order_detail)
        self.db.commit()
        
        # Ricalcola i totali del documento
        self.update_document_totals(id_order_document, document_type)
        
        return True
