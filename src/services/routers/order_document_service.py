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
from src.services.core.tool import calculate_price_without_tax, calculate_price_with_tax


class OrderDocumentService:
    """Service centralizzato per funzioni comuni tra Preventivi e DDT"""
    
    def __init__(self, db: Session):
        self.db = db

    def _get_order_service(self):
        """Restituisce un OrderService che usa la stessa sessione DB."""
        from src.repository.order_repository import OrderRepository
        from src.services.routers.order_service import OrderService

        return OrderService(OrderRepository(self.db))
    
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
            Dict con i dati del mittente, incluso id_address se configurato
        """
        configs = self.db.query(AppConfiguration).filter(
            AppConfiguration.category == "ddt_sender"
        ).all()
        
        sender_config = {}
        for config in configs:
            sender_config[config.name] = config.value
        
        # Recupera id_address default se configurato
        default_address_config = self.db.query(AppConfiguration).filter(
            and_(
                AppConfiguration.category == "ddt_sender",
                AppConfiguration.name == "default_sender_address_id"
            )
        ).first()
        
        if default_address_config and default_address_config.value:
            try:
                sender_config["default_sender_address_id"] = int(default_address_config.value)
            except (ValueError, TypeError):
                sender_config["default_sender_address_id"] = None
        
        return sender_config

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
        Recupera articoli di un documento (preventivo, DDT o shipping)
        
        Args:
            id_order_document: ID del documento
            document_type: Tipo documento ("preventivo", "DDT" o "shipping")
            
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
        elif document_type == "shipping":
            # Per shipping (multispedizione): articoli con id_order = 0 (collegati al documento, non all'ordine)
            return self.db.query(OrderDetail).filter(
                and_(
                    OrderDetail.id_order_document == id_order_document
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
        
        # Recupera il documento per ottenere total_discount
        document = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        if not articoli:
            total_discount = float(document.total_discount) if document and document.total_discount else 0.0
            return {
                "total_imponibile": 0.0,
                "total_price_net": 0.0,
                "total_iva": 0.0,
                "total_articoli": 0.0,
                "shipping_cost": 0.0,
                "total_finale": 0.0,
                "total_discount": round(total_discount, 2),
                "total_discounts_applicati": round(total_discount, 2),
                "products_total_price_net": 0.0,
                "products_total_price_with_tax": 0.0
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
        
        # Totali base (prima dello sconto totale) - SOLO PRODOTTI, senza shipping
        total_imponibile_base = totals['total_price']  # Prezzo base prodotti dopo sconti articoli
        total_iva_base = totals['total_price_with_tax'] - totals['total_price']  # IVA prodotti
        total_articoli_base = totals['total_price_with_tax']  # Totale prodotti con IVA
        
        # Per products_total_price_net, usiamo total_imponibile_base che è già corretto (senza shipping)
        # Questo è il totale imponibile dei prodotti dopo gli sconti sugli articoli, ma prima dello sconto totale documento
        total_price_net_base = total_imponibile_base
        
        # Recupera total_discount dal documento
        total_discount = float(document.total_discount) if document and document.total_discount else 0.0
        
        # Applica lo sconto al totale senza IVA (comportamento standard)
        if total_discount > 0:
            # Applica lo sconto al totale senza IVA
            total_imponibile_dopo_sconto = max(0.0, total_imponibile_base - total_discount)
            # Applica lo sconto anche al total_price_net
            total_price_net_dopo_sconto = max(0.0, total_price_net_base - total_discount)
            
            # Ricalcola total_iva proporzionalmente
            if total_imponibile_base > 0:
                ratio = total_imponibile_dopo_sconto / total_imponibile_base
                total_iva_dopo_sconto = total_iva_base * ratio
            else:
                total_iva_dopo_sconto = 0.0
            
            total_articoli_dopo_sconto = total_imponibile_dopo_sconto + total_iva_dopo_sconto
        else:
            # Nessuno sconto
            total_imponibile_dopo_sconto = total_imponibile_base
            total_price_net_dopo_sconto = total_price_net_base
            total_iva_dopo_sconto = total_iva_base
            total_articoli_dopo_sconto = total_articoli_base
        
        # Aggiungi spese di spedizione (dopo lo sconto)
        shipping_cost = 0.0
        if document and document.id_shipping:
            shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == document.id_shipping
            ).first()
            if shipping and shipping.price_tax_incl:
                shipping_cost = float(shipping.price_tax_incl)
        
        total_finale = total_articoli_dopo_sconto + shipping_cost
        
        # Calcola totale sconti: sconti sugli articoli + sconto totale documento
        total_discounts_articoli = totals.get('total_discounts', 0.0)
        total_discounts_applicati = total_discounts_articoli + total_discount
        
        return {
            "total_imponibile": round(total_imponibile_dopo_sconto, 2),
            "total_price_net": round(total_price_net_dopo_sconto, 2),
            "total_iva": round(total_iva_dopo_sconto, 2),
            "total_articoli": round(total_articoli_dopo_sconto, 2),
            "shipping_cost": round(shipping_cost, 2),
            "total_finale": round(total_finale, 2),
            "total_discount": round(total_discount, 2),
            "total_discounts_applicati": round(total_discounts_applicati, 2),
            "products_total_price_net": round(total_price_net_base, 2),  # Totale prodotti senza shipping e senza sconto totale
            "products_total_price_with_tax": round(total_articoli_base, 2)  # Totale prodotti con IVA senza shipping e senza sconto totale
        }
    
    def update_document_totals(self, id_order_document: int, document_type: str, skip_shipping_weight_update: bool = False) -> None:
        """
        Aggiorna i totali del documento nel database
        
        Args:
            id_order_document: ID del documento
            document_type: Tipo documento ("preventivo" o "DDT")
            skip_shipping_weight_update: Se True, non aggiorna il peso della shipping (utile quando il peso è stato passato esplicitamente)
        """
        totals = self.calculate_totals(id_order_document, document_type)
        
        # Recupera il documento
        document = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        if document:
            # Aggiorna i totali
            document.total_price_with_tax = totals["total_finale"]
            document.total_price_net = totals["total_price_net"]
            
            # Aggiorna i totali prodotti (solo per preventivi)
            if document_type == "preventivo":
                document.products_total_price_net = totals["products_total_price_net"]
                document.products_total_price_with_tax = totals["products_total_price_with_tax"]
            else:
                document.products_total_price_net = 0.0
                document.products_total_price_with_tax = 0.0
            
            # Calcola peso totale
            articoli = self.get_articoli_order_document(id_order_document, document_type)
            total_weight = sum((float(articolo.product_weight)) * articolo.product_qty for articolo in articoli)
            document.total_weight = total_weight
            
            # Aggiorna timestamp
            document.updated_at = datetime.now()
            
            self.db.commit()
            
            # Aggiorna peso spedizione automaticamente solo se non è stato passato esplicitamente
            if not skip_shipping_weight_update:
                self.update_shipping_weight_from_articles(id_order_document=id_order_document)

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
        """Ricalcola i totali dell'ordine delegando al servizio ordini."""
        order_service = self._get_order_service()
        order_service.recalculate_totals_for_order(id_order)
    
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
        
        # Calcola i campi prezzo mancanti
        # Recupera tax_percentage se id_tax è fornito
        tax_percentage = 0.0
        if articolo.id_tax:
            tax = self.db.query(Tax).filter(Tax.id_tax == articolo.id_tax).first()
            if tax and tax.percentage is not None:
                tax_percentage = float(tax.percentage)
        
        # total_price_with_tax è OBBLIGATORIO
        total_price_with_tax = articolo.total_price_with_tax
        
        # Calcola total_price_net se non fornito
        if articolo.total_price_net is not None:
            total_price_net = articolo.total_price_net
        else:
            # Calcola da total_price_with_tax usando la percentuale IVA
            total_price_net = calculate_price_without_tax(total_price_with_tax, tax_percentage)
        
        # Calcola unit_price_with_tax se non fornito
        if articolo.unit_price_with_tax is not None:
            unit_price_with_tax = articolo.unit_price_with_tax
        else:
            # Calcola da total_price_with_tax diviso per quantità
            unit_price_with_tax = total_price_with_tax / articolo.product_qty
        
        # Prezzi unitari da totali (dati usati come passati, nessuna applicazione sconti)
        unit_price_net = total_price_net / articolo.product_qty
        unit_price_with_tax = total_price_with_tax / articolo.product_qty
        
        reduction_percent = articolo.reduction_percent or 0.0
        reduction_amount = articolo.reduction_amount or 0.0
        
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
            product_price=unit_price_net,  # unit_price_net viene mappato a product_price tramite setter
            unit_price_net=unit_price_net,
            unit_price_with_tax=unit_price_with_tax,
            total_price_net=total_price_net,
            total_price_with_tax=total_price_with_tax,
            id_tax=articolo.id_tax,
            reduction_percent=reduction_percent,
            reduction_amount=reduction_amount,
            note=articolo.note
        )
        
        self.db.add(order_detail)
        self.db.commit()
        
        if id_order and id_order > 0:
            self._get_order_service().recalculate_totals_for_order(id_order)

        # Ricalcola i totali
        self.update_document_totals(id_order_document, document_type)
        
        # Aggiorna peso spedizione automaticamente
        self.update_shipping_weight_from_articles(id_order_document=id_order_document)
        
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
        tracked_fields = ("id_tax", "product_price", "product_weight", "reduction_percent", "reduction_amount")
        previous_values = {field: getattr(order_detail, field) for field in tracked_fields}
        order_id = getattr(order_detail, "id_order", 0)
        
        # Aggiorna i campi forniti
        update_data = articolo_data.model_dump(exclude_unset=True)
        
        # Se viene passato total_price_with_tax, ricalcola i prezzi unitari (devono essere al pezzo singolo)
        if 'total_price_with_tax' in update_data and update_data['total_price_with_tax'] is not None:
            total_price_with_tax = float(update_data['total_price_with_tax'])
            product_qty = update_data.get('product_qty', order_detail.product_qty) or 1
            
            # Calcola unit_price_with_tax (al pezzo singolo)
            unit_price_with_tax = total_price_with_tax / product_qty
            
            # Recupera tax_percentage per calcolare unit_price_net
            tax_percentage = 0.0
            id_tax = update_data.get('id_tax', order_detail.id_tax)
            if id_tax:
                tax = self.db.query(Tax).filter(Tax.id_tax == id_tax).first()
                if tax and tax.percentage is not None:
                    tax_percentage = float(tax.percentage)
            
            # Calcola unit_price_net (al pezzo singolo)
            unit_price_net = calculate_price_without_tax(unit_price_with_tax, tax_percentage)
            
            # Calcola total_price_net
            total_price_net = unit_price_net * product_qty
            
            # Aggiorna i prezzi calcolati
            order_detail.unit_price_net = unit_price_net
            order_detail.unit_price_with_tax = unit_price_with_tax
            order_detail.total_price_net = total_price_net
            order_detail.total_price_with_tax = total_price_with_tax
            # Rimuovi total_price_with_tax da update_data per evitare sovrascrittura
            update_data.pop('total_price_with_tax', None)
        
        # Se viene passato unit_price_net o unit_price_with_tax, assicurati che siano al pezzo singolo
        # e ricalcola i totali
        if 'unit_price_net' in update_data or 'unit_price_with_tax' in update_data:
            unit_price_net = float(update_data.get('unit_price_net', order_detail.unit_price_net)) if update_data.get('unit_price_net') is not None else float(order_detail.unit_price_net or 0.0)
            unit_price_with_tax = float(update_data.get('unit_price_with_tax', order_detail.unit_price_with_tax)) if update_data.get('unit_price_with_tax') is not None else float(order_detail.unit_price_with_tax or 0.0)
            product_qty = update_data.get('product_qty', order_detail.product_qty) or 1
            
            # Se manca uno dei due, calcolalo
            if unit_price_net == 0.0 and unit_price_with_tax > 0.0:
                tax_percentage = 0.0
                id_tax = update_data.get('id_tax', order_detail.id_tax)
                if id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                unit_price_net = calculate_price_without_tax(unit_price_with_tax, tax_percentage)
            elif unit_price_with_tax == 0.0 and unit_price_net > 0.0:
                tax_percentage = 0.0
                id_tax = update_data.get('id_tax', order_detail.id_tax)
                if id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                unit_price_with_tax = calculate_price_with_tax(unit_price_net, tax_percentage, quantity=1)
            
            # Calcola totali (prezzi unitari * quantità, dati usati come passati)
            total_price_net = unit_price_net * product_qty
            total_price_with_tax = unit_price_with_tax * product_qty
            
            # Aggiorna i prezzi
            order_detail.unit_price_net = unit_price_net
            order_detail.unit_price_with_tax = unit_price_with_tax
            order_detail.total_price_net = total_price_net
            order_detail.total_price_with_tax = total_price_with_tax
            # Rimuovi da update_data per evitare sovrascrittura
            update_data.pop('unit_price_net', None)
            update_data.pop('unit_price_with_tax', None)
        
        # Aggiorna gli altri campi
        for key, value in update_data.items():
            if hasattr(order_detail, key) and value is not None:
                setattr(order_detail, key, value)
        
        self.db.commit()
        if order_id and order_id > 0:
            tracked_changed = any(
                field in update_data and previous_values.get(field) != getattr(order_detail, field)
                for field in tracked_fields
            )
            if tracked_changed:
                self._get_order_service().recalculate_totals_for_order(order_id)
        
        # Ricalcola i totali del documento
        self.update_document_totals(order_detail.id_order_document, document_type)
        
        # Aggiorna peso spedizione automaticamente
        if order_detail.id_order_document and order_detail.id_order_document > 0:
            self.update_shipping_weight_from_articles(id_order_document=order_detail.id_order_document)
        elif order_detail.id_order and order_detail.id_order > 0:
            self.update_shipping_weight_from_articles(id_order=order_detail.id_order, check_order_state=True)
        
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
        order_id = getattr(order_detail, "id_order", 0)
        
        # Salva l'ID del documento per ricalcolare i totali
        id_order_document = order_detail.id_order_document
        
        # Rimuovi l'articolo
        self.db.delete(order_detail)
        self.db.commit()
        if order_id and order_id > 0:
            self._get_order_service().recalculate_totals_for_order(order_id)
        
        # Ricalcola i totali del documento
        self.update_document_totals(id_order_document, document_type)
        
        # Aggiorna peso spedizione automaticamente
        if id_order_document and id_order_document > 0:
            self.update_shipping_weight_from_articles(id_order_document=id_order_document)
        elif order_id and order_id > 0:
            self.update_shipping_weight_from_articles(id_order=order_id, check_order_state=True)
        
        return True
    
    def update_shipping_weight_from_articles(
        self,
        id_order_document: Optional[int] = None,
        id_order: Optional[int] = None,
        check_order_state: bool = True
    ) -> bool:
        """
        Aggiorna il peso della spedizione basandosi sul totale peso articoli * quantità.
        
        Calcola automaticamente il peso totale degli articoli (peso * quantità) e 
        aggiorna il campo weight della spedizione collegata.
        
        Args:
            id_order_document: ID OrderDocument (per preventivi/DDT)
            id_order: ID Order (per ordini)
            check_order_state: Se True, aggiorna solo ordini con stato = 1
            
        Returns:
            bool: True se aggiornato con successo, False altrimenti
        
        Raises:
            ValueError: Se né id_order_document né id_order sono forniti
        
        Note:
            - Per OrderDocument: aggiorna sempre il peso
            - Per Order: aggiorna solo se stato = 1 (quando check_order_state=True)
            - I modelli sono già importati in cima al file (no import locali)
        """
        if not id_order_document and not id_order:
            raise ValueError("Deve essere fornito id_order_document o id_order")
        
        shipping_id = None
        total_weight = 0.0
        
        # Caso 1: OrderDocument (preventivi/DDT)
        if id_order_document:
            # Recupera solo product_weight e product_qty degli articoli (ottimizzazione)
            articoli = self.db.query(
                OrderDetail.product_weight,
                OrderDetail.product_qty
            ).filter(
                OrderDetail.id_order_document == id_order_document,
                OrderDetail.id_order == 0
            ).all()
            
            # Calcola peso totale: sum(peso * quantità)
            total_weight = sum(
                float(a.product_weight or 0.0) * int(a.product_qty or 0)
                for a in articoli
            )
            
            # Recupera solo id_shipping dall'OrderDocument (ottimizzazione)
            result = self.db.query(OrderDocument.id_shipping).filter(
                OrderDocument.id_order_document == id_order_document
            ).first()
            if result:
                shipping_id = result.id_shipping
        
        # Caso 2: Order (ordini)
        elif id_order:
            # Recupera solo id_order_state e id_shipping (ottimizzazione)
            order_result = self.db.query(
                Order.id_order_state,
                Order.id_shipping
            ).filter(Order.id_order == id_order).first()
            
            if not order_result:
                return False
            
            if check_order_state and order_result.id_order_state != 1:
                return False  # Non aggiornare se stato != 1
            
            # Recupera solo product_weight e product_qty degli articoli (ottimizzazione)
            articoli = self.db.query(
                OrderDetail.product_weight,
                OrderDetail.product_qty
            ).filter(
                OrderDetail.id_order == id_order
            ).all()
            
            # Calcola peso totale: sum(peso * quantità)
            total_weight = sum(
                float(a.product_weight or 0.0) * int(a.product_qty or 0)
                for a in articoli
            )
            
            shipping_id = order_result.id_shipping
        
        # Aggiorna shipping.weight se esiste
        if shipping_id:
            shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == shipping_id
            ).first()
            if shipping:
                shipping.weight = total_weight
                self.db.commit()
                return True
        
        return False