"""
Servizio PDF per generazione documenti fiscali (fatture e note di credito)
Estende BasePDFService e implementa metodi helper specifici per documenti fiscali
"""
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
from io import BytesIO
import os

from src.services.pdf.base_pdf_service import BasePDFService
from src.services.media.media_utils import get_store_logo_path


class FiscalDocumentPDFService(BasePDFService):
    """Servizio per generazione PDF di documenti fiscali"""
    
    def generate_pdf(self, fiscal_document, order=None, invoice_address=None,
                     delivery_address=None, details_with_products: List[Dict[str, Any]] = None,
                     payment_name: Optional[str] = None, company_config: Dict[str, Any] = None,
                     referenced_invoice=None, db=None) -> bytes:
        """
        Genera il PDF del documento fiscale
        
        Args:
            fiscal_document: FiscalDocument (fattura o nota di credito)
            order: Order collegato (opzionale)
            invoice_address: Address di fatturazione (opzionale)
            delivery_address: Address di consegna (opzionale)
            details_with_products: Lista di dettagli con info prodotto (richiesto)
            payment_name: Nome metodo di pagamento (opzionale)
            company_config: Configurazioni aziendali (richiesto)
            referenced_invoice: FiscalDocument di riferimento per note di credito (opzionale)
            db: Sessione database per recuperare dati aggiuntivi (opzionale)
            
        Returns:
            bytes: Contenuto del PDF
            
        Raises:
            ValueError: Se i dati richiesti non sono disponibili
            Exception: Per altri errori durante la generazione
        """
        try:
            if not fiscal_document:
                raise ValueError("fiscal_document è richiesto")
            
            if not details_with_products:
                raise ValueError("details_with_products è richiesto")
            
            if not company_config:
                raise ValueError("company_config è richiesto")
            
            # Determina tipo documento
            is_credit_note = fiscal_document.document_type == 'credit_note'
            doc_title = "NOTA DI CREDITO" if is_credit_note else "FATTURA"
            doc_number = fiscal_document.document_number or fiscal_document.internal_number or "N/A"
            doc_date = fiscal_document.date_add.strftime("%d/%m/%Y") if fiscal_document.date_add else ""
            
            # Recupera logo: prima prova logo store, poi fallback a logo aziendale
            logo_path = company_config.get('company_logo', 'media/logos/logo.png')
            if fiscal_document.id_store and db:
                from src.models.store import Store
                store = db.query(Store).filter(Store.id_store == fiscal_document.id_store).first()
                if store:
                    logo_path = get_store_logo_path(store, fallback_path=logo_path)
            
            # Inizializza PDF
            pdf = self.create_pdf(margin=15)
            
            # Header documento
            self.create_document_header(
                pdf=pdf,
                title=doc_title,
                document_number=doc_number,
                date=doc_date,
                logo_path=logo_path if logo_path and os.path.exists(logo_path) else None
            )
            
            # Riferimento fattura per note di credito
            if is_credit_note and referenced_invoice:
                ref_number = referenced_invoice.document_number or referenced_invoice.internal_number or "N/A"
                ref_date = referenced_invoice.date_add.strftime("%d/%m/%Y") if referenced_invoice.date_add else ""
                self.add_credit_note_reference(pdf, ref_number, ref_date)
            
            # Box Venditore e Cliente (diverso da MITTENTE/DESTINATARIO)
            self.create_seller_customer_boxes(
                pdf=pdf,
                company_config=company_config,
                invoice_address=invoice_address
            )
            
            # Box Consegna (se presente, specifico per documenti fiscali)
            if delivery_address:
                self.add_delivery_address_box(pdf, delivery_address)
            
            # Riferimento ordine
            if order and order.reference:
                self.add_order_reference(pdf, order.reference)
            
            # Tabella articoli - Header (con colonna Sc.%)
            self.create_items_table_header_with_discount(pdf)
            
            # Tabella articoli - Righe
            subtotal = 0.0
            total_with_vat_sum = 0.0
            total_quantity = 0
            
            for detail in details_with_products:
                code = detail.get('product_reference', '')[:15]
                description = detail.get('product_name', '')[:30]
                quantity = detail.get('product_qty', detail.get('quantity', 0))
                unit_price = detail.get('unit_price', 0.0)
                total_price_with_tax = detail.get('total_price_with_tax', detail.get('total_amount', 0.0))
                reduction_percent = detail.get('reduction_percent', 0.0)
                vat_rate = detail.get('vat_rate', 0)
                
                vat_multiplier = 1 + (vat_rate / 100.0) if vat_rate else 1.0
                total_with_vat = total_price_with_tax * vat_multiplier
                
                self.add_items_table_row_with_discount(
                    pdf=pdf,
                    code=code,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    reduction_percent=reduction_percent,
                    vat_rate=vat_rate,
                    total_with_vat=total_with_vat
                )
                
                subtotal += total_price_with_tax
                total_with_vat_sum += total_with_vat
                total_quantity += quantity
            
            # Sezione Info Spedizione e Riepilogo
            total_weight = order.total_weight if order and order.total_weight else 0.0
            self.create_shipping_info_section(pdf, total_quantity, total_weight)
            
            # Calcola spese trasporto
            shipping_cost = 0.0
            shipping_cost_with_vat = 0.0
            shipping_vat_percentage = 0
            
            if order and hasattr(order, 'shipments') and order.shipments:
                shipping_cost = order.shipments.price_tax_excl if order.shipments.price_tax_excl else 0.0
                
                if order.shipments.id_tax and db:
                    from src.repository.tax_repository import TaxRepository
                    tax_repo = TaxRepository(db)
                    shipping_vat_percentage = tax_repo.get_percentage_by_id(order.shipments.id_tax)
                    
                    if shipping_vat_percentage:
                        shipping_cost_with_vat = shipping_cost * (1 + shipping_vat_percentage / 100.0)
                    else:
                        shipping_cost_with_vat = order.shipments.price_tax_incl if order.shipments.price_tax_incl else 0.0
                else:
                    shipping_cost_with_vat = order.shipments.price_tax_incl if order.shipments.price_tax_incl else 0.0
            
            # Calcola totali
            total_doc = fiscal_document.total_price_with_tax
            if details_with_products and details_with_products[0].get('vat_rate'):
                vat_rate_first = details_with_products[0]['vat_rate']
                total_imponibile = total_doc / (1 + (vat_rate_first / 100.0))
                total_vat = total_doc - total_imponibile
            else:
                total_imponibile = subtotal + shipping_cost
                total_vat = total_doc - total_imponibile
            
            # Tabella Riepilogo IVA e Totali
            self.create_vat_summary_section(
                pdf=pdf,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total_vat=total_vat,
                shipping_vat_percentage=shipping_vat_percentage,
                shipping_cost_with_vat=shipping_cost_with_vat
            )
            
            # Blocco totali finali
            self.create_fiscal_totals_section(
                pdf=pdf,
                subtotal=subtotal,
                total_imponibile=total_imponibile,
                total_with_vat_sum=total_with_vat_sum,
                total_vat=total_vat,
                total_doc=total_doc
            )
            
            # Sezione Pagamento e Scadenze
            self.create_payment_section(
                pdf=pdf,
                payment_text=payment_name if payment_name else '-',
                deadlines_text=''
            )
            
            # Firma trasporto
            self.create_transport_signature_section(pdf=pdf)
            
            # Note (specifiche per documenti fiscali)
            self.add_fiscal_notes(
                pdf=pdf,
                is_credit_note=is_credit_note,
                credit_note_reason=fiscal_document.credit_note_reason if hasattr(fiscal_document, 'credit_note_reason') else None,
                order_note=order.general_note if order and order.general_note else None
            )
            
            # Footer
            self.add_footer(pdf=pdf)
            
            # Ritorna contenuto PDF
            return pdf.output()
            
        except ImportError:
            raise Exception("Libreria fpdf2 non installata. Installare con: pip install fpdf2")
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")
    
    # Metodi helper specifici per documenti fiscali
    
    @staticmethod
    def create_pdf(margin: int = 15) -> Any:
        """Crea e inizializza un'istanza FPDF"""
        from fpdf import FPDF
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=margin)
        
        return pdf
    
    @staticmethod
    def insert_logo(pdf, logo_path: Optional[str], x: float = 10, y: float = 8, width: float = 40) -> bool:
        """Inserisce il logo aziendale nel PDF"""
        if not logo_path:
            return False
            
        if not os.path.exists(logo_path):
            return False
            
        try:
            pdf.image(logo_path, x=x, y=y, w=width)
            return True
        except Exception:
            return False
    
    @staticmethod
    def create_document_header(
        pdf,
        title: str,
        document_number: str,
        date: Union[str, datetime],
        logo_path: Optional[str] = None
    ) -> Dict[str, float]:
        """Crea l'header del documento con logo, titolo e data"""
        FiscalDocumentPDFService.insert_logo(pdf, logo_path, x=10, y=8, width=40)
        
        pdf.set_xy(120, 10)
        pdf.set_font('Arial', 'B', 18)
        pdf.cell(0, 10, f"{title} n. {document_number}", 0, 1, 'R')
        
        pdf.set_xy(120, 17)
        pdf.set_font('Arial', '', 12)
        
        if isinstance(date, datetime):
            date_str = date.strftime('%d/%m/%Y')
        else:
            date_str = str(date)
        
        pdf.cell(0, 7, f"Data: {date_str}", 0, 1, 'R')
        pdf.ln(5)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_credit_note_reference(pdf, ref_number: str, ref_date: str) -> Dict[str, float]:
        """Aggiunge riferimento fattura per note di credito"""
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 5, f"A storno di FATTURA n. {ref_number} del {ref_date}", 0, 1, 'C')
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_seller_customer_boxes(
        pdf,
        company_config: Dict[str, Any],
        invoice_address: Any = None,
        col_width: float = 95
    ) -> Dict[str, float]:
        """Crea i box VENDITORE e CLIENTE (specifico per documenti fiscali)"""
        y_start = pdf.get_y()
        
        # VENDITORE (colonna sinistra)
        pdf.set_xy(10, y_start)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 6, 'VENDITORE', 1, 0)
        pdf.ln()
        pdf.set_font('Arial', '', 8)
        
        company_name = company_config.get('company_name', '')
        company_address = company_config.get('address', '')
        company_postal_code = company_config.get('postal_code', '')
        company_city = company_config.get('city', '')
        company_province = company_config.get('province', '')
        company_city_full = f"{company_postal_code} - {company_city} ({company_province})"
        
        seller_info = f"{company_name}\n{company_address}\n{company_city_full}\n"
        
        # P.IVA e C.F.
        vat_cf_line = []
        if company_config.get('vat_number'):
            vat_cf_line.append(f"P.I. {company_config['vat_number']}")
        if company_config.get('fiscal_code'):
            vat_cf_line.append(f"C.F. {company_config['fiscal_code']}")
        if vat_cf_line:
            seller_info += " - ".join(vat_cf_line) + "\n"
        
        # IBAN, BIC, PEC, SDI
        if company_config.get('iban'):
            seller_info += f"IBAN {company_config['iban']}\n"
        if company_config.get('bic_swift'):
            seller_info += f"BIC/SWIFT {company_config['bic_swift']}\n"
        if company_config.get('pec'):
            seller_info += f"PEC: {company_config['pec']}\n"
        if company_config.get('sdi_code'):
            seller_info += f"SDI: {company_config['sdi_code']}"
        
        pdf.multi_cell(col_width, 4, seller_info, 1)
        
        # CLIENTE (colonna destra)
        y_end_seller = pdf.get_y()
        pdf.set_xy(10 + col_width, y_start)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 6, 'CLIENTE', 1, 0)
        pdf.ln()
        pdf.set_xy(10 + col_width, y_start + 6)
        
        if invoice_address:
            customer_name = invoice_address.company if invoice_address.company else f"{invoice_address.firstname or ''} {invoice_address.lastname or ''}".strip()
            customer_info = f"{customer_name}\n" if customer_name else ""
            
            if invoice_address.address1:
                customer_info += f"{invoice_address.address1 or ''} {invoice_address.address2 or ''}".strip() + "\n"
            
            city_line = f"{invoice_address.postcode or ''} {invoice_address.city or ''}".strip()
            if invoice_address.state:
                city_line += f" ({invoice_address.state})"
            if city_line.strip():
                customer_info += city_line.strip() + "\n"
            
            if invoice_address.vat:
                customer_info += f"P.IVA/CF: {invoice_address.vat}\n"
            elif invoice_address.dni:
                customer_info += f"Cod. Fiscale: {invoice_address.dni}\n"
            
            if invoice_address.pec:
                customer_info += f"PEC: {invoice_address.pec}\n"
            
            if invoice_address.sdi:
                customer_info += f"SDI: {invoice_address.sdi}"
            elif invoice_address.ipa:
                customer_info += f"IPA: {invoice_address.ipa}"
            
            if not customer_info.strip():
                customer_info = "N/A"
        else:
            customer_info = "N/A"
        
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(col_width, 5, customer_info, 1)
        y_end_customer = pdf.get_y()
        
        pdf.set_y(max(y_end_seller, y_end_customer))
        pdf.ln(3)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_delivery_address_box(pdf, delivery_address: Any) -> Dict[str, float]:
        """Aggiunge box destinazione merce (specifico per documenti fiscali)"""
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, 'DESTINAZIONE MERCE', 1, 1)
        pdf.set_font('Arial', '', 9)
        
        delivery_name = delivery_address.company if delivery_address.company else f"{delivery_address.firstname or ''} {delivery_address.lastname or ''}".strip()
        delivery_info = f"{delivery_name}\n"
        delivery_info += f"{delivery_address.address1 or ''} {delivery_address.address2 or ''}".strip() + "\n"
        delivery_info += f"{delivery_address.postcode or ''} {delivery_address.city or ''} ({delivery_address.state or ''})".strip()
        
        pdf.multi_cell(0, 5, delivery_info, 1)
        pdf.ln(3)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_order_reference(pdf, order_reference: str) -> Dict[str, float]:
        """Aggiunge riferimento ordine"""
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, f"Riferimento ordine: {order_reference}", 0, 1)
        pdf.ln(2)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_items_table_header_with_discount(pdf) -> Dict[str, float]:
        """Crea l'header della tabella articoli con colonna Sc.% (specifico per documenti fiscali)"""
        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(224, 224, 224)
        pdf.cell(30, 6, 'Codice', 1, 0, 'L', True)
        pdf.cell(60, 6, 'Descrizione', 1, 0, 'L', True)
        pdf.cell(15, 6, 'Qta', 1, 0, 'R', True)
        pdf.cell(25, 6, 'Prezzo No IVA', 1, 0, 'R', True)
        pdf.cell(15, 6, 'Sc.%', 1, 0, 'C', True)
        pdf.cell(20, 6, 'IVA', 1, 0, 'C', True)
        pdf.cell(25, 6, 'Totale', 1, 1, 'R', True)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_items_table_row_with_discount(
        pdf,
        code: str,
        description: str,
        quantity: float,
        unit_price: float,
        reduction_percent: float,
        vat_rate: float,
        total_with_vat: float
    ) -> Dict[str, float]:
        """Aggiunge una riga alla tabella articoli con colonna Sc.%"""
        pdf.set_font('Arial', '', 8)
        pdf.cell(30, 5, str(code)[:15], 1, 0, 'L')
        pdf.cell(60, 5, str(description)[:30], 1, 0, 'L')
        pdf.cell(15, 5, f"{quantity:.0f}", 1, 0, 'R')
        pdf.cell(25, 5, f"{unit_price:.2f} EUR", 1, 0, 'R')
        pdf.cell(15, 5, f"{reduction_percent:.0f}%" if reduction_percent > 0 else "-", 1, 0, 'C')
        pdf.cell(20, 5, f"{vat_rate}%" if vat_rate else "-", 1, 0, 'C')
        pdf.cell(25, 5, f"{total_with_vat:.2f} EUR", 1, 1, 'R')
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_shipping_info_section(pdf, total_quantity: int, total_weight: float) -> Dict[str, float]:
        """Crea sezione informazioni spedizione"""
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, 'INFORMAZIONI SPEDIZIONE E RIEPILOGO', 0, 1, 'L')
        pdf.ln(2)
        
        y_shipping = pdf.get_y()
        col_w = 63
        
        pdf.set_xy(10, y_shipping)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(col_w, 4, 'Tot. Quant.', 1, 0, 'L')
        pdf.cell(col_w, 4, 'Peso (Kg)', 1, 0, 'L')
        pdf.cell(col_w, 4, 'Colli', 1, 1, 'L')
        
        pdf.set_font('Arial', '', 8)
        pdf.cell(col_w, 4, str(int(total_quantity)), 1, 0, 'C')
        pdf.cell(col_w, 4, f"{total_weight:.3f}", 1, 0, 'C')
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
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_vat_summary_section(
        pdf,
        subtotal: float,
        shipping_cost: float,
        total_vat: float,
        shipping_vat_percentage: float,
        shipping_cost_with_vat: float
    ) -> Dict[str, float]:
        """Crea sezione riepilogo IVA"""
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, 'RIEPILOGO IVA E TOTALI', 0, 1, 'L')
        pdf.ln(1)
        
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(224, 224, 224)
        pdf.cell(25, 5, 'Aliquota', 1, 0, 'C', True)
        pdf.cell(35, 5, 'Imp. Merce', 1, 0, 'R', True)
        pdf.cell(35, 5, 'Imp. Spese', 1, 0, 'R', True)
        pdf.cell(35, 5, 'Tot. IVA', 1, 0, 'R', True)
        pdf.cell(60, 5, '', 0, 1)
        
        pdf.set_font('Arial', '', 8)
        pdf.cell(25, 5, '22%', 1, 0, 'C')
        pdf.cell(35, 5, f"{subtotal:.2f}", 1, 0, 'R')
        pdf.cell(35, 5, f"{shipping_cost:.2f}", 1, 0, 'R')
        pdf.cell(35, 5, f"{total_vat:.2f}", 1, 0, 'R')
        
        shipping_label = 'Spese trasporto'
        if shipping_vat_percentage:
            shipping_label += f' (+{shipping_vat_percentage}% IVA)'
        
        pdf.set_xy(140, pdf.get_y())
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(35, 5, shipping_label, 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(25, 5, f"{shipping_cost_with_vat:.2f}", 0, 1, 'R')
        
        pdf.ln(5)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_fiscal_totals_section(
        pdf,
        subtotal: float,
        total_imponibile: float,
        total_with_vat_sum: float,
        total_vat: float,
        total_doc: float
    ) -> Dict[str, float]:
        """Crea sezione totali finali per documenti fiscali"""
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
        pdf.cell(25, 5, f"{total_imponibile:.2f}", 0, 1, 'R')
        
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
        
        # Totale documento
        pdf.ln(2)
        pdf.set_xy(130, pdf.get_y())
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(45, 8, 'Totale documento', 0, 0, 'L')
        pdf.cell(25, 8, f"{total_doc:.2f} EUR", 0, 1, 'R')
        
        pdf.ln(3)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_payment_section(
        pdf,
        payment_text: str = '-',
        deadlines_text: str = '',
        col_width: float = 95
    ) -> Dict[str, float]:
        """Crea la sezione pagamento e scadenze"""
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(col_width, 5, 'Pagamento', 1, 0, 'L')
        pdf.cell(col_width, 5, 'Scadenze', 1, 1, 'L')
        
        pdf.set_font('Arial', '', 9)
        pdf.cell(col_width, 5, payment_text, 1, 0, 'L')
        pdf.cell(col_width, 5, deadlines_text, 1, 1, 'L')
        
        pdf.ln(2)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_transport_signature_section(
        pdf,
        transporter_label: str = 'Incaricato del trasporto',
        appearance_label: str = 'Aspetto esteriore dei beni',
        recipient_label: str = 'Firma destinatario',
        driver_label: str = 'Firma conducente',
        col_width_1: float = 63,
        col_width_2: float = 95
    ) -> Dict[str, float]:
        """Crea la sezione firma trasporto"""
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(col_width_1, 5, transporter_label, 1, 0, 'L')
        pdf.cell(col_width_1, 5, appearance_label, 1, 0, 'L')
        pdf.cell(64, 5, '', 0, 1)
        
        pdf.set_font('Arial', '', 8)
        pdf.cell(col_width_1, 8, '', 1, 0, 'L')
        pdf.cell(col_width_1, 8, '', 1, 1, 'L')
        
        pdf.ln(1)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(col_width_2, 5, recipient_label, 1, 0, 'L')
        pdf.cell(col_width_2, 5, driver_label, 1, 1, 'L')
        
        pdf.set_font('Arial', '', 8)
        pdf.cell(col_width_2, 8, '', 1, 0, 'L')
        pdf.cell(col_width_2, 8, '', 1, 1, 'L')
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_fiscal_notes(
        pdf,
        is_credit_note: bool = False,
        credit_note_reason: Optional[str] = None,
        order_note: Optional[str] = None
    ) -> Dict[str, float]:
        """Aggiunge note specifiche per documenti fiscali"""
        if is_credit_note and credit_note_reason:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 5, 'Motivo nota di credito:', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, credit_note_reason)
            pdf.ln(2)
        
        if order_note:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 5, 'Note:', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, order_note)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_footer(pdf, text: str = None, spacing_before: float = 10.0) -> Dict[str, float]:
        """Aggiunge un footer al PDF"""
        pdf.ln(spacing_before)
        
        if text is None:
            text = f"Documento generato automaticamente - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, text, 0, 1, 'C')
        
        return {'y_end': pdf.get_y()}

