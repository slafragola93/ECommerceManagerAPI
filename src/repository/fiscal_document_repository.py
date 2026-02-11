from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
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
from src.models.tax import Tax
from src.services.core.tool import (
    calculate_amount_with_percentage,
    calculate_price_with_tax,
    calculate_price_without_tax
)
from src.core.base_repository import BaseRepository
from src.repository.interfaces.fiscal_document_repository_interface import IFiscalDocumentRepository
from src.core.exceptions import ValidationException, NotFoundException, BusinessRuleException
from src.repository.tax_repository import TaxRepository


class FiscalDocumentRepository(BaseRepository[FiscalDocument, int], IFiscalDocumentRepository):
    def __init__(self, session: Session):
        super().__init__(session, FiscalDocument)
        self._tax_repository = TaxRepository(session)
    
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
        order = self._session.query(Order).filter(Order.id_order == id_order).first()
        if not order:
            raise ValueError(f"Ordine {id_order} non trovato")
        
        # Se is_electronic=True, verifica che l'indirizzo sia italiano
        if is_electronic:
            # Recupera ID Italia da iso_code
            italy = self._session.query(Country).filter(Country.iso_code == 'IT').first()
            if not italy:
                raise ValueError("Paese Italia (IT) non trovato nel database")
            
            address = self._session.query(Address).filter(Address.id_address == order.id_address_invoice).first()
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
            id_store=order.id_store,  # Porta id_store dall'ordine
            document_number=document_number,
            is_electronic=is_electronic,
            status=initial_status,
            includes_shipping=True,  # Le fatture includono sempre le spese di spedizione
            total_price_with_tax=order.total_price_with_tax  # Verrà aggiornato dopo aver creato i dettagli
        )
        
        self._session.add(invoice)
        self._session.flush()  # Per ottenere id_fiscal_document
        
        # Crea fiscal_document_details per ogni order_detail dell'ordine
        order_details = self._session.query(OrderDetail).filter(
            OrderDetail.id_order == id_order
        ).all()
                
        for od in order_details:
            # Usa i nuovi campi se disponibili, altrimenti calcola da product_price per retrocompatibilità
            # Converti Decimal in float per evitare errori di tipo
            unit_price_net = float(od.unit_price_net or od.product_price or 0.0)
            unit_price_with_tax = float(od.unit_price_with_tax or 0.0)
            quantity = int(od.product_qty or 0)
            
            # Se unit_price_with_tax non è disponibile, calcolalo da unit_price_net usando id_tax
            if unit_price_with_tax == 0.0 and unit_price_net > 0 and od.id_tax:
                tax = self._tax_repository.get_tax_by_id(od.id_tax)
                tax_percentage = float(tax.percentage) if tax and tax.percentage is not None else None
                if tax_percentage is not None:
                    tax_percentage = float(tax_percentage)
                    unit_price_with_tax = calculate_price_with_tax(unit_price_net, tax_percentage, quantity=1)
                else:
                    unit_price_with_tax = unit_price_net  # Fallback se tax non trovata
            
            # Calcola total_price_net applicando gli sconti
            total_base = unit_price_net * quantity
            
            # Applica sconti
            if od.reduction_percent and od.reduction_percent > 0:
                reduction_percent = float(od.reduction_percent)
                sconto = calculate_amount_with_percentage(total_base, reduction_percent)
                total_price_net = total_base - sconto
            elif od.reduction_amount and od.reduction_amount > 0:
                reduction_amount = float(od.reduction_amount)
                total_price_net = total_base - reduction_amount
            else:
                total_price_net = total_base
            
            # Calcola total_price_with_tax usando la percentuale di id_tax
            total_price_with_tax = total_price_net
            if od.id_tax:
                tax = self._tax_repository.get_tax_by_id(od.id_tax)
                tax_percentage = float(tax.percentage) if tax and tax.percentage is not None else None
                if tax_percentage is not None:
                    tax_percentage = float(tax_percentage)
                    total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            
            # IMPORTANTE:
            # - unit_price_net: prezzo unitario ORIGINALE (no sconto, senza IVA)
            # - unit_price_with_tax: prezzo unitario ORIGINALE (no sconto, con IVA)
            # - total_price_net: totale riga SCONTATO (unit_price_net × qty - sconto), SENZA IVA
            # - total_price_with_tax: totale riga SCONTATO con IVA = total_price_net × (1 + tax_percentage/100)
            
            detail = FiscalDocumentDetail(
                id_fiscal_document=invoice.id_fiscal_document,
                id_order_detail=od.id_order_detail,
                product_qty=quantity,
                unit_price_net=unit_price_net,  # Prezzo originale senza sconto, senza IVA
                unit_price_with_tax=unit_price_with_tax,  # Prezzo originale senza sconto, con IVA
                total_price_net=total_price_net,  # Totale con sconto applicato, senza IVA
                total_price_with_tax=total_price_with_tax,  # Totale con sconto applicato, con IVA
                id_tax=od.id_tax
            )
            
            self._session.add(detail)

        self._session.flush()
        self.recalculate_fiscal_document_total(invoice.id_fiscal_document)
        self._session.refresh(invoice)

        return invoice
    
    def get_invoice_by_order(self, id_order: int) -> Optional[FiscalDocument]:
        """Recupera la prima fattura di un ordine (deprecato, usare get_invoices_by_order)"""
        return self._session.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_order == id_order,
                FiscalDocument.document_type == 'invoice'
            )
        ).first()
    
    def get_invoices_by_order(self, id_order: int) -> List[FiscalDocument]:
        """Recupera tutte le fatture di un ordine"""
        return self._session.query(FiscalDocument).filter(
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
        existing_credit_notes = self._session.query(FiscalDocument).filter(
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
            already_refunded_details = self._session.query(FiscalDocumentDetail).filter(
                FiscalDocumentDetail.id_fiscal_document.in_([cn.id_fiscal_document for cn in existing_credit_notes])
            ).all()
            
            # Mappa: id_order_detail → quantità totale già stornata
            refunded_quantities = {}
            for detail in already_refunded_details:
                if detail.id_order_detail in refunded_quantities:
                    refunded_quantities[detail.id_order_detail] += detail.product_qty
                else:
                    refunded_quantities[detail.id_order_detail] = detail.product_qty
            
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
                remaining_quantity = invoice_detail.product_qty - already_refunded
                
                if remaining_quantity <= 0:
                    raise ValueError(
                        f"L'articolo {id_order_detail} è già stato completamente stornato "
                        f"(quantità fatturata: {invoice_detail.product_qty}, già stornata: {already_refunded})"
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
        invoice = self._session.query(FiscalDocument).filter(
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
            italy = self._session.query(Country).filter(Country.iso_code == 'IT').first()
            if not italy:
                raise ValueError("Paese Italia (IT) non trovato nel database")
            
            order = self._session.query(Order).filter(Order.id_order == invoice.id_order).first()
            address = self._session.query(Address).filter(Address.id_address == order.id_address_invoice).first()
            if not address or address.id_country != italy.id_country:
                raise ValueError("La nota di credito elettronica può essere emessa solo per indirizzi italiani")
        
        # Recupera articoli della fattura (serve per i controlli)
        invoice_details = self._session.query(FiscalDocumentDetail).filter(
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
                
                if quantity_to_refund > invoice_detail.product_qty:
                    raise ValueError(f"Quantità da stornare ({quantity_to_refund}) superiore a quella fatturata ({invoice_detail.product_qty})")
                
                # USA i valori dalla fattura (già contengono sconti applicati)
                unit_price_net = invoice_detail.unit_price_net or invoice_detail.unit_price or 0.0
                unit_price_with_tax = invoice_detail.unit_price_with_tax or 0.0
                
                # Calcola totali proporzionali
                # invoice_detail.total_price_net e total_price_with_tax sono già scontati per invoice_detail.product_qty
                # Calcolo proporzionale: (total_fatturato / qty_fatturata) × qty_da_stornare
                if invoice_detail.product_qty > 0:
                    total_price_net = (invoice_detail.total_price_net / invoice_detail.product_qty) * quantity_to_refund
                    total_price_with_tax = (invoice_detail.total_price_with_tax / invoice_detail.product_qty) * quantity_to_refund
                else:
                    total_price_net = 0.0
                    total_price_with_tax = 0.0
                
                credit_note_details_data.append({
                    'id_order_detail': id_order_detail,
                    'quantity': quantity_to_refund,
                    'unit_price_net': unit_price_net,
                    'unit_price_with_tax': unit_price_with_tax,
                    'total_price_net': total_price_net,
                    'total_price_with_tax': total_price_with_tax,
                    'id_tax': invoice_detail.id_tax
                })
        else:
            # NOTA TOTALE: Prepara dettagli SOLO degli articoli NON ancora stornati completamente
            # Recupera le note di credito esistenti per calcolare quantità residue
            existing_credit_notes = self._session.query(FiscalDocument).filter(
                and_(
                    FiscalDocument.id_fiscal_document_ref == id_invoice,
                    FiscalDocument.document_type == 'credit_note'
                )
            ).all()
            
            # Calcola quantità già stornate per ogni articolo
            refunded_quantities = {}
            if existing_credit_notes:
                already_refunded_details = self._session.query(FiscalDocumentDetail).filter(
                    FiscalDocumentDetail.id_fiscal_document.in_([cn.id_fiscal_document for cn in existing_credit_notes])
                ).all()
                
                for detail in already_refunded_details:
                    if detail.id_order_detail in refunded_quantities:
                        refunded_quantities[detail.id_order_detail] += detail.product_qty
                    else:
                        refunded_quantities[detail.id_order_detail] = detail.product_qty
            
            # Prepara dettagli solo per articoli con quantità residua
            # USA i valori già salvati in FiscalDocumentDetail della fattura (non ricalcolare sconti!)
            for invoice_detail in invoice_details:
                id_order_detail = invoice_detail.id_order_detail
                original_quantity = invoice_detail.product_qty
                already_refunded = refunded_quantities.get(id_order_detail, 0)
                remaining_quantity = original_quantity - already_refunded
                
                # Includi solo se c'è quantità residua
                if remaining_quantity > 0:
                    # USA i valori dalla fattura (già contengono sconti applicati)
                    unit_price_net = invoice_detail.unit_price_net or invoice_detail.unit_price or 0.0
                    unit_price_with_tax = invoice_detail.unit_price_with_tax or 0.0
                    
                    # Calcola totali proporzionali
                    # invoice_detail.total_price_net e total_price_with_tax sono già scontati per invoice_detail.product_qty
                    # Calcolo proporzionale: (total_fatturato / qty_fatturata) × qty_residua
                    if original_quantity > 0:
                        total_price_net = (invoice_detail.total_price_net / original_quantity) * remaining_quantity
                        total_price_with_tax = (invoice_detail.total_price_with_tax / original_quantity) * remaining_quantity
                    else:
                        total_price_net = 0.0
                        total_price_with_tax = 0.0
                    
                    credit_note_details_data.append({
                        'id_order_detail': id_order_detail,
                        'quantity': remaining_quantity,  # Quantità residua
                        'unit_price_net': unit_price_net,
                        'unit_price_with_tax': unit_price_with_tax,
                        'total_price_net': total_price_net,
                        'total_price_with_tax': total_price_with_tax,
                        'id_tax': invoice_detail.id_tax
                    })
        
        # Verifica che ci siano articoli da stornare
        if not credit_note_details_data:
            raise ValueError(
                "Nessun articolo residuo da stornare. "
                "Tutti gli articoli della fattura sono già stati completamente stornati in note di credito precedenti."
            )
        
        # Calcola il totale IMPONIBILE (senza IVA) dai dettagli preparati (solo prodotti)
        total_imponibile_prodotti = sum(d['total_price_net'] for d in credit_note_details_data)
        
        # Aggiungi spese di spedizione se richieste
        shipping_cost_no_vat = 0.0
        shipping_vat_amount = 0.0
        
        if include_shipping:
            order = self._session.query(Order).filter(Order.id_order == invoice.id_order).first()
            if order and order.id_shipping:
                shipping = self._session.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
                if shipping and shipping.price_tax_excl and shipping.price_tax_excl > 0:
                    shipping_cost_no_vat = float(shipping.price_tax_excl)
                    # Calcola IVA spedizione
                    shipping_vat_percentage = self._get_vat_percentage_from_shipping(shipping)
                    shipping_vat_amount = calculate_amount_with_percentage(shipping_cost_no_vat, shipping_vat_percentage)
                    print(f"Spese spedizione: {shipping_cost_no_vat}€ (IVA {shipping_vat_percentage}% = {shipping_vat_amount}€)")
        
        # Totale imponibile (prodotti + spedizione)
        total_imponibile = total_imponibile_prodotti + shipping_cost_no_vat
        
        # Recupera l'aliquota IVA dei prodotti
        first_detail_id = credit_note_details_data[0]['id_order_detail']
        od_first = self._session.query(OrderDetail).filter(OrderDetail.id_order_detail == first_detail_id).first()
        
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
            id_store=invoice.id_store,  # Porta id_store dalla fattura di riferimento
            id_fiscal_document_ref=id_invoice,
            document_number=document_number,
            is_electronic=is_electronic,
            status=initial_status,
            credit_note_reason=reason,
            is_partial=is_partial,
            includes_shipping=include_shipping,  # Traccia se include spese di spedizione
            total_price_with_tax=total_with_vat  # Totale CON IVA calcolato dai dettagli residui + spese
        )
        
        self._session.add(credit_note)
        self._session.flush()
        
        # Crea i FiscalDocumentDetail usando i dati già preparati
        for detail_data in credit_note_details_data:
            detail = FiscalDocumentDetail(
                id_fiscal_document=credit_note.id_fiscal_document,
                id_order_detail=detail_data['id_order_detail'],
                product_qty=detail_data['quantity'],
                unit_price_net=detail_data.get('unit_price_net', 0.0),
                unit_price_with_tax=detail_data.get('unit_price_with_tax', 0.0),
                total_price_net=detail_data.get('total_price_net', 0.0),
                total_price_with_tax=detail_data.get('total_price_with_tax', 0.0),
                id_tax=detail_data.get('id_tax')
            )
            self._session.add(detail)
        
        self._session.flush()
        self.recalculate_fiscal_document_total(credit_note.id_fiscal_document)
        self._session.refresh(credit_note)
        return credit_note
    
    def get_credit_notes_by_invoice(self, id_invoice: int) -> List[FiscalDocument]:
        """Recupera tutte le note di credito di una fattura"""
        return self._session.query(FiscalDocument).filter(
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
        tax = self._tax_repository.get_tax_by_id(first_tax_id)
        tax_percentage = float(tax.percentage) if tax and tax.percentage is not None else None
        
        if tax_percentage is not None:
            return float(tax_percentage)
        
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
        tax = self._tax_repository.get_tax_by_id(shipping.id_tax)
        tax_percentage = float(tax.percentage) if tax and tax.percentage is not None else None
        
        if tax_percentage is not None:
            return float(tax_percentage)
        
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
        last_doc = self._session.query(FiscalDocument).filter(
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
        return self._session.query(FiscalDocument).filter(
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
        query = self._session.query(FiscalDocument)
        
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
        
        self._session.commit()
        self._session.refresh(doc)
        
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
        
        self._session.commit()
        self._session.refresh(doc)
        
        return doc
    
    def delete_fiscal_document(self, id_fiscal_document: int) -> bool:
        """Elimina documento fiscale (solo se pending)"""
        doc = self.get_fiscal_document_by_id(id_fiscal_document)
        
        if not doc:
            return False
        
        if doc.status != 'pending' and doc.document_type != 'return':
            raise ValueError("Non è possibile eliminare un documento già generato/inviato")
        
        # Verifica che non ci siano note di credito collegate
        if doc.document_type == 'invoice':
            credit_notes = self.get_credit_notes_by_invoice(id_fiscal_document)
            if credit_notes:
                raise ValueError("Non è possibile eliminare una fattura con note di credito collegate")
        
        self._session.delete(doc)
        self._session.commit()
        
        return True
    
    # ==================== RESI ====================
    
    def create_return(self, id_order: int, order_details: List[dict], includes_shipping: bool = False, note: Optional[str] = None) -> FiscalDocument:
        """
        Crea un reso per un ordine
        
        Args:
            id_order: ID dell'ordine
            order_details: Lista di dettagli da restituire [{"id_order_detail": X, "quantity": Y, "unit_price": Z}, ...]
            includes_shipping: Se includere spese di spedizione
            note: Note aggiuntive
        
        Returns:
            FiscalDocument creato (reso)
        """
        # Verifica che l'ordine esista
        order = self._session.query(Order).filter(Order.id_order == id_order).first()
        if not order:
            raise ValueError(f"Ordine {id_order} non trovato")
        
        # Valida gli articoli del reso
        self.validate_return_items(id_order, order_details)
        
        # Genera numero sequenziale per reso
        document_number = self.get_next_document_number('return')
        
        # Calcola il totale del reso
        total_amount = self.calculate_return_totals(order_details, includes_shipping, id_order)
        # Determina se il reso è parziale confrontando con le quantità totali dell'ordine
        original_order_details = self._session.query(OrderDetail).filter(OrderDetail.id_order == id_order).all()
        
        # Se non ci sono tutti gli articoli dell'ordine nel reso, è parziale
        if len(order_details) < len(original_order_details):
            is_partial = True
        else:
            # Controlla se per ogni articolo la quantità del reso è uguale alla quantità totale
            is_partial = False
            for item in order_details:
                original_detail = next((od for od in original_order_details if od.id_order_detail == item['id_order_detail']), None)
                if original_detail and item['quantity'] < original_detail.product_qty:
                    is_partial = True
                    break
        
        # Crea il documento reso
        return_doc = FiscalDocument(
            document_type='return',
            id_order=id_order,
            id_store=order.id_store,  # Porta id_store dall'ordine
            document_number=str(document_number),
            status='issued',
            is_electronic=False,  # I resi non sono elettronici per ora
            credit_note_reason=note,
            is_partial=is_partial,
            includes_shipping=includes_shipping,
            total_price_with_tax=total_amount
        )
        
        self._session.add(return_doc)
        self._session.flush()  # Per ottenere id_fiscal_document
        
        # Crea i dettagli del reso
        for item in order_details:            
            # Usa l'id_tax fornito o quello dell'ordine originale
            id_tax = item.get('id_tax')
            unit_price_net = item.get('unit_price_net', item.get('unit_price', 0.0))
            unit_price_with_tax = item.get('unit_price_with_tax', 0.0)
            quantity = item['quantity']
            
            # Calcola totali
            total_price_net = quantity * unit_price_net
            
            # Calcola total_price_with_tax usando la percentuale di id_tax
            total_price_with_tax = total_price_net
            if id_tax:
                tax = self._tax_repository.get_tax_by_id(id_tax)
                if tax and tax.percentage is not None:
                    tax_percentage = float(tax.percentage)
                    total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
            
            # Se unit_price_with_tax non è fornito, calcolalo
            if unit_price_with_tax == 0.0 and unit_price_net > 0 and id_tax:
                tax = self._tax_repository.get_tax_by_id(id_tax)
                if tax and tax.percentage is not None:
                    tax_percentage = float(tax.percentage)
                    unit_price_with_tax = calculate_price_with_tax(unit_price_net, tax_percentage, quantity=1)

            detail = FiscalDocumentDetail(
                id_fiscal_document=return_doc.id_fiscal_document,
                id_order_detail=item['id_order_detail'],
                product_qty=quantity,
                unit_price_net=unit_price_net,
                unit_price_with_tax=unit_price_with_tax,
                total_price_net=total_price_net,
                total_price_with_tax=total_price_with_tax,
                id_tax=id_tax
            )
            self._session.add(detail)
        
        self._session.flush()
        self.recalculate_fiscal_document_total(return_doc.id_fiscal_document)
        self._session.refresh(return_doc)
        return return_doc
    
    def update_fiscal_document_detail(self, id_detail: int, quantity: Optional[int] = None, unit_price: Optional[float] = None, id_tax: Optional[int] = None) -> FiscalDocumentDetail:
        """Aggiorna un dettaglio di documento fiscale e ricalcola il totale"""
        detail = self._session.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document_detail == id_detail
        ).first()
        
        if not detail:
            raise ValueError(f"Dettaglio {id_detail} non trovato")
        
        # Aggiorna i campi se forniti
        if quantity is not None:
            detail.product_qty = quantity
        if unit_price is not None:
            detail.unit_price_net = unit_price
        if id_tax is not None:
            detail.id_tax = id_tax
        
        # Ricalcola i totali
        unit_price_net = detail.unit_price_net or 0.0
        detail.total_price_net = detail.product_qty * unit_price_net
        
        # Calcola total_price_with_tax usando la percentuale di id_tax
        detail.total_price_with_tax = detail.total_price_net
        if detail.id_tax:
            tax = self._tax_repository.get_tax_by_id(detail.id_tax)
            tax_percentage = float(tax.percentage) if tax and tax.percentage is not None else None
            if tax_percentage is not None:
                tax_percentage = float(tax_percentage)
                detail.total_price_with_tax = calculate_price_with_tax(detail.total_price_net, tax_percentage, quantity=1)
        
        # Ricalcola il totale del documento fiscale
        self.recalculate_fiscal_document_total(detail.id_fiscal_document)
        
        self._session.commit()
        self._session.refresh(detail)
        
        return detail
    
    def delete_fiscal_document_detail(self, id_detail: int) -> bool:
        """Elimina un dettaglio di documento fiscale e ricalcola il totale"""
        detail = self._session.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document_detail == id_detail
        ).first()
        
        if not detail:
            return False
        
        fiscal_document_id = detail.id_fiscal_document
        
        self._session.delete(detail)
        self._session.commit()
        
        # Ricalcola il totale del documento fiscale
        self.recalculate_fiscal_document_total(fiscal_document_id)
        
        return True
    
    def recalculate_fiscal_document_total(self, id_fiscal_document: int) -> None:
        """Ricalcola il totale di un documento fiscale basato sui suoi dettagli"""
        fiscal_doc = self._session.query(FiscalDocument).filter(
            FiscalDocument.id_fiscal_document == id_fiscal_document
        ).first()
        
        if not fiscal_doc:
            return
        
        # Calcola il totale dai dettagli (solo prodotti)
        details = self._session.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == id_fiscal_document
        ).all()

        products_total_price_net = sum(float(d.total_price_net or 0) for d in details)
        products_total_price_with_tax = sum(float(d.total_price_with_tax or 0) for d in details)
        total_price_net = products_total_price_net
        total_price_with_tax = products_total_price_with_tax

        # Aggiungi spese di spedizione se incluse
        if fiscal_doc.includes_shipping:
            order_id_shipping = self._session.query(Order.id_shipping).filter(Order.id_order == fiscal_doc.id_order).scalar()
            if order_id_shipping:
                shipping = self._session.query(Shipping).filter(Shipping.id_shipping == order_id_shipping).first()
                if shipping:
                    if shipping.price_tax_excl is not None:
                        total_price_net += float(shipping.price_tax_excl)
                    if shipping.price_tax_incl:
                        total_price_with_tax += float(shipping.price_tax_incl)
                    elif shipping.price_tax_excl is not None and shipping.id_tax:
                        tax = self._tax_repository.get_tax_by_id(shipping.id_tax)
                        if tax and tax.percentage is not None:
                            total_price_with_tax += float(calculate_price_with_tax(float(shipping.price_tax_excl), float(tax.percentage), quantity=1))

        fiscal_doc.products_total_price_net = products_total_price_net
        fiscal_doc.products_total_price_with_tax = products_total_price_with_tax
        fiscal_doc.total_price_net = total_price_net
        fiscal_doc.total_price_with_tax = total_price_with_tax
        self._session.commit()
    
    # ==================== METODI INTERFACCIA ====================
    
    def get_next_document_number(self, document_type: str) -> int:
        """Ottiene il prossimo numero sequenziale per un tipo di documento (solo intero, si resetta ogni anno)"""
        current_year = datetime.now().year
        
        # Recupera l'ultimo numero per questo tipo nell'anno corrente
        last_doc = self._session.query(FiscalDocument).filter(
            and_(
                FiscalDocument.document_type == document_type,
                func.extract('year', FiscalDocument.date_add) == current_year,
                FiscalDocument.document_number.isnot(None)
            )
        ).order_by(desc(FiscalDocument.id_fiscal_document)).first()
        
        if last_doc and last_doc.document_number:
            try:
                last_number = int(last_doc.document_number)
                return last_number + 1
            except ValueError:
                return 1
        else:
            return 1
    
    def get_by_order_id(self, id_order: int, document_type: Optional[str] = None) -> List[FiscalDocument]:
        """Ottiene tutti i documenti fiscali per un ordine"""
        query = self._session.query(FiscalDocument).filter(FiscalDocument.id_order == id_order)
        
        if document_type:
            query = query.filter(FiscalDocument.document_type == document_type)
        
        return query.order_by(desc(FiscalDocument.date_add)).all()
    
    def get_by_document_type(self, document_type: str, page: int = 1, limit: int = 10) -> List[FiscalDocument]:
        """Ottiene documenti per tipo"""
        offset = (page - 1) * limit
        return self._session.query(FiscalDocument).filter(
            FiscalDocument.document_type == document_type
        ).order_by(desc(FiscalDocument.date_add)).offset(offset).limit(limit).all()
    
    def get_document_count_by_type(self, document_type: str) -> int:
        """Conta i documenti per tipo"""
        return self._session.query(FiscalDocument).filter(
            FiscalDocument.document_type == document_type
        ).count()
    
    def validate_return_items(self, id_order: int, return_items: List[dict]) -> None:
        """Valida gli articoli per un reso"""
        if not return_items:
            raise ValueError("Nessun articolo specificato per il reso")
        
        # Ottieni le quantità già restituite
        returned_quantities = self.get_returned_quantities(id_order)
        
        # Verifica ogni articolo
        for item in return_items:
            id_order_detail = item['id_order_detail']
            quantity_to_return = item['quantity']
            
            # Verifica che l'order_detail esista e appartenga all'ordine
            order_detail = self._session.query(OrderDetail).filter(
                and_(
                    OrderDetail.id_order_detail == id_order_detail,
                    OrderDetail.id_order == id_order
                )
            ).first()
            
            if not order_detail:
                raise ValueError(f"OrderDetail {id_order_detail} non trovato per l'ordine {id_order}")
            
            # Verifica che la quantità da restituire non superi quella disponibile
            original_quantity = order_detail.product_qty
            already_returned = returned_quantities.get(id_order_detail, 0)
            available_quantity = original_quantity - already_returned
            
            if quantity_to_return > available_quantity:
                raise ValueError(
                    f"Quantità da restituire ({quantity_to_return}) superiore alla quantità disponibile "
                    f"({available_quantity}) per l'articolo {id_order_detail}"
                )
    
    def get_returned_quantities(self, id_order: int) -> dict:
        """Ottiene le quantità già restituite per ogni order_detail"""
        # Recupera tutti i resi per questo ordine
        returns = self._session.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_order == id_order,
                FiscalDocument.document_type == 'return'
            )
        ).all()
        
        returned_quantities = {}
        
        for return_doc in returns:
            details = self._session.query(FiscalDocumentDetail).filter(
                FiscalDocumentDetail.id_fiscal_document == return_doc.id_fiscal_document
            ).all()
            
            for detail in details:
                id_order_detail = detail.id_order_detail
                if id_order_detail in returned_quantities:
                    returned_quantities[id_order_detail] += detail.product_qty
                else:
                    returned_quantities[id_order_detail] = detail.product_qty
        
        return returned_quantities
    
    def calculate_return_totals(self, order_details: List[dict], includes_shipping: bool, id_order: int) -> float:
        """Calcola il totale di un reso"""
        total_amount = 0.0
        
        # Calcola il totale dei prodotti
        for item in order_details:
            quantity = item['quantity']
            unit_price_net = item.get('unit_price_net', item.get('unit_price', 0.0))
            id_tax = item.get('id_tax')
            
            # Se unit_price_net non è specificato, recupera dall'order_detail
            if unit_price_net == 0.0:
                order_detail = self._session.query(OrderDetail).filter(
                    OrderDetail.id_order_detail == item['id_order_detail']
                ).first()
                if order_detail:
                    unit_price_net = order_detail.unit_price_net or order_detail.product_price or 0.0
                    if not id_tax:
                        id_tax = order_detail.id_tax
            
            # Calcola il totale della riga senza IVA
            line_total_net = quantity * unit_price_net
            
            # Applica l'IVA se presente (per il totale del documento fiscale)
            line_total_with_tax = line_total_net
            if id_tax:
                tax = self._tax_repository.get_tax_by_id(id_tax)
                tax_percentage = float(tax.percentage) if tax and tax.percentage is not None else None
                if tax_percentage is not None:
                    tax_percentage = float(tax_percentage)
                    line_total_with_tax = calculate_price_with_tax(line_total_net, tax_percentage, quantity=1)
            
            total_amount += line_total_with_tax
        
        # Aggiungi spese di spedizione se richieste
        if includes_shipping:
            order = self._session.query(Order).filter(Order.id_order == id_order).first()
            if order and order.id_shipping:
                shipping = self._session.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
                if shipping and shipping.price_tax_incl:
                    total_amount += float(shipping.price_tax_incl)
        return total_amount
