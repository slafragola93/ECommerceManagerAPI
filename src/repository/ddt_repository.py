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
from src.services.routers.order_document_service import OrderDocumentService


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
        # NOTA: Rimosso controllo is_ddt_modifiable per permettere più DDT per ordine
        
        # Recupera l'ordine originale
        original_order = self.db.query(Order).filter(Order.id_order == id_order).first()
        if not original_order:
            return None
        
        # Genera nuovo numero documento DDT
        new_document_number = self.order_doc_service.get_next_document_number("DDT")
        
        # Crea nuovo OrderDocument (DDT) copiando i dati dell'ordine
        # Converti 0 a None per le foreign key
        id_customer = original_order.id_customer if original_order.id_customer and original_order.id_customer > 0 else None
        id_address_delivery = original_order.id_address_delivery if original_order.id_address_delivery and original_order.id_address_delivery > 0 else None
        id_address_invoice = original_order.id_address_invoice if original_order.id_address_invoice and original_order.id_address_invoice > 0 else None
        id_sectional = original_order.id_sectional if original_order.id_sectional and original_order.id_sectional > 0 else None
        id_shipping = original_order.id_shipping if original_order.id_shipping and original_order.id_shipping > 0 else None
        
        new_ddt = OrderDocument(
            type_document="DDT",
            document_number=new_document_number,
            id_customer=id_customer,
            id_address_delivery=id_address_delivery,
            id_address_invoice=id_address_invoice,
            id_sectional=id_sectional,
            id_shipping=id_shipping,
            is_invoice_requested=original_order.is_invoice_requested,
            note=f"DDT generato da ordine {original_order.reference}",
            total_weight=original_order.total_weight,
            total_price_with_tax=original_order.total_price_with_tax,  # ex total_paid
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
            # Assicurati che i prezzi unitari siano al pezzo singolo (non moltiplicati per quantità)
            unit_price_net = float(detail.unit_price_net) if detail.unit_price_net else 0.0
            unit_price_with_tax = float(detail.unit_price_with_tax) if detail.unit_price_with_tax else 0.0
            
            new_detail = OrderDetail(
                id_origin=0,
                id_order=0,  # Per distinguere dalle righe ordine
                id_order_document=new_ddt.id_order_document,
                id_product=detail.id_product,
                product_name=detail.product_name,
                product_reference=detail.product_reference,
                product_qty=detail.product_qty,
                product_weight=detail.product_weight,
                unit_price_net=unit_price_net,  # Prezzo unitario al pezzo singolo
                unit_price_with_tax=unit_price_with_tax,  # Prezzo unitario al pezzo singolo
                total_price_net=float(detail.total_price_net) if detail.total_price_net else 0.0,
                total_price_with_tax=float(detail.total_price_with_tax) if detail.total_price_with_tax else 0.0,
                id_tax=detail.id_tax,
                reduction_percent=detail.reduction_percent,
                reduction_amount=detail.reduction_amount,
                rda=detail.rda if hasattr(detail, 'rda') else None,
                rda_quantity=detail.rda_quantity if hasattr(detail, 'rda_quantity') else None,
                note=detail.note
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
    
    def create_ddt_partial_from_order_detail(self, id_order_detail: int, quantity: int, user_id: int) -> Optional[OrderDocument]:
        """
        Crea un DDT parziale a partire da un singolo articolo ordine
        
        Args:
            id_order_detail: ID dell'articolo ordine
            quantity: Quantità da includere nel DDT
            user_id: ID dell'utente che crea il DDT
            
        Returns:
            OrderDocument: Il nuovo DDT creato, None se l'articolo non esiste
        """
        # Recupera l'articolo ordine originale
        original_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not original_detail:
            return None
        
        # Verifica che quantity <= product_qty
        if quantity > original_detail.product_qty:
            raise ValueError(f"La quantità richiesta ({quantity}) supera la quantità disponibile ({original_detail.product_qty})")
        
        # Recupera RDA e rda_quantity se presenti
        rda = original_detail.rda if hasattr(original_detail, 'rda') else None
        rda_quantity = original_detail.rda_quantity if hasattr(original_detail, 'rda_quantity') and original_detail.rda_quantity is not None else None
        
        # Usa rda_quantity come quantità se disponibile, altrimenti usa quantity passata
        final_quantity = rda_quantity if rda_quantity is not None and rda_quantity > 0 else quantity
        
        # Verifica che final_quantity <= product_qty
        if final_quantity > original_detail.product_qty:
            raise ValueError(f"La quantità RDA ({final_quantity}) supera la quantità disponibile ({original_detail.product_qty})")
        
        # Recupera l'ordine per ottenere i dati del cliente/indirizzi
        original_order = None
        if original_detail.id_order:
            original_order = self.db.query(Order).filter(Order.id_order == original_detail.id_order).first()
        
        # Genera nuovo numero documento DDT
        new_document_number = self.order_doc_service.get_next_document_number("DDT")
        
        # Prepara dati DDT
        id_customer = original_order.id_customer if original_order and original_order.id_customer and original_order.id_customer > 0 else None
        id_address_delivery = original_order.id_address_delivery if original_order and original_order.id_address_delivery and original_order.id_address_delivery > 0 else None
        id_address_invoice = original_order.id_address_invoice if original_order and original_order.id_address_invoice and original_order.id_address_invoice > 0 else None
        id_sectional = original_order.id_sectional if original_order and original_order.id_sectional and original_order.id_sectional > 0 else None
        id_shipping = original_order.id_shipping if original_order and original_order.id_shipping and original_order.id_shipping > 0 else None
        
        # Crea nuovo OrderDocument (DDT)
        new_ddt = OrderDocument(
            type_document="DDT",
            document_number=new_document_number,
            id_customer=id_customer,
            id_address_delivery=id_address_delivery,
            id_address_invoice=id_address_invoice,
            id_sectional=id_sectional,
            id_shipping=id_shipping,
            is_invoice_requested=original_order.is_invoice_requested if original_order else False,
            note=f"DDT parziale generato da articolo ordine {id_order_detail}",
            total_weight=0.0,  # Verrà ricalcolato
            total_price_with_tax=0.0,  # Verrà ricalcolato
            id_order=original_detail.id_order if original_detail.id_order else None,
            date_add=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.db.add(new_ddt)
        self.db.flush()  # Per ottenere l'ID
        
        # Calcola prezzi unitari (devono essere al pezzo singolo)
        unit_price_net = float(original_detail.unit_price_net) if original_detail.unit_price_net else 0.0
        unit_price_with_tax = float(original_detail.unit_price_with_tax) if original_detail.unit_price_with_tax else 0.0
        
        # Calcola totali per la quantità specificata
        total_price_net = unit_price_net * final_quantity
        total_price_with_tax = unit_price_with_tax * final_quantity
        
        # Applica sconti se presenti
        reduction_percent = float(original_detail.reduction_percent) if original_detail.reduction_percent else 0.0
        reduction_amount = float(original_detail.reduction_amount) if original_detail.reduction_amount else 0.0
        
        if reduction_percent > 0:
            from src.services.core.tool import calculate_amount_with_percentage
            discount = calculate_amount_with_percentage(total_price_net, reduction_percent)
            total_price_net = total_price_net - discount
            # Ricalcola total_price_with_tax dopo lo sconto
            if original_detail.id_tax:
                tax = self.db.query(Tax).filter(Tax.id_tax == original_detail.id_tax).first()
                if tax and tax.percentage is not None:
                    tax_percentage = float(tax.percentage)
                    from src.services.core.tool import calculate_price_with_tax
                    total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
        elif reduction_amount > 0:
            total_price_net = total_price_net - reduction_amount
            # Ricalcola total_price_with_tax dopo lo sconto
            if original_detail.id_tax:
                tax = self.db.query(Tax).filter(Tax.id_tax == original_detail.id_tax).first()
                if tax and tax.percentage is not None:
                    tax_percentage = float(tax.percentage)
                    from src.services.core.tool import calculate_price_with_tax
                    total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
        
        # Crea OrderDetail nel DDT
        new_detail = OrderDetail(
            id_origin=0,
            id_order=0,  # Per distinguere dalle righe ordine
            id_order_document=new_ddt.id_order_document,
            id_product=original_detail.id_product,
            product_name=original_detail.product_name,
            product_reference=original_detail.product_reference,
            product_qty=final_quantity,
            product_weight=original_detail.product_weight,
            unit_price_net=unit_price_net,  # Prezzo unitario al pezzo singolo
            unit_price_with_tax=unit_price_with_tax,  # Prezzo unitario al pezzo singolo
            total_price_net=total_price_net,
            total_price_with_tax=total_price_with_tax,
            id_tax=original_detail.id_tax,
            reduction_percent=reduction_percent,
            reduction_amount=reduction_amount,
            rda=rda,
            rda_quantity=rda_quantity,
            note=original_detail.note
        )
        self.db.add(new_detail)
        
        # Ricalcola totali DDT
        self.order_doc_service.update_document_totals(new_ddt.id_order_document, "DDT")
        
        self.db.commit()
        return new_ddt
    
    def create_ddt_partial_from_order_details(self, articoli_data: List[dict], user_id: int) -> Optional[OrderDocument]:
        """
        Crea un DDT parziale a partire da più articoli ordine
        
        Args:
            articoli_data: Lista di dizionari con id_order_detail e quantity
            user_id: ID dell'utente che crea il DDT
            
        Returns:
            OrderDocument: Il nuovo DDT creato, None se gli articoli non esistono
        """
        if not articoli_data:
            raise ValueError("La lista di articoli non può essere vuota")
        
        # Recupera il primo articolo per ottenere i dati dell'ordine
        first_articolo = articoli_data[0]
        first_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == first_articolo['id_order_detail']
        ).first()
        
        if not first_detail:
            return None
        
        # Recupera l'ordine per ottenere i dati del cliente/indirizzi
        original_order = None
        if first_detail.id_order:
            original_order = self.db.query(Order).filter(Order.id_order == first_detail.id_order).first()
        
        # Genera nuovo numero documento DDT
        new_document_number = self.order_doc_service.get_next_document_number("DDT")
        
        # Prepara dati DDT
        id_customer = original_order.id_customer if original_order and original_order.id_customer and original_order.id_customer > 0 else None
        id_address_delivery = original_order.id_address_delivery if original_order and original_order.id_address_delivery and original_order.id_address_delivery > 0 else None
        id_address_invoice = original_order.id_address_invoice if original_order and original_order.id_address_invoice and original_order.id_address_invoice > 0 else None
        id_sectional = original_order.id_sectional if original_order and original_order.id_sectional and original_order.id_sectional > 0 else None
        id_shipping = original_order.id_shipping if original_order and original_order.id_shipping and original_order.id_shipping > 0 else None
        
        # Crea nuovo OrderDocument (DDT)
        new_ddt = OrderDocument(
            type_document="DDT",
            document_number=new_document_number,
            id_customer=id_customer,
            id_address_delivery=id_address_delivery,
            id_address_invoice=id_address_invoice,
            id_sectional=id_sectional,
            id_shipping=id_shipping,
            is_invoice_requested=original_order.is_invoice_requested if original_order else False,
            note=f"DDT parziale generato da {len(articoli_data)} articoli ordine",
            total_weight=0.0,  # Verrà ricalcolato
            total_price_with_tax=0.0,  # Verrà ricalcolato
            id_order=first_detail.id_order if first_detail.id_order else None,
            date_add=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.db.add(new_ddt)
        self.db.flush()  # Per ottenere l'ID
        
        # Processa ogni articolo
        for articolo_data in articoli_data:
            id_order_detail = articolo_data['id_order_detail']
            quantity = articolo_data['quantity']
            
            # Recupera l'articolo ordine originale
            original_detail = self.db.query(OrderDetail).filter(
                OrderDetail.id_order_detail == id_order_detail
            ).first()
            
            if not original_detail:
                raise ValueError(f"Articolo ordine {id_order_detail} non trovato")
            
            # Verifica che quantity <= product_qty
            if quantity > original_detail.product_qty:
                raise ValueError(f"La quantità richiesta ({quantity}) supera la quantità disponibile ({original_detail.product_qty}) per l'articolo {id_order_detail}")
            
            # Recupera RDA e rda_quantity se presenti
            rda = original_detail.rda if hasattr(original_detail, 'rda') else None
            rda_quantity = original_detail.rda_quantity if hasattr(original_detail, 'rda_quantity') and original_detail.rda_quantity is not None else None
            
            # Usa rda_quantity come quantità se disponibile, altrimenti usa quantity passata
            final_quantity = rda_quantity if rda_quantity is not None and rda_quantity > 0 else quantity
            
            # Verifica che final_quantity <= product_qty
            if final_quantity > original_detail.product_qty:
                raise ValueError(f"La quantità RDA ({final_quantity}) supera la quantità disponibile ({original_detail.product_qty}) per l'articolo {id_order_detail}")
            
            # Calcola prezzi unitari (devono essere al pezzo singolo)
            unit_price_net = float(original_detail.unit_price_net) if original_detail.unit_price_net else 0.0
            unit_price_with_tax = float(original_detail.unit_price_with_tax) if original_detail.unit_price_with_tax else 0.0
            
            # Calcola totali per la quantità specificata
            total_price_net = unit_price_net * final_quantity
            total_price_with_tax = unit_price_with_tax * final_quantity
            
            # Applica sconti se presenti
            reduction_percent = float(original_detail.reduction_percent) if original_detail.reduction_percent else 0.0
            reduction_amount = float(original_detail.reduction_amount) if original_detail.reduction_amount else 0.0
            
            if reduction_percent > 0:
                from src.services.core.tool import calculate_amount_with_percentage
                discount = calculate_amount_with_percentage(total_price_net, reduction_percent)
                total_price_net = total_price_net - discount
                # Ricalcola total_price_with_tax dopo lo sconto
                if original_detail.id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == original_detail.id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                        from src.services.core.tool import calculate_price_with_tax
                        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            elif reduction_amount > 0:
                total_price_net = total_price_net - reduction_amount
                # Ricalcola total_price_with_tax dopo lo sconto
                if original_detail.id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == original_detail.id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                        from src.services.core.tool import calculate_price_with_tax
                        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            
            # Crea OrderDetail nel DDT
            new_detail = OrderDetail(
                id_origin=0,
                id_order=0,  # Per distinguere dalle righe ordine
                id_order_document=new_ddt.id_order_document,
                id_product=original_detail.id_product,
                product_name=original_detail.product_name,
                product_reference=original_detail.product_reference,
                product_qty=final_quantity,
                product_weight=original_detail.product_weight,
                unit_price_net=unit_price_net,  # Prezzo unitario al pezzo singolo
                unit_price_with_tax=unit_price_with_tax,  # Prezzo unitario al pezzo singolo
                total_price_net=total_price_net,
                total_price_with_tax=total_price_with_tax,
                id_tax=original_detail.id_tax,
                reduction_percent=reduction_percent,
                reduction_amount=reduction_amount,
                rda=rda,
                rda_quantity=rda_quantity,
                note=original_detail.note
            )
            self.db.add(new_detail)
        
        # Ricalcola totali DDT
        self.order_doc_service.update_document_totals(new_ddt.id_order_document, "DDT")
        
        self.db.commit()
        return new_ddt
    
    def create_ddt(self, data: dict, user_id: int) -> Optional[OrderDocument]:
        """
        Crea un DDT normale
        
        Args:
            data: Dizionario con dati DDT
            user_id: ID dell'utente che crea il DDT
            
        Returns:
            OrderDocument: Il nuovo DDT creato
        """
        # Genera nuovo numero documento DDT
        new_document_number = self.order_doc_service.get_next_document_number("DDT")
        
        # Crea nuovo OrderDocument (DDT)
        new_ddt = OrderDocument(
            type_document="DDT",
            document_number=new_document_number,
            id_customer=data.get('id_customer'),
            id_address_delivery=data.get('id_address_delivery'),
            id_address_invoice=data.get('id_address_invoice'),
            id_sectional=data.get('id_sectional'),
            id_shipping=data.get('id_shipping'),
            id_payment=data.get('id_payment'),
            is_invoice_requested=data.get('is_invoice_requested', False),
            note=data.get('note'),
            total_weight=0.0,
            total_price_with_tax=0.0,
            id_order=data.get('id_order'),
            date_add=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.db.add(new_ddt)
        self.db.flush()
        
        self.db.commit()
        return new_ddt
    
    def get_ddt_list(self, skip: int = 0, limit: int = 100, search: Optional[str] = None,
                     sectionals_ids: Optional[str] = None, payments_ids: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[OrderDocument]:
        """
        Recupera lista DDT con filtri (stessi filtri preventivi)
        
        Args:
            skip: Offset per paginazione
            limit: Limite risultati
            search: Ricerca testuale in document_number o note
            sectionals_ids: ID sezionali separati da virgole
            payments_ids: ID pagamenti separati da virgole
            date_from: Data inizio filtro
            date_to: Data fine filtro
            
        Returns:
            List[OrderDocument]: Lista DDT
        """
        from sqlalchemy import or_
        from src.services import QueryUtils
        from fastapi import HTTPException
        
        query = self.db.query(OrderDocument).filter(
            OrderDocument.type_document == "DDT"
        )
        
        try:
            # Filtro per ricerca testuale
            if search:
                query = query.filter(
                    or_(
                        OrderDocument.document_number.ilike(f"%{search}%"),
                        OrderDocument.note.ilike(f"%{search}%")
                    )
                )
            
            # Filtri per ID
            if sectionals_ids:
                query = QueryUtils.filter_by_id(query, OrderDocument, 'id_sectional', sectionals_ids)
            if payments_ids:
                query = QueryUtils.filter_by_id(query, OrderDocument, 'id_payment', payments_ids)
            
            # Filtri per data
            if date_from:
                query = query.filter(OrderDocument.date_add >= date_from)
            if date_to:
                query = query.filter(OrderDocument.date_add <= date_to)
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        return query.order_by(OrderDocument.id_order_document.desc()).offset(skip).limit(limit).all()
    
    def get_ddt_list_count(self, search: Optional[str] = None,
                           sectionals_ids: Optional[str] = None, payments_ids: Optional[str] = None,
                           date_from: Optional[str] = None, date_to: Optional[str] = None) -> int:
        """
        Conta DDT con filtri applicati
        """
        from sqlalchemy import func, or_
        from src.services import QueryUtils
        from fastapi import HTTPException
        
        query = self.db.query(func.count(OrderDocument.id_order_document)).filter(
            OrderDocument.type_document == "DDT"
        )
        
        try:
            if search:
                query = query.filter(
                    or_(
                        OrderDocument.document_number.ilike(f"%{search}%"),
                        OrderDocument.note.ilike(f"%{search}%")
                    )
                )
            if sectionals_ids:
                query = QueryUtils.filter_by_id(query, OrderDocument, 'id_sectional', sectionals_ids)
            if payments_ids:
                query = QueryUtils.filter_by_id(query, OrderDocument, 'id_payment', payments_ids)
            if date_from:
                query = query.filter(OrderDocument.date_add >= date_from)
            if date_to:
                query = query.filter(OrderDocument.date_add <= date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        return query.scalar()
    
    def merge_articolo_to_ddt(self, id_order_document: int, id_order_detail: int, quantity: int) -> Optional[OrderDetail]:
        """
        Accorpa un articolo a un DDT esistente
        
        Args:
            id_order_document: ID DDT esistente
            id_order_detail: ID articolo ordine da aggiungere
            quantity: Quantità da aggiungere
            
        Returns:
            OrderDetail: Articolo aggiunto/aggiornato nel DDT
        """
        # Verifica che il DDT sia modificabile (per modifiche a DDT esistente)
        if not self.is_ddt_modifiable(id_order_document):
            raise ValueError("Il DDT non può essere modificato: l'ordine è già stato fatturato o spedito")
        
        # Recupera DDT
        ddt = self.get_ddt_by_id(id_order_document)
        if not ddt:
            raise ValueError("DDT non trovato")
        
        # Recupera articolo ordine originale
        original_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not original_detail:
            raise ValueError("Articolo ordine non trovato")
        
        # Verifica che quantity <= product_qty disponibile
        if quantity > original_detail.product_qty:
            raise ValueError(f"La quantità richiesta ({quantity}) supera la quantità disponibile ({original_detail.product_qty})")
        
        # Cerca se articolo esiste già nel DDT (stesso id_product o product_reference)
        existing_detail = None
        if original_detail.id_product:
            existing_detail = self.db.query(OrderDetail).filter(
                and_(
                    OrderDetail.id_order_document == id_order_document,
                    OrderDetail.id_order == 0,
                    OrderDetail.id_product == original_detail.id_product
                )
            ).first()
        elif original_detail.product_reference:
            existing_detail = self.db.query(OrderDetail).filter(
                and_(
                    OrderDetail.id_order_document == id_order_document,
                    OrderDetail.id_order == 0,
                    OrderDetail.product_reference == original_detail.product_reference
                )
            ).first()
        
        if existing_detail:
            # Somma quantità alla riga esistente
            existing_detail.product_qty += quantity
            
            # Ricalcola totali
            unit_price_net = float(existing_detail.unit_price_net) if existing_detail.unit_price_net else 0.0
            unit_price_with_tax = float(existing_detail.unit_price_with_tax) if existing_detail.unit_price_with_tax else 0.0
            
            total_price_net = unit_price_net * existing_detail.product_qty
            total_price_with_tax = unit_price_with_tax * existing_detail.product_qty
            
            # Applica sconti
            reduction_percent = float(existing_detail.reduction_percent) if existing_detail.reduction_percent else 0.0
            reduction_amount = float(existing_detail.reduction_amount) if existing_detail.reduction_amount else 0.0
            
            if reduction_percent > 0:
                from src.services.core.tool import calculate_amount_with_percentage
                discount = calculate_amount_with_percentage(total_price_net, reduction_percent)
                total_price_net = total_price_net - discount
                if existing_detail.id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == existing_detail.id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                        from src.services.core.tool import calculate_price_with_tax
                        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            elif reduction_amount > 0:
                total_price_net = total_price_net - reduction_amount
                if existing_detail.id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == existing_detail.id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                        from src.services.core.tool import calculate_price_with_tax
                        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            
            existing_detail.total_price_net = total_price_net
            existing_detail.total_price_with_tax = total_price_with_tax
            
            # Aggiorna timestamp DDT
            ddt.updated_at = datetime.now()
            
            # Ricalcola totali DDT
            self.order_doc_service.update_document_totals(id_order_document, "DDT")
            
            self.db.commit()
            return existing_detail
        else:
            # Crea nuova riga nel DDT
            unit_price_net = float(original_detail.unit_price_net) if original_detail.unit_price_net else 0.0
            unit_price_with_tax = float(original_detail.unit_price_with_tax) if original_detail.unit_price_with_tax else 0.0
            
            total_price_net = unit_price_net * quantity
            total_price_with_tax = unit_price_with_tax * quantity
            
            # Applica sconti
            reduction_percent = float(original_detail.reduction_percent) if original_detail.reduction_percent else 0.0
            reduction_amount = float(original_detail.reduction_amount) if original_detail.reduction_amount else 0.0
            
            if reduction_percent > 0:
                from src.services.core.tool import calculate_amount_with_percentage
                discount = calculate_amount_with_percentage(total_price_net, reduction_percent)
                total_price_net = total_price_net - discount
                if original_detail.id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == original_detail.id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                        from src.services.core.tool import calculate_price_with_tax
                        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            elif reduction_amount > 0:
                total_price_net = total_price_net - reduction_amount
                if original_detail.id_tax:
                    tax = self.db.query(Tax).filter(Tax.id_tax == original_detail.id_tax).first()
                    if tax and tax.percentage is not None:
                        tax_percentage = float(tax.percentage)
                        from src.services.core.tool import calculate_price_with_tax
                        total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            
            new_detail = OrderDetail(
                id_origin=0,
                id_order=0,
                id_order_document=id_order_document,
                id_product=original_detail.id_product,
                product_name=original_detail.product_name,
                product_reference=original_detail.product_reference,
                product_qty=quantity,
                product_weight=original_detail.product_weight,
                unit_price_net=unit_price_net,  # Prezzo unitario al pezzo singolo
                unit_price_with_tax=unit_price_with_tax,  # Prezzo unitario al pezzo singolo
                total_price_net=total_price_net,
                total_price_with_tax=total_price_with_tax,
                id_tax=original_detail.id_tax,
                reduction_percent=reduction_percent,
                reduction_amount=reduction_amount,
                rda=original_detail.rda if hasattr(original_detail, 'rda') else None,
                rda_quantity=original_detail.rda_quantity if hasattr(original_detail, 'rda_quantity') else None,
                note=original_detail.note
            )
            self.db.add(new_detail)
            
            # Aggiorna timestamp DDT
            ddt.updated_at = datetime.now()
            
            # Ricalcola totali DDT
            self.order_doc_service.update_document_totals(id_order_document, "DDT")
            
            self.db.commit()
            return new_detail
