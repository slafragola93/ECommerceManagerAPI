from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.repository.ddt_repository import DDTRepository
from src.services.order_document_service import OrderDocumentService
from src.models.app_configuration import AppConfiguration
from src.schemas.ddt_schema import (
    DDTResponseSchema, 
    DDTDetailSchema, 
    DDTPackageSchema, 
    DDTSenderSchema,
    DDTGenerateResponseSchema
)
from src.models.customer import Customer
from src.models.address import Address
from src.models.shipping import Shipping
from src.models.order_package import OrderPackage


class DDTService:
    """Service per la logica business dei DDT"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ddt_repo = DDTRepository(db)
        self.order_doc_service = OrderDocumentService(db)
    
    def generate_ddt_from_order(self, id_order: int, user_id: int) -> DDTGenerateResponseSchema:
        """
        Genera un DDT a partire da un ordine
        
        Args:
            id_order: ID dell'ordine
            user_id: ID dell'utente
            
        Returns:
            DDTGenerateResponseSchema: Risposta con il DDT generato
        """
        try:
            # Crea il DDT
            ddt = self.ddt_repo.create_ddt_from_order(id_order, user_id)
            
            if not ddt:
                return DDTGenerateResponseSchema(
                    success=False,
                    message="Ordine non trovato"
                )
            
            # Recupera il DDT completo con tutti i dati
            ddt_complete = self.get_ddt_complete(ddt.id_order_document)
            
            return DDTGenerateResponseSchema(
                success=True,
                message=f"DDT {ddt.document_number} generato con successo",
                ddt=ddt_complete
            )
            
        except ValueError as e:
            return DDTGenerateResponseSchema(
                success=False,
                message=str(e)
            )
        except Exception as e:
            return DDTGenerateResponseSchema(
                success=False,
                message=f"Errore durante la generazione del DDT: {str(e)}"
            )
    
    def get_ddt_complete(self, id_order_document: int) -> Optional[DDTResponseSchema]:
        """
        Recupera un DDT completo con tutti i dati
        
        Args:
            id_order_document: ID del DDT
            
        Returns:
            DDTResponseSchema: DDT completo
        """
        ddt = self.ddt_repo.get_ddt_with_details(id_order_document)
        if not ddt:
            return None
        
        # Recupera i dettagli (articoli)
        details = self.ddt_repo.get_ddt_details(id_order_document)
        details_schema = [
            DDTDetailSchema(
                id_order_detail=d.id_order_detail,
                id_product=d.id_product,
                product_name=d.product_name,
                product_reference=d.product_reference,
                product_qty=d.product_qty,
                product_price=d.product_price,
                product_weight=d.product_weight,
                id_tax=d.id_tax,
                reduction_percent=d.reduction_percent,
                reduction_amount=d.reduction_amount
            ) for d in details
        ]
        
        # Recupera i pacchi se c'è un ordine collegato
        packages_schema = []
        if ddt.id_order:
            packages = self.ddt_repo.get_ddt_packages(ddt.id_order)
            packages_schema = [
                DDTPackageSchema(
                    id_order_package=p.id_order_package,
                    height=p.height,
                    width=p.width,
                    depth=p.depth,
                    weight=p.weight,
                    value=p.value
                ) for p in packages
            ]
        
        # Recupera dati cliente
        customer_data = None
        if ddt.id_customer:
            customer = self.db.query(Customer).filter(Customer.id_customer == ddt.id_customer).first()
            if customer:
                customer_data = {
                    "id_customer": customer.id_customer,
                    "firstname": customer.firstname,
                    "lastname": customer.lastname,
                    "email": customer.email
                }
        
        # Recupera indirizzo di consegna
        address_delivery_data = None
        if ddt.id_address_delivery:
            address = self.db.query(Address).filter(Address.id_address == ddt.id_address_delivery).first()
            if address:
                address_delivery_data = {
                    "id_address": address.id_address,
                    "firstname": address.firstname,
                    "lastname": address.lastname,
                    "address1": address.address1,
                    "address2": address.address2,
                    "city": address.city,
                    "postcode": address.postcode,
                    "phone": address.phone
                }
        
        # Recupera indirizzo di fatturazione
        address_invoice_data = None
        if ddt.id_address_invoice:
            address = self.db.query(Address).filter(Address.id_address == ddt.id_address_invoice).first()
            if address:
                address_invoice_data = {
                    "id_address": address.id_address,
                    "firstname": address.firstname,
                    "lastname": address.lastname,
                    "address1": address.address1,
                    "address2": address.address2,
                    "city": address.city,
                    "postcode": address.postcode,
                    "phone": address.phone
                }
        
        # Recupera dati spedizione
        shipping_data = None
        if ddt.id_shipping:
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == ddt.id_shipping).first()
            if shipping:
                shipping_data = {
                    "id_shipping": shipping.id_shipping,
                    "tracking": shipping.tracking,
                    "weight": shipping.weight,
                    "price_tax_incl": shipping.price_tax_incl,
                    "price_tax_excl": shipping.price_tax_excl,
                    "shipping_message": shipping.shipping_message
                }
        
        # Recupera dati mittente
        sender_config = self.order_doc_service.get_sender_config()
        
        # Recupera il logo dalla configurazione company_logo
        company_logo_config = self.db.query(AppConfiguration).filter(
            and_(
                AppConfiguration.category == "company_info",
                AppConfiguration.name == "company_logo"
            )
        ).first()
        
        logo_path = company_logo_config.value if company_logo_config else None
        
        sender_schema = DDTSenderSchema(
            company_name=sender_config.get("ddt_sender_company_name", ""),
            address=sender_config.get("ddt_sender_address", ""),
            vat=sender_config.get("ddt_sender_vat", ""),
            phone=sender_config.get("ddt_sender_phone", ""),
            email=sender_config.get("ddt_sender_email", ""),
            logo_path=logo_path
        )
        
        # Verifica se il DDT è modificabile
        is_modifiable = self.ddt_repo.is_ddt_modifiable(id_order_document)
        
        return DDTResponseSchema(
            id_order_document=ddt.id_order_document,
            document_number=ddt.document_number,
            type_document=ddt.type_document,
            date_add=ddt.date_add,
            updated_at=ddt.updated_at,
            note=ddt.note,
            total_weight=ddt.total_weight,
            total_price_with_tax=ddt.total_price_with_tax,
            id_order=ddt.id_order or 0,
            customer=customer_data,
            address_delivery=address_delivery_data,
            address_invoice=address_invoice_data,
            shipping=shipping_data,
            details=details_schema,
            packages=packages_schema,
            sender=sender_schema,
            is_modifiable=is_modifiable
        )
    
    def generate_ddt_pdf(self, id_order_document: int) -> bytes:
        """
        Genera il PDF del DDT
        
        Args:
            id_order_document: ID del DDT
            
        Returns:
            bytes: Contenuto del PDF
        """
        try:
            from fpdf import FPDF
            from datetime import datetime
            from io import BytesIO
            
            # Recupera i dati del DDT
            ddt_data = self.get_ddt_complete(id_order_document)
            if not ddt_data:
                raise ValueError("DDT non trovato")
            
            # Inizializza PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # Logo aziendale (se esiste)
            import os
            if ddt_data.sender and ddt_data.sender.logo_path and os.path.exists(ddt_data.sender.logo_path):
                try:
                    pdf.image(ddt_data.sender.logo_path, x=10, y=8, w=40)
                except:
                    pass  # Se il logo non è leggibile, continua senza
            
            # Header - Titolo documento
            pdf.set_xy(120, 10)
            pdf.set_font('Arial', 'B', 18)
            pdf.cell(0, 10, f"DOCUMENTO DI TRASPORTO n. {ddt_data.document_number}", 0, 1, 'R')
            pdf.set_xy(120, 17)
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 7, f"Data: {ddt_data.date_add.strftime('%d/%m/%Y')}", 0, 1, 'R')
            
            pdf.ln(5)
            
            # Box Mittente e Destinatario (due colonne)
            col_width = 95
            y_start = pdf.get_y()
            
            # MITTENTE (colonna sinistra)
            pdf.set_xy(10, y_start)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(col_width, 6, 'MITTENTE', 1, 0)
            pdf.ln()
            pdf.set_font('Arial', '', 8)
            
            if ddt_data.sender:
                sender_info = f"{ddt_data.sender.company_name or ''}\n{ddt_data.sender.address or ''}\n"
                if ddt_data.sender.vat:
                    sender_info += f"P.IVA: {ddt_data.sender.vat}\n"
                if ddt_data.sender.phone:
                    sender_info += f"Tel: {ddt_data.sender.phone}\n"
                if ddt_data.sender.email:
                    sender_info += f"Email: {ddt_data.sender.email}"
            else:
                sender_info = "Dati mittente non disponibili"
            
            pdf.multi_cell(col_width, 4, sender_info, 1)
            
            # DESTINATARIO (colonna destra)
            y_end_sender = pdf.get_y()
            pdf.set_xy(10 + col_width, y_start)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(col_width, 6, 'DESTINATARIO', 1, 0)
            pdf.ln()
            pdf.set_xy(10 + col_width, y_start + 6)
            
            if ddt_data.customer and ddt_data.address_delivery:
                customer_name = f"{ddt_data.customer.get('firstname', '')} {ddt_data.customer.get('lastname', '')}".strip()
                customer_info = f"{customer_name}\n" if customer_name else ""
                
                if ddt_data.address_delivery:
                    if ddt_data.address_delivery.get('address1'):
                        customer_info += f"{ddt_data.address_delivery.get('address1', '')}\n"
                    if ddt_data.address_delivery.get('city') and ddt_data.address_delivery.get('postcode'):
                        customer_info += f"{ddt_data.address_delivery.get('postcode', '')} {ddt_data.address_delivery.get('city', '')}"
            else:
                customer_info = "Dati destinatario non disponibili"
            
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(col_width, 5, customer_info, 1)
            y_end_customer = pdf.get_y()
            
            # Posiziona dopo la colonna più lunga
            pdf.set_y(max(y_end_sender, y_end_customer))
            pdf.ln(3)
            
            # Riferimento ordine
            if ddt_data.id_order:
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 5, f"Riferimento ordine: {ddt_data.id_order}", 0, 1)
                pdf.ln(2)
            
            # Tabella articoli - Header
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(224, 224, 224)
            pdf.cell(30, 6, 'Codice', 1, 0, 'L', True)
            pdf.cell(60, 6, 'Descrizione', 1, 0, 'L', True)
            pdf.cell(15, 6, 'Qta', 1, 0, 'R', True)
            pdf.cell(25, 6, 'Prezzo', 1, 0, 'R', True)
            pdf.cell(20, 6, 'IVA', 1, 0, 'C', True)
            pdf.cell(25, 6, 'Totale', 1, 1, 'R', True)
            
            # Tabella articoli - Righe
            pdf.set_font('Arial', '', 8)
            subtotal = 0.0
            total_with_vat_sum = 0.0
            total_quantity = 0
            total_weight = 0.0
            
            if ddt_data.details:
                for detail in ddt_data.details:
                    code = (detail.product_reference or '')[:15]
                    description = (detail.product_name or '')[:30]
                    quantity = detail.product_qty or 0
                    unit_price = detail.product_price or 0.0
                    vat_rate = detail.id_tax or 0
                    
                    # Calcola totale riga
                    total_amount = unit_price * quantity
                    vat_multiplier = 1 + (vat_rate / 100.0) if vat_rate else 1.0
                    total_with_vat = total_amount * vat_multiplier
                    
                    pdf.cell(30, 5, code, 1, 0, 'L')
                    pdf.cell(60, 5, description, 1, 0, 'L')
                    pdf.cell(15, 5, f"{quantity:.0f}", 1, 0, 'R')
                    pdf.cell(25, 5, f"{unit_price:.2f} EUR", 1, 0, 'R')
                    pdf.cell(20, 5, f"{vat_rate}%" if vat_rate else "-", 1, 0, 'C')
                    pdf.cell(25, 5, f"{total_with_vat:.2f} EUR", 1, 1, 'R')
                    
                    subtotal += total_amount
                    total_with_vat_sum += total_with_vat
                    total_quantity += quantity
            
            pdf.ln(3)
            
            # Sezione Info Spedizione e Riepilogo
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 5, 'INFORMAZIONI SPEDIZIONE E RIEPILOGO', 0, 1, 'L')
            pdf.ln(2)
            
            # Box con info spedizione (3 colonne)
            y_shipping = pdf.get_y()
            col_w = 63
            
            # Colonna 1
            pdf.set_xy(10, y_shipping)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(col_w, 4, 'Tot. Quant.', 1, 0, 'L')
            pdf.cell(col_w, 4, 'Peso (Kg)', 1, 0, 'L')
            pdf.cell(col_w, 4, 'Colli', 1, 1, 'L')
            
            # Valori shipping
            total_weight_kg = ddt_data.total_weight or 0.0
            pdf.set_font('Arial', '', 8)
            pdf.cell(col_w, 4, str(int(total_quantity)), 1, 0, 'C')
            pdf.cell(col_w, 4, f"{total_weight_kg:.3f}", 1, 0, 'C')
            pdf.cell(col_w, 4, '1', 1, 1, 'C')
            
            pdf.ln(2)
            
            # Porto, Causale, Inizio trasporto
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(col_w, 4, 'Porto', 1, 0, 'L')
            pdf.cell(col_w, 4, 'Causale trasporto', 1, 0, 'L')
            pdf.cell(col_w, 4, 'Inizio trasporto', 1, 1, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(col_w, 4, '-', 1, 0, 'C')
            pdf.cell(col_w, 4, '-', 1, 0, 'C')
            pdf.cell(col_w, 4, '-', 1, 1, 'C')
            
            pdf.ln(3)
            
            # Tabella Riepilogo IVA e Totali
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 5, 'RIEPILOGO IVA E TOTALI', 0, 1, 'L')
            pdf.ln(1)
            
            # Header tabella riepilogo
            pdf.set_font('Arial', 'B', 8)
            pdf.set_fill_color(224, 224, 224)
            pdf.cell(25, 5, 'Aliquota', 1, 0, 'C', True)
            pdf.cell(35, 5, 'Imp. Merce', 1, 0, 'R', True)
            pdf.cell(35, 5, 'Imp. Spese', 1, 0, 'R', True)
            pdf.cell(35, 5, 'Tot. IVA', 1, 0, 'R', True)
            pdf.cell(60, 5, '', 0, 1)  # Spazio per i totali a destra
            
            # Calcolo spese trasporto
            shipping_cost = 0.0
            shipping_cost_with_vat = 0.0
            shipping_vat_percentage = 0
            
            if ddt_data.shipping:
                shipping_cost = ddt_data.shipping.get('price_tax_excl', 0.0)
                shipping_cost_with_vat = ddt_data.shipping.get('price_tax_incl', 0.0)
                shipping_vat_percentage = ddt_data.shipping.get('vat_percentage', 0)
            
            # Calcola totali
            total_doc = ddt_data.total_price_with_tax or 0.0
            total_vat = total_doc - subtotal
            
            # Riga IVA (assumiamo 22% come default)
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, '22%', 1, 0, 'C')
            pdf.cell(35, 5, f"{subtotal:.2f}", 1, 0, 'R')
            pdf.cell(35, 5, f"{shipping_cost:.2f}", 1, 0, 'R')
            pdf.cell(35, 5, f"{total_vat:.2f}", 1, 0, 'R')
            
            # Colonna destra - Totali dettagliati
            pdf.set_xy(140, pdf.get_y())
            pdf.set_font('Arial', 'B', 8)
            shipping_label = f'Spese trasporto'
            if shipping_vat_percentage:
                shipping_label += f' (+{shipping_vat_percentage}% IVA)'
            pdf.cell(35, 5, shipping_label, 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, f"{shipping_cost_with_vat:.2f}", 0, 1, 'R')
            
            pdf.ln(5)
            
            # Blocco totali finali (2 colonne)
            y_totals = pdf.get_y()
            
            # Colonna sinistra
            pdf.set_xy(10, y_totals)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(45, 5, 'Merce netta', 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, f"{subtotal:.2f}", 0, 1, 'R')
            
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(45, 5, 'Totale imponibile', 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, f"{subtotal + shipping_cost:.2f}", 0, 1, 'R')
            
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(45, 5, 'Spese incasso', 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, '0,00', 0, 1, 'R')
            
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(45, 5, 'Merce lorda', 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, f"{total_with_vat_sum:.2f}", 0, 1, 'R')
            
            # Colonna destra
            pdf.set_xy(130, y_totals)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(45, 5, 'Totale IVA', 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, f"{total_vat:.2f}", 0, 1, 'R')
            
            pdf.set_xy(130, pdf.get_y())
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(45, 5, 'Spese varie', 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, '0,00', 0, 1, 'R')
            
            # Totale documento (evidenziato)
            pdf.ln(2)
            pdf.set_xy(130, pdf.get_y())
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(45, 8, 'Totale documento', 0, 0, 'L')
            pdf.cell(25, 8, f"{total_doc:.2f} EUR", 0, 1, 'R')
            
            pdf.ln(5)
            
            # Sezione Pagamento e Scadenze
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(95, 5, 'Pagamento', 1, 0, 'L')
            pdf.cell(95, 5, 'Scadenze', 1, 1, 'L')
            
            pdf.set_font('Arial', '', 9)
            pdf.cell(95, 5, '-', 1, 0, 'L')
            pdf.cell(95, 5, '', 1, 1, 'L')
            
            pdf.ln(2)
            
            # Firma trasporto
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(63, 5, 'Incaricato del trasporto', 1, 0, 'L')
            pdf.cell(63, 5, 'Aspetto esteriore dei beni', 1, 0, 'L')
            pdf.cell(64, 5, '', 0, 1)
            
            pdf.set_font('Arial', '', 8)
            pdf.cell(63, 8, '', 1, 0, 'L')
            pdf.cell(63, 8, '', 1, 1, 'L')
            
            pdf.ln(1)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(95, 5, 'Firma destinatario', 1, 0, 'L')
            pdf.cell(95, 5, 'Firma conducente', 1, 1, 'L')
            
            pdf.set_font('Arial', '', 8)
            pdf.cell(95, 8, '', 1, 0, 'L')
            pdf.cell(95, 8, '', 1, 1, 'L')
            
            # Note
            if ddt_data.note:
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 5, 'Note:', 0, 1)
                pdf.set_font('Arial', '', 9)
                pdf.multi_cell(0, 5, ddt_data.note)
            
            # Footer
            pdf.ln(10)
            pdf.set_font('Arial', 'I', 8)
            pdf.set_text_color(128, 128, 128)
            pdf.cell(0, 5, f"Documento generato automaticamente - {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')
            
            # Ritorna contenuto PDF
            return pdf.output()
            
        except ImportError:
            raise Exception("Libreria fpdf2 non installata. Installare con: pip install fpdf2")
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")
    
    def update_ddt_detail(self, id_order_detail: int, detail_data: dict) -> Optional[DDTDetailSchema]:
        """
        Aggiorna un dettaglio del DDT
        
        Args:
            id_order_detail: ID del dettaglio
            detail_data: Dati da aggiornare
            
        Returns:
            DDTDetailSchema: Dettaglio aggiornato
        """
        try:
            updated_detail = self.ddt_repo.update_ddt_detail(id_order_detail, **detail_data)
            
            if not updated_detail:
                return None
            
            return DDTDetailSchema(
                id_order_detail=updated_detail.id_order_detail,
                id_product=updated_detail.id_product,
                product_name=updated_detail.product_name,
                product_reference=updated_detail.product_reference,
                product_qty=updated_detail.product_qty,
                product_price=updated_detail.product_price,
                product_weight=updated_detail.product_weight,
                id_tax=updated_detail.id_tax,
                reduction_percent=updated_detail.reduction_percent,
                reduction_amount=updated_detail.reduction_amount
            )
            
        except ValueError as e:
            raise e
        except Exception as e:
            raise Exception(f"Errore durante l'aggiornamento del dettaglio: {str(e)}")
    
    def delete_ddt_detail(self, id_order_detail: int) -> bool:
        """
        Elimina un dettaglio del DDT
        
        Args:
            id_order_detail: ID del dettaglio
            
        Returns:
            bool: True se eliminato con successo
        """
        try:
            return self.ddt_repo.delete_ddt_detail(id_order_detail)
        except ValueError as e:
            raise e
        except Exception as e:
            raise Exception(f"Errore durante l'eliminazione del dettaglio: {str(e)}")
