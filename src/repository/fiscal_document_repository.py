from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime
import math

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.address import Address
from src.models.country import Country
from src.models.shipping import Shipping


class FiscalDocumentRepository:
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== FATTURE ====================
    
    def create_invoice(self, id_order: int, is_electronic: bool = True) -> FiscalDocument:
        """
        Crea una nuova fattura per un ordine
        
        Args:
            id_order: ID dell'ordine
            is_electronic: Se True, genera fattura elettronica (solo per IT)
        
        Returns:
            FiscalDocument creato
        """
        # Verifica che l'ordine esista
        order = self.db.query(Order).filter(Order.id_order == id_order).first()
        if not order:
            raise ValueError(f"Ordine {id_order} non trovato")
        
        # Se is_electronic=True, verifica che l'indirizzo sia italiano
        if is_electronic:
            # Recupera ID Italia da iso_code
            italy = self.db.query(Country).filter(Country.iso_code == 'IT').first()
            if not italy:
                raise ValueError("Paese Italia (IT) non trovato nel database")
            
            address = self.db.query(Address).filter(Address.id_address == order.id_address_invoice).first()
            if not address or address.id_country != italy.id_country:
                raise ValueError("La fattura elettronica può essere emessa solo per indirizzi italiani")
        
        # Genera numero documento se elettronico
        document_number = None
        tipo_documento_fe = None
        
        if is_electronic:
            document_number = self._get_next_electronic_number('invoice')
            tipo_documento_fe = 'TD01'
        
        # Crea fattura (total_amount verrà calcolato dopo)
        invoice = FiscalDocument(
            document_type='invoice',
            tipo_documento_fe=tipo_documento_fe,
            id_order=id_order,
            document_number=document_number,
            is_electronic=is_electronic,
            status='pending',
            total_amount=0.0  # Verrà aggiornato dopo aver creato i dettagli
        )
        
        self.db.add(invoice)
        self.db.flush()  # Per ottenere id_fiscal_document
        
        # Crea fiscal_document_details per ogni order_detail dell'ordine
        order_details = self.db.query(OrderDetail).filter(
            OrderDetail.id_order == id_order
        ).all()
        
        total_details_amount = 0.0  # Somma dei total_amount dei dettagli (senza IVA, già scontati)
        
        for od in order_details:
            # unit_price: prezzo unitario originale senza alterazioni
            unit_price = od.product_price or 0.0
            quantity = od.product_qty or 0
            
            # Calcola total_amount applicando gli sconti
            total_base = unit_price * quantity
            
            # Applica sconti a total_amount
            if od.reduction_percent and od.reduction_percent > 0:
                sconto = total_base * (od.reduction_percent / 100)
                total_amount = total_base - sconto
            elif od.reduction_amount and od.reduction_amount > 0:
                total_amount = total_base - od.reduction_amount
            else:
                total_amount = total_base
            
            # IMPORTANTE:
            # - unit_price: prezzo unitario ORIGINALE (no sconto)
            # - total_amount: totale riga SCONTATO (unit_price × qty - sconto), SENZA IVA
            
            detail = FiscalDocumentDetail(
                id_fiscal_document=invoice.id_fiscal_document,
                id_order_detail=od.id_order_detail,
                quantity=quantity,
                unit_price=unit_price,  # Prezzo originale senza sconto
                total_amount=total_amount  # Totale con sconto applicato (SENZA IVA)
            )
            self.db.add(detail)
            total_details_amount += total_amount
        
        # Recupera spese di spedizione e calcola IVA separatamente
        shipping_cost_no_vat = 0.0
        shipping_vat_amount = 0.0
        if order.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping:
                shipping_cost_no_vat = shipping.price_tax_excl or 0.0
                # Recupera la percentuale IVA per le spese di spedizione
                shipping_vat_percentage = self._get_vat_percentage_from_shipping(shipping)
                shipping_vat_amount = shipping_cost_no_vat * (shipping_vat_percentage / 100)
        
        # Calcola total_amount del documento: somma dettagli SENZA IVA + spese SENZA IVA
        # Sottrai gli sconti dell'ordine (se presenti)
        total_imponibile = total_details_amount + shipping_cost_no_vat - (order.total_discounts or 0.0)
        
        # Recupera la percentuale IVA dai dettagli dell'ordine per i prodotti
        products_vat_percentage = self._get_vat_percentage_from_order_details(order_details)
        products_vat_amount = total_details_amount * (products_vat_percentage / 100)
        
        # Calcola il totale finale: imponibile + IVA prodotti + IVA spedizione
        total_with_vat = total_imponibile + products_vat_amount + shipping_vat_amount
        
        # Tronca a 2 decimali senza arrotondare (es. 1.190,82614 -> 1.190,82)
        total_with_vat_truncated = math.floor(total_with_vat * 100) / 100
        
        # Il total_amount della fattura è il totale CON IVA (troncato)
        invoice.total_amount = total_with_vat_truncated
        
        self.db.commit()
        self.db.refresh(invoice)
        
        return invoice
    
    def get_invoice_by_order(self, id_order: int) -> Optional[FiscalDocument]:
        """Recupera la prima fattura di un ordine (deprecato, usare get_invoices_by_order)"""
        return self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_order == id_order,
                FiscalDocument.document_type == 'invoice'
            )
        ).first()
    
    def get_invoices_by_order(self, id_order: int) -> List[FiscalDocument]:
        """Recupera tutte le fatture di un ordine"""
        return self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_order == id_order,
                FiscalDocument.document_type == 'invoice'
            )
        ).all()
    
    # ==================== NOTE DI CREDITO ====================
    
    def create_credit_note(
        self, 
        id_invoice: int, 
        reason: str,
        is_partial: bool = False,
        items: Optional[List[Dict[str, Any]]] = None,
        is_electronic: bool = True
    ) -> FiscalDocument:
        """
        Crea una nota di credito per una fattura
        
        Args:
            id_invoice: ID della fattura di riferimento
            reason: Motivo della nota di credito
            is_partial: Se True, nota di credito parziale
            items: Lista di articoli da stornare (per NC parziali)
                   Formato: [{"id_order_detail": X, "quantity": Y, "unit_price": Z}, ...]
            is_electronic: Se True, genera XML elettronico
        
        Returns:
            FiscalDocument creato (nota di credito)
        """
        # Verifica che la fattura esista
        invoice = self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_fiscal_document == id_invoice,
                FiscalDocument.document_type == 'invoice'
            )
        ).first()
        
        if not invoice:
            raise ValueError(f"Fattura {id_invoice} non trovata")
        
        # Se is_electronic, verifica che la fattura sia elettronica
        if is_electronic and not invoice.is_electronic:
            raise ValueError("Non è possibile emettere nota di credito elettronica per fattura non elettronica")
        
        # Se is_electronic, verifica indirizzo italiano
        if is_electronic:
            # Recupera ID Italia da iso_code
            italy = self.db.query(Country).filter(Country.iso_code == 'IT').first()
            if not italy:
                raise ValueError("Paese Italia (IT) non trovato nel database")
            
            order = self.db.query(Order).filter(Order.id_order == invoice.id_order).first()
            address = self.db.query(Address).filter(Address.id_address == order.id_address_invoice).first()
            if not address or address.id_country != italy.id_country:
                raise ValueError("La nota di credito elettronica può essere emessa solo per indirizzi italiani")
        
        # Genera numero documento se elettronico
        document_number = None
        tipo_documento_fe = None
        
        if is_electronic:
            document_number = self._get_next_electronic_number('credit_note')
            tipo_documento_fe = 'TD04'
        
        # Recupera articoli della fattura
        invoice_details = self.db.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == id_invoice
        ).all()
        
        if not invoice_details:
            raise ValueError(f"Nessun articolo trovato nella fattura {id_invoice}")
        
        invoice_order_detail_ids = {d.id_order_detail for d in invoice_details}
        invoice_details_map = {d.id_order_detail: d for d in invoice_details}
        
        # Calcola importo totale (SENZA IVA)
        total_amount_no_vat = 0.0
        
        if is_partial and items:
            # Valida che gli articoli siano nella fattura
            for item in items:
                id_order_detail = item.get('id_order_detail')
                if id_order_detail not in invoice_order_detail_ids:
                    raise ValueError(f"OrderDetail {id_order_detail} non presente nella fattura {id_invoice}")
                
                # Verifica che la quantità non superi quella fatturata
                invoice_detail = invoice_details_map[id_order_detail]
                if item.get('quantity', 0) > invoice_detail.quantity:
                    raise ValueError(f"Quantità da stornare ({item['quantity']}) superiore a quella fatturata ({invoice_detail.quantity})")
            
            # Somma importi degli articoli specificati (SENZA IVA)
            for item in items:
                qty = item.get('quantity', 0)
                price = item.get('unit_price', 0)
                
                # Recupera order_detail per sconto
                od = self.db.query(OrderDetail).filter(
                    OrderDetail.id_order_detail == item['id_order_detail']
                ).first()
                
                # Calcola total con sconto (SENZA IVA)
                total_base = qty * price
                if od and od.reduction_percent and od.reduction_percent > 0:
                    sconto = total_base * (od.reduction_percent / 100)
                    total_no_vat = total_base - sconto
                elif od and od.reduction_amount and od.reduction_amount > 0:
                    total_no_vat = total_base - od.reduction_amount
                else:
                    total_no_vat = total_base
                    
                total_amount_no_vat += total_no_vat
        else:
            # Nota di credito totale = somma di tutti gli articoli fatturati (SENZA IVA)
            total_amount_no_vat = sum(d.total_amount for d in invoice_details)
            
            # Aggiungi anche spese di spedizione SENZA IVA per note di credito totali
            shipping_cost_no_vat = 0.0
            if order.id_shipping:
                shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
                if shipping:
                    shipping_cost_no_vat = shipping.price_tax_excl or 0.0
                    total_amount_no_vat += shipping_cost_no_vat
        
        # Applica la stessa logica dell'invoice: sottrai sconti e applica IVA separatamente
        total_imponibile = total_amount_no_vat - (order.total_discounts or 0.0)
        
        # Calcola IVA per i prodotti
        order_details = self.db.query(OrderDetail).filter(OrderDetail.id_order == order.id_order).all()
        products_vat_percentage = self._get_vat_percentage_from_order_details(order_details)
        products_vat_amount = (total_amount_no_vat - shipping_cost_no_vat) * (products_vat_percentage / 100)
        
        # Calcola IVA per le spese di spedizione
        shipping_vat_amount = 0.0
        if order.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping:
                shipping_vat_percentage = self._get_vat_percentage_from_shipping(shipping)
                shipping_vat_amount = shipping_cost_no_vat * (shipping_vat_percentage / 100)
        
        # Calcola il totale finale: imponibile + IVA prodotti + IVA spedizione
        total_with_vat = total_imponibile + products_vat_amount + shipping_vat_amount
        
        # Tronca a 2 decimali senza arrotondare (es. 1.190,82614 -> 1.190,82)
        total_with_vat_truncated = math.floor(total_with_vat * 100) / 100
        
        # Crea nota di credito
        credit_note = FiscalDocument(
            document_type='credit_note',
            tipo_documento_fe=tipo_documento_fe,
            id_order=invoice.id_order,
            id_fiscal_document_ref=id_invoice,
            document_number=document_number,
            is_electronic=is_electronic,
            status='pending',
            credit_note_reason=reason,
            is_partial=is_partial,
            total_amount=total_with_vat  # Totale CON IVA
        )
        
        self.db.add(credit_note)
        self.db.flush()
        
        # Se parziale, aggiungi dettagli
        if is_partial and items:
            for item in items:
                # Recupera order_detail per applicare lo sconto corretto
                od = self.db.query(OrderDetail).filter(
                    OrderDetail.id_order_detail == item['id_order_detail']
                ).first()
                
                unit_price = item['unit_price']
                quantity = item['quantity']
                total_base = unit_price * quantity
                
                # Applica sconti se presenti nell'order_detail
                if od and od.reduction_percent and od.reduction_percent > 0:
                    sconto = total_base * (od.reduction_percent / 100)
                    total_amount = total_base - sconto
                elif od and od.reduction_amount and od.reduction_amount > 0:
                    total_amount = total_base - od.reduction_amount
                else:
                    total_amount = total_base
                
                detail = FiscalDocumentDetail(
                    id_fiscal_document=credit_note.id_fiscal_document,
                    id_order_detail=item['id_order_detail'],
                    quantity=quantity,
                    unit_price=unit_price,  # Prezzo originale senza sconto
                    total_amount=total_amount  # Totale con sconto applicato
                )
                self.db.add(detail)
        
        self.db.commit()
        self.db.refresh(credit_note)
        
        return credit_note
    
    def get_credit_notes_by_invoice(self, id_invoice: int) -> List[FiscalDocument]:
        """Recupera tutte le note di credito di una fattura"""
        return self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_fiscal_document_ref == id_invoice,
                FiscalDocument.document_type == 'credit_note'
            )
        ).all()
    
    # ==================== UTILITY ====================
    
    def _get_vat_percentage_from_order_details(self, order_details) -> float:
        """
        Recupera la percentuale IVA dai dettagli dell'ordine.
        Se ci sono più tax diverse, usa la più comune o la prima trovata.
        
        Args:
            order_details: Lista di OrderDetail
            
        Returns:
            float: Percentuale IVA (es. 22.0 per 22%)
        """
        if not order_details:
            return 22.0  # Default 22%
        
        # Recupera gli id_tax unici dai dettagli
        tax_ids = [od.id_tax for od in order_details if od.id_tax]
        
        if not tax_ids:
            return 22.0  # Default 22%
        
        # Usa il primo id_tax trovato (potresti voler implementare una logica più sofisticata)
        first_tax_id = tax_ids[0]
        
        # Recupera la percentuale dalla tabella Tax
        from src.models.tax import Tax
        tax = self.db.query(Tax).filter(Tax.id_tax == first_tax_id).first()
        
        if tax and tax.percentage:
            return float(tax.percentage)
        
        return 22.0  # Default 22%
    
    def _get_vat_percentage_from_shipping(self, shipping) -> float:
        """
        Recupera la percentuale IVA per le spese di spedizione.
        
        Args:
            shipping: Oggetto Shipping
            
        Returns:
            float: Percentuale IVA (es. 22.0 per 22%)
        """
        if not shipping or not shipping.id_tax:
            return 22.0  # Default 22%
        
        # Recupera la percentuale dalla tabella Tax
        from src.models.tax import Tax
        tax = self.db.query(Tax).filter(Tax.id_tax == shipping.id_tax).first()
        
        if tax and tax.percentage:
            return float(tax.percentage)
        
        return 22.0  # Default 22%
    
    def _get_next_electronic_number(self, doc_type: str) -> str:
        """
        Genera il prossimo numero sequenziale per documenti elettronici
        
        Args:
            doc_type: 'invoice' o 'credit_note'
        
        Returns:
            Numero sequenziale come stringa (es. "000123")
        """
        # Recupera l'ultimo numero elettronico per questo tipo
        last_doc = self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.document_type == doc_type,
                FiscalDocument.is_electronic == True,
                FiscalDocument.document_number.isnot(None)
            )
        ).order_by(desc(FiscalDocument.id_fiscal_document)).first()
        
        if last_doc and last_doc.document_number:
            try:
                last_number = int(last_doc.document_number)
                next_number = last_number + 1
            except ValueError:
                next_number = 1
        else:
            next_number = 1
        
        return f"{next_number:06d}"
    
    def get_fiscal_document_by_id(self, id_fiscal_document: int) -> Optional[FiscalDocument]:
        """Recupera documento fiscale per ID"""
        return self.db.query(FiscalDocument).filter(
            FiscalDocument.id_fiscal_document == id_fiscal_document
        ).first()
    
    def get_fiscal_documents(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        document_type: Optional[str] = None,
        is_electronic: Optional[bool] = None,
        status: Optional[str] = None
    ) -> List[FiscalDocument]:
        """
        Recupera lista documenti fiscali con filtri
        
        Args:
            skip: Offset per paginazione
            limit: Limite risultati
            document_type: Filtra per tipo ('invoice', 'credit_note')
            is_electronic: Filtra per elettronici/non elettronici
            status: Filtra per status
        """
        query = self.db.query(FiscalDocument)
        
        if document_type:
            query = query.filter(FiscalDocument.document_type == document_type)
        
        if is_electronic is not None:
            query = query.filter(FiscalDocument.is_electronic == is_electronic)
        
        if status:
            query = query.filter(FiscalDocument.status == status)
        
        return query.order_by(desc(FiscalDocument.date_add)).offset(skip).limit(limit).all()
    
    def update_fiscal_document_status(
        self, 
        id_fiscal_document: int, 
        status: str, 
        upload_result: Optional[str] = None
    ) -> Optional[FiscalDocument]:
        """Aggiorna status di un documento fiscale"""
        doc = self.get_fiscal_document_by_id(id_fiscal_document)
        
        if not doc:
            return None
        
        doc.status = status
        if upload_result:
            doc.upload_result = upload_result
        
        self.db.commit()
        self.db.refresh(doc)
        
        return doc
    
    def update_fiscal_document_xml(
        self, 
        id_fiscal_document: int, 
        filename: str, 
        xml_content: str
    ) -> Optional[FiscalDocument]:
        """Aggiorna XML di un documento fiscale"""
        doc = self.get_fiscal_document_by_id(id_fiscal_document)
        
        if not doc:
            return None
        
        doc.filename = filename
        doc.xml_content = xml_content
        doc.status = 'generated'
        
        self.db.commit()
        self.db.refresh(doc)
        
        return doc
    
    def delete_fiscal_document(self, id_fiscal_document: int) -> bool:
        """Elimina documento fiscale (solo se pending)"""
        doc = self.get_fiscal_document_by_id(id_fiscal_document)
        
        if not doc:
            return False
        
        if doc.status != 'pending':
            raise ValueError("Non è possibile eliminare un documento già generato/inviato")
        
        # Verifica che non ci siano note di credito collegate
        if doc.document_type == 'invoice':
            credit_notes = self.get_credit_notes_by_invoice(id_fiscal_document)
            if credit_notes:
                raise ValueError("Non è possibile eliminare una fattura con note di credito collegate")
        
        self.db.delete(doc)
        self.db.commit()
        
        return True
