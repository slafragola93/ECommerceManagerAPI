from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import math

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.address import Address
from src.models.country import Country
from src.models.shipping import Shipping
from src.services.tool import calculate_amount_with_percentage


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
        
        
        # Determina status iniziale
        # - 'pending': fatture elettroniche in attesa di generazione XML
        # - 'issued': fatture non elettroniche già emesse manualmente
        initial_status = 'pending' if is_electronic else 'issued'
        
        invoice = FiscalDocument(
            document_type='invoice',
            tipo_documento_fe=tipo_documento_fe,
            id_order=id_order,
            document_number=document_number,
            is_electronic=is_electronic,
            status=initial_status,
            includes_shipping=True,  # Le fatture includono sempre le spese di spedizione
            total_amount=order.total_paid  # Verrà aggiornato dopo aver creato i dettagli
        )
        
        self.db.add(invoice)
        self.db.flush()  # Per ottenere id_fiscal_document
        
        # Crea fiscal_document_details per ogni order_detail dell'ordine
        order_details = self.db.query(OrderDetail).filter(
            OrderDetail.id_order == id_order
        ).all()
                
        for od in order_details:
            # unit_price: prezzo unitario originale senza alterazioni
            unit_price = od.product_price or 0.0
            quantity = od.product_qty or 0
            
            # Calcola total_amount applicando gli sconti
            total_base = unit_price * quantity
            
            # Applica sconti a total_amount
            if od.reduction_percent and od.reduction_percent > 0:
                sconto = calculate_amount_with_percentage(total_base, od.reduction_percent)
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
    
    def _validate_credit_note_creation(
        self,
        invoice: FiscalDocument,
        invoice_details: List[FiscalDocumentDetail],
        is_partial: bool,
        items: Optional[List[Dict[str, Any]]],
        include_shipping: bool
    ) -> None:
        """
        Valida la creazione di una nota di credito
        
        Args:
            invoice: Fattura di riferimento
            invoice_details: Dettagli della fattura
            is_partial: Se True, nota parziale
            items: Articoli da stornare (per note parziali)
            include_shipping: Se True, vuole includere spese di spedizione
            
        Raises:
            ValueError: Se i controlli falliscono
        """
        # Recupera tutte le note di credito esistenti per questa fattura
        existing_credit_notes = self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_fiscal_document_ref == invoice.id_fiscal_document,
                FiscalDocument.document_type == 'credit_note'
            )
        ).all()
        
        # CONTROLLO 1: Verifica se esiste già una nota di credito TOTALE
        total_credit_note_exists = any(cn for cn in existing_credit_notes if not cn.is_partial)
        if total_credit_note_exists:
            raise ValueError(
                f"Esiste già una nota di credito TOTALE per la fattura {invoice.id_fiscal_document}. "
                "Non è possibile creare altre note di credito."
            )
        
        # CONTROLLO 2: Se ci sono note parziali, verifica articoli già stornati
        if existing_credit_notes and is_partial and items:
            # Recupera tutti gli articoli già stornati dalle note precedenti
            already_refunded_details = self.db.query(FiscalDocumentDetail).filter(
                FiscalDocumentDetail.id_fiscal_document.in_([cn.id_fiscal_document for cn in existing_credit_notes])
            ).all()
            
            # Mappa: id_order_detail → quantità totale già stornata
            refunded_quantities = {}
            for detail in already_refunded_details:
                if detail.id_order_detail in refunded_quantities:
                    refunded_quantities[detail.id_order_detail] += detail.quantity
                else:
                    refunded_quantities[detail.id_order_detail] = detail.quantity
            
            # Verifica ogni articolo da stornare
            for item in items:
                id_order_detail = item.get('id_order_detail')
                quantity_to_refund = item.get('quantity', 0)
                
                # Recupera quantità originale dalla fattura
                invoice_detail = next((d for d in invoice_details if d.id_order_detail == id_order_detail), None)
                if not invoice_detail:
                    continue
                
                # Verifica se l'articolo è già stato completamente stornato
                already_refunded = refunded_quantities.get(id_order_detail, 0)
                remaining_quantity = invoice_detail.quantity - already_refunded
                
                if remaining_quantity <= 0:
                    raise ValueError(
                        f"L'articolo {id_order_detail} è già stato completamente stornato "
                        f"(quantità fatturata: {invoice_detail.quantity}, già stornata: {already_refunded})"
                    )
                
                if quantity_to_refund > remaining_quantity:
                    raise ValueError(
                        f"Quantità da stornare ({quantity_to_refund}) superiore alla quantità residua ({remaining_quantity}) "
                        f"per l'articolo {id_order_detail} (già stornate: {already_refunded})"
                    )
        
        # CONTROLLO 3: Verifica se le spese di spedizione sono già state stornate
        if existing_credit_notes and include_shipping:
            # Verifica se in qualche nota di credito precedente le spese sono già state incluse
            shipping_already_refunded = any(cn.includes_shipping for cn in existing_credit_notes)
            if shipping_already_refunded:
                raise ValueError(
                    "Le spese di spedizione sono già state stornate in una nota di credito precedente. "
                    "Imposta include_shipping=False per procedere."
                )
    
    def create_credit_note(
        self, 
        id_invoice: int, 
        reason: str,
        is_partial: bool = False,
        items: Optional[List[Dict[str, Any]]] = None,
        is_electronic: bool = True,
        include_shipping: bool = True
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
            include_shipping: Se True, include spese di spedizione (default: True)
        
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
        
        # Recupera articoli della fattura (serve per i controlli)
        invoice_details = self.db.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == id_invoice
        ).all()
        
        if not invoice_details:
            raise ValueError(f"Nessun articolo trovato nella fattura {id_invoice}")
        
        invoice_order_detail_ids = {d.id_order_detail for d in invoice_details}
        invoice_details_map = {d.id_order_detail: d for d in invoice_details}
        
        # ==================== VALIDAZIONE NOTE DI CREDITO ====================
        self._validate_credit_note_creation(invoice, invoice_details, is_partial, items, include_shipping)
        
        # Genera numero documento se elettronico
        document_number = None
        tipo_documento_fe = None
        
        if is_electronic:
            document_number = self._get_next_electronic_number('credit_note')
            tipo_documento_fe = 'TD04'
        
        # Prepara i dettagli della nota di credito PRIMA di calcolare il totale
        credit_note_details_data = []
        
        if is_partial and items:
            # NOTA PARZIALE: Prepara i dettagli degli articoli specificati
            # USA i valori già salvati in FiscalDocumentDetail della fattura (non ricalcolare sconti!)
            for item in items:
                id_order_detail = item.get('id_order_detail')
                
                # Validazioni
                if id_order_detail not in invoice_order_detail_ids:
                    raise ValueError(f"OrderDetail {id_order_detail} non presente nella fattura {id_invoice}")
                
                invoice_detail = invoice_details_map[id_order_detail]
                quantity_to_refund = item.get('quantity', 0)
                
                if quantity_to_refund > invoice_detail.quantity:
                    raise ValueError(f"Quantità da stornare ({quantity_to_refund}) superiore a quella fatturata ({invoice_detail.quantity})")
                
                # USA i valori dalla fattura (già contengono sconti applicati)
                unit_price = invoice_detail.unit_price  # Prezzo unitario originale
                
                # Calcola total_amount proporzionale
                # invoice_detail.total_amount è già scontato per invoice_detail.quantity
                # Calcolo proporzionale: (total_fatturato / qty_fatturata) × qty_da_stornare
                if invoice_detail.quantity > 0:
                    total_amount = (invoice_detail.total_amount / invoice_detail.quantity) * quantity_to_refund
                else:
                    total_amount = 0.0
                
                credit_note_details_data.append({
                    'id_order_detail': id_order_detail,
                    'quantity': quantity_to_refund,
                    'unit_price': unit_price,
                    'total_amount': total_amount  # Imponibile proporzionale (già scontato)
                })
        else:
            # NOTA TOTALE: Prepara dettagli SOLO degli articoli NON ancora stornati completamente
            # Recupera le note di credito esistenti per calcolare quantità residue
            existing_credit_notes = self.db.query(FiscalDocument).filter(
                and_(
                    FiscalDocument.id_fiscal_document_ref == id_invoice,
                    FiscalDocument.document_type == 'credit_note'
                )
            ).all()
            
            # Calcola quantità già stornate per ogni articolo
            refunded_quantities = {}
            if existing_credit_notes:
                already_refunded_details = self.db.query(FiscalDocumentDetail).filter(
                    FiscalDocumentDetail.id_fiscal_document.in_([cn.id_fiscal_document for cn in existing_credit_notes])
                ).all()
                
                for detail in already_refunded_details:
                    if detail.id_order_detail in refunded_quantities:
                        refunded_quantities[detail.id_order_detail] += detail.quantity
                    else:
                        refunded_quantities[detail.id_order_detail] = detail.quantity
            
            # Prepara dettagli solo per articoli con quantità residua
            # USA i valori già salvati in FiscalDocumentDetail della fattura (non ricalcolare sconti!)
            for invoice_detail in invoice_details:
                id_order_detail = invoice_detail.id_order_detail
                original_quantity = invoice_detail.quantity
                already_refunded = refunded_quantities.get(id_order_detail, 0)
                remaining_quantity = original_quantity - already_refunded
                
                # Includi solo se c'è quantità residua
                if remaining_quantity > 0:
                    # USA i valori dalla fattura (già contengono sconti applicati)
                    unit_price = invoice_detail.unit_price  # Prezzo unitario originale
                    
                    # Calcola total_amount proporzionale
                    # invoice_detail.total_amount è già scontato per invoice_detail.quantity
                    # Calcolo proporzionale: (total_fatturato / qty_fatturata) × qty_residua
                    if original_quantity > 0:
                        total_amount = (invoice_detail.total_amount / original_quantity) * remaining_quantity
                    else:
                        total_amount = 0.0
                    
                    credit_note_details_data.append({
                        'id_order_detail': id_order_detail,
                        'quantity': remaining_quantity,  # Quantità residua
                        'unit_price': unit_price,
                        'total_amount': total_amount  # Imponibile proporzionale (già scontato)
                    })
        
        # Verifica che ci siano articoli da stornare
        if not credit_note_details_data:
            raise ValueError(
                "Nessun articolo residuo da stornare. "
                "Tutti gli articoli della fattura sono già stati completamente stornati in note di credito precedenti."
            )
        
        # Calcola il totale IMPONIBILE (senza IVA) dai dettagli preparati (solo prodotti)
        total_imponibile_prodotti = sum(d['total_amount'] for d in credit_note_details_data)
        
        # Aggiungi spese di spedizione se richieste
        shipping_cost_no_vat = 0.0
        shipping_vat_amount = 0.0
        
        if include_shipping:
            order = self.db.query(Order).filter(Order.id_order == invoice.id_order).first()
            if order and order.id_shipping:
                shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
                if shipping and shipping.price_tax_excl and shipping.price_tax_excl > 0:
                    shipping_cost_no_vat = shipping.price_tax_excl
                    # Calcola IVA spedizione
                    shipping_vat_percentage = self._get_vat_percentage_from_shipping(shipping)
                    shipping_vat_amount = calculate_amount_with_percentage(shipping_cost_no_vat, shipping_vat_percentage)
                    print(f"Spese spedizione: {shipping_cost_no_vat}€ (IVA {shipping_vat_percentage}% = {shipping_vat_amount}€)")
        
        # Totale imponibile (prodotti + spedizione)
        total_imponibile = total_imponibile_prodotti + shipping_cost_no_vat
        
        # Recupera l'aliquota IVA dei prodotti
        first_detail_id = credit_note_details_data[0]['id_order_detail']
        od_first = self.db.query(OrderDetail).filter(OrderDetail.id_order_detail == first_detail_id).first()
        
        # Calcola l'IVA sui prodotti
        vat_percentage = self._get_vat_percentage_from_order_details([od_first]) 
        print(f"vat_percentage prodotti: {vat_percentage}")
        products_vat_amount = calculate_amount_with_percentage(total_imponibile_prodotti, vat_percentage)
        print(f"IVA prodotti: {products_vat_amount}")
        
        # Totale IVA (prodotti + spedizione)
        total_vat_amount = products_vat_amount + shipping_vat_amount
        
        # Totale con IVA (imponibile + IVA)
        total_with_vat = total_imponibile + total_vat_amount
        print(f"TOTALE NC: Imponibile={total_imponibile}€, IVA={total_vat_amount}€, Totale={total_with_vat}€")
        
        # Determina status iniziale
        # - 'pending': note elettroniche in attesa di generazione XML
        # - 'issued': note non elettroniche già emesse manualmente
        initial_status = 'pending' if is_electronic else 'issued'
        
        # Crea nota di credito
        credit_note = FiscalDocument(
            document_type='credit_note',
            tipo_documento_fe=tipo_documento_fe,
            id_order=invoice.id_order,
            id_fiscal_document_ref=id_invoice,
            document_number=document_number,
            is_electronic=is_electronic,
            status=initial_status,
            credit_note_reason=reason,
            is_partial=is_partial,
            includes_shipping=include_shipping,  # Traccia se include spese di spedizione
            total_amount=total_with_vat  # Totale CON IVA calcolato dai dettagli residui + spese
        )
        
        self.db.add(credit_note)
        self.db.flush()
        
        # Crea i FiscalDocumentDetail usando i dati già preparati
        for detail_data in credit_note_details_data:
            detail = FiscalDocumentDetail(
                id_fiscal_document=credit_note.id_fiscal_document,
                id_order_detail=detail_data['id_order_detail'],
                quantity=detail_data['quantity'],
                unit_price=detail_data['unit_price'],
                total_amount=detail_data['total_amount']  # Imponibile (senza IVA)
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
