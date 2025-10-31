"""
Servizio PDF per generazione DDT
Estende BasePDFService e implementa metodi helper specifici per DDT
"""
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
import os

from src.services.pdf.base_pdf_service import BasePDFService


class DDTPDFService(BasePDFService):
    """Servizio per generazione PDF di DDT"""
    
    def generate_pdf(self, ddt_data, sender: Optional[Any] = None, 
                     customer_data: Optional[Dict[str, Any]] = None,
                     address_delivery_data: Optional[Dict[str, Any]] = None,
                     shipping_data: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Genera il PDF del DDT
        
        Args:
            ddt_data: DDTResponseSchema con tutti i dati del DDT
            sender: DDTSenderSchema con dati mittente (opzionale, usa ddt_data.sender se None)
            customer_data: Dati cliente (opzionale, usa ddt_data.customer se None)
            address_delivery_data: Dati indirizzo consegna (opzionale, usa ddt_data.address_delivery se None)
            shipping_data: Dati spedizione (opzionale, usa ddt_data.shipping se None)
            
        Returns:
            bytes: Contenuto del PDF
            
        Raises:
            ValueError: Se i dati richiesti non sono disponibili
            Exception: Per altri errori durante la generazione
        """
        try:
            if not ddt_data:
                raise ValueError("ddt_data è richiesto")
            
            # Usa i dati da ddt_data se non forniti esplicitamente
            sender_obj = sender if sender else (ddt_data.sender if hasattr(ddt_data, 'sender') else None)
            customer = customer_data if customer_data else (ddt_data.customer if hasattr(ddt_data, 'customer') else None)
            address_del = address_delivery_data if address_delivery_data else (ddt_data.address_delivery if hasattr(ddt_data, 'address_delivery') else None)
            shipping = shipping_data if shipping_data else (ddt_data.shipping if hasattr(ddt_data, 'shipping') else None)
            
            logo_path = sender_obj.logo_path if sender_obj and hasattr(sender_obj, 'logo_path') else None
            
            # Inizializza PDF
            pdf = self.create_pdf(margin=15)
            
            # Header documento
            document_date = ddt_data.date_add if ddt_data.date_add else datetime.now()
            self.create_document_header(
                pdf=pdf,
                title="DOCUMENTO DI TRASPORTO",
                document_number=ddt_data.document_number,
                date=document_date,
                logo_path=logo_path
            )
            
            # Box Mittente e Destinatario
            sender_info_dict = {}
            if sender_obj:
                sender_info_dict = {
                    'name': sender_obj.company_name if hasattr(sender_obj, 'company_name') else '',
                    'address': sender_obj.address if hasattr(sender_obj, 'address') else '',
                    'vat': sender_obj.vat if hasattr(sender_obj, 'vat') else '',
                    'phone': sender_obj.phone if hasattr(sender_obj, 'phone') else '',
                    'email': sender_obj.email if hasattr(sender_obj, 'email') else ''
                }
            
            recipient_info_dict = {}
            if customer and address_del:
                customer_name = f"{customer.get('firstname', '')} {customer.get('lastname', '')}".strip()
                recipient_info_dict = {
                    'name': customer_name,
                    'address': address_del.get('address1', ''),
                    'city': address_del.get('city', ''),
                    'postcode': address_del.get('postcode', ''),
                    'phone': address_del.get('phone', '')
                }
            
            self.create_address_boxes(
                pdf=pdf,
                sender_data=sender_info_dict,
                recipient_data=recipient_info_dict
            )
            
            # Riferimento ordine (specifico per DDT)
            if hasattr(ddt_data, 'id_order') and ddt_data.id_order:
                self.add_order_reference(pdf, ddt_data.id_order)
            
            # Tabella articoli - Header
            self.create_items_table_header(pdf)
            
            # Tabella articoli - Righe
            subtotal = 0.0
            total_with_vat_sum = 0.0
            total_quantity = 0
            total_weight = 0.0
            
            if hasattr(ddt_data, 'details') and ddt_data.details:
                for detail in ddt_data.details:
                    code = (detail.product_reference or '')[:15]
                    description = (detail.product_name or '')[:30]
                    quantity = detail.product_qty or 0
                    unit_price = detail.product_price or 0.0
                    vat_rate = detail.id_tax or 0
                    
                    # Calcola totale riga (DDT non ha sconti come nel preventivo)
                    total_amount = unit_price * quantity
                    vat_multiplier = 1 + (vat_rate / 100.0) if vat_rate else 1.0
                    total_with_vat = total_amount * vat_multiplier
                    
                    self.add_items_table_row(
                        pdf=pdf,
                        code=code,
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        vat_rate=vat_rate,
                        total_with_vat=total_with_vat
                    )
                    
                    subtotal += total_amount
                    total_with_vat_sum += total_with_vat
                    total_quantity += quantity
            
            # Calcola peso totale
            if hasattr(ddt_data, 'total_weight'):
                total_weight = ddt_data.total_weight or 0.0
            else:
                total_weight = 0.0
            
            # Sezione Info Spedizione e Riepilogo
            self.create_section_title(pdf, 'INFORMAZIONI SPEDIZIONE E RIEPILOGO', spacing_after=2.0)
            
            # Box con info spedizione
            total_weight_kg = total_weight if total_weight > 0 else (shipping.get('weight', 0.0) if shipping else 0.0)
            self.create_simple_table(
                pdf=pdf,
                headers=['Tot. Quant.', 'Peso (Kg)', 'Colli'],
                rows=[[str(int(total_quantity)), f"{total_weight_kg:.3f}", '1']],
                column_width=63,
                spacing_after=2.0
            )
            
            # Porto, Causale, Inizio trasporto
            self.create_simple_table(
                pdf=pdf,
                headers=['Porto', 'Causale trasporto', 'Inizio trasporto'],
                rows=[['-', '-', '-']],
                column_width=63,
                spacing_after=3.0
            )
            
            # Tabella Riepilogo IVA e Totali
            self.create_section_title(pdf, 'RIEPILOGO IVA E TOTALI', spacing_after=1.0)
            
            # Calcolo spese trasporto
            shipping_cost = shipping.get('price_tax_excl', 0.0) if shipping else 0.0
            shipping_cost_with_vat = shipping.get('price_tax_incl', 0.0) if shipping else 0.0
            shipping_vat_percentage = shipping.get('vat_percentage', 0) if shipping else 0
            
            # Calcola totali
            total_doc = ddt_data.total_price_with_tax if hasattr(ddt_data, 'total_price_with_tax') else 0.0
            total_vat = total_doc - subtotal if total_doc > 0 else 0.0
            
            # Preparazione label spese trasporto
            shipping_label = 'Spese trasporto'
            if shipping_vat_percentage:
                shipping_label += f' (+{shipping_vat_percentage}% IVA)'
            
            # Tabella riepilogo IVA
            self.create_vat_summary_table(
                pdf=pdf,
                vat_rate='22%',
                merchandise_amount=subtotal,
                shipping_amount=shipping_cost,
                total_vat=total_vat,
                shipping_label=shipping_label,
                shipping_with_vat=shipping_cost_with_vat
            )
            
            # Blocco totali finali
            self.create_totals_section(
                pdf=pdf,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total_with_vat_sum=total_with_vat_sum,
                total_vat=total_vat,
                total_doc=total_doc
            )
            
            # Sezione Pagamento e Scadenze
            self.create_payment_section(
                pdf=pdf,
                payment_text='-',
                deadlines_text=''
            )
            
            # Firma trasporto
            self.create_transport_signature_section(pdf=pdf)
            
            # Note
            note_text = ddt_data.note if hasattr(ddt_data, 'note') and ddt_data.note else None
            self.add_notes(pdf=pdf, notes=note_text)
            
            # Footer
            self.add_footer(pdf=pdf)
            
            # Ritorna contenuto PDF
            return pdf.output()
            
        except ImportError:
            raise Exception("Libreria fpdf2 non installata. Installare con: pip install fpdf2")
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")
    
    # Metodi helper (simili a PreventivoPDFService)
    
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
        DDTPDFService.insert_logo(pdf, logo_path, x=10, y=8, width=40)
        
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
    def create_address_boxes(
        pdf,
        sender_data: Dict[str, Any],
        recipient_data: Dict[str, Any],
        col_width: float = 95,
        border: int = 1
    ) -> Dict[str, float]:
        """Crea i box mittente e destinatario affiancati"""
        y_start = pdf.get_y()
        
        # MITTENTE (colonna sinistra)
        pdf.set_xy(10, y_start)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 6, 'MITTENTE', border, 0)
        pdf.ln()
        pdf.set_font('Arial', '', 8)
        
        sender_info_parts = []
        if sender_data.get('name'):
            sender_info_parts.append(sender_data['name'])
        if sender_data.get('address'):
            sender_info_parts.append(sender_data['address'])
        if sender_data.get('vat'):
            sender_info_parts.append(f"P.IVA: {sender_data['vat']}")
        if sender_data.get('phone'):
            sender_info_parts.append(f"Tel: {sender_data['phone']}")
        if sender_data.get('email'):
            sender_info_parts.append(f"Email: {sender_data['email']}")
        
        sender_info = "\n".join(sender_info_parts) if sender_info_parts else "Dati mittente non disponibili"
        pdf.multi_cell(col_width, 4, sender_info, border)
        
        y_end_sender = pdf.get_y()
        
        # DESTINATARIO (colonna destra)
        pdf.set_xy(10 + col_width, y_start)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 6, 'DESTINATARIO', border, 0)
        pdf.ln()
        pdf.set_xy(10 + col_width, y_start + 6)
        
        recipient_info_parts = []
        if recipient_data.get('name'):
            recipient_info_parts.append(recipient_data['name'])
        if recipient_data.get('address'):
            recipient_info_parts.append(recipient_data['address'])
        if recipient_data.get('city') and recipient_data.get('postcode'):
            recipient_info_parts.append(f"{recipient_data.get('postcode', '')} {recipient_data.get('city', '')}")
        
        recipient_info = "\n".join(recipient_info_parts) if recipient_info_parts else "Dati destinatario non disponibili"
        
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(col_width, 5, recipient_info, border)
        y_end_recipient = pdf.get_y()
        
        pdf.set_y(max(y_end_sender, y_end_recipient))
        pdf.ln(3)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_order_reference(pdf, id_order: int) -> Dict[str, float]:
        """Aggiunge riferimento ordine (specifico per DDT)"""
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, f"Riferimento ordine: {id_order}", 0, 1)
        pdf.ln(2)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_section_title(pdf, title: str, font_size: int = 9, spacing_after: float = 2.0) -> Dict[str, float]:
        """Crea un titolo di sezione"""
        pdf.set_font('Arial', 'B', font_size)
        pdf.cell(0, 5, title, 0, 1, 'L')
        pdf.ln(spacing_after)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_items_table_header(pdf, column_widths: List[float] = None) -> Dict[str, float]:
        """Crea l'header della tabella articoli"""
        if column_widths is None:
            column_widths = [30, 60, 15, 25, 20, 25]
        
        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(224, 224, 224)
        pdf.cell(column_widths[0], 6, 'Codice', 1, 0, 'L', True)
        pdf.cell(column_widths[1], 6, 'Descrizione', 1, 0, 'L', True)
        pdf.cell(column_widths[2], 6, 'Qta', 1, 0, 'R', True)
        pdf.cell(column_widths[3], 6, 'Prezzo', 1, 0, 'R', True)
        pdf.cell(column_widths[4], 6, 'IVA', 1, 0, 'C', True)
        pdf.cell(column_widths[5], 6, 'Totale', 1, 1, 'R', True)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def add_items_table_row(
        pdf,
        code: str,
        description: str,
        quantity: float,
        unit_price: float,
        vat_rate: float,
        total_with_vat: float,
        column_widths: List[float] = None
    ) -> Dict[str, float]:
        """Aggiunge una riga alla tabella articoli"""
        if column_widths is None:
            column_widths = [30, 60, 15, 25, 20, 25]
        
        pdf.set_font('Arial', '', 8)
        pdf.cell(column_widths[0], 5, str(code)[:15], 1, 0, 'L')
        pdf.cell(column_widths[1], 5, str(description)[:30], 1, 0, 'L')
        pdf.cell(column_widths[2], 5, f"{quantity:.0f}", 1, 0, 'R')
        pdf.cell(column_widths[3], 5, f"{unit_price:.2f} EUR", 1, 0, 'R')
        pdf.cell(column_widths[4], 5, f"{vat_rate}%" if vat_rate else "-", 1, 0, 'C')
        pdf.cell(column_widths[5], 5, f"{total_with_vat:.2f} EUR", 1, 1, 'R')
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_simple_table(
        pdf,
        headers: List[str],
        rows: List[List[str]],
        column_width: float = 63,
        header_font_size: int = 8,
        row_font_size: int = 8,
        spacing_after: float = 2.0
    ) -> Dict[str, float]:
        """Crea una tabella semplice con header e righe"""
        y_start = pdf.get_y()
        
        pdf.set_xy(10, y_start)
        pdf.set_font('Arial', 'B', header_font_size)
        for header in headers:
            pdf.cell(column_width, 4, header, 1, 0, 'L')
        pdf.ln()
        
        pdf.set_font('Arial', '', row_font_size)
        for row in rows:
            for cell in row:
                pdf.cell(column_width, 4, str(cell), 1, 0, 'C')
            pdf.ln()
        
        pdf.ln(spacing_after)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_vat_summary_table(
        pdf,
        vat_rate: str,
        merchandise_amount: float,
        shipping_amount: float,
        total_vat: float,
        shipping_label: str = None,
        shipping_with_vat: float = 0.0
    ) -> Dict[str, float]:
        """Crea la tabella riepilogo IVA"""
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(224, 224, 224)
        pdf.cell(25, 5, 'Aliquota', 1, 0, 'C', True)
        pdf.cell(35, 5, 'Imp. Merce', 1, 0, 'R', True)
        pdf.cell(35, 5, 'Imp. Spese', 1, 0, 'R', True)
        pdf.cell(35, 5, 'Tot. IVA', 1, 0, 'R', True)
        pdf.cell(60, 5, '', 0, 1)
        
        pdf.set_font('Arial', '', 8)
        pdf.cell(25, 5, vat_rate, 1, 0, 'C')
        pdf.cell(35, 5, f"{merchandise_amount:.2f}", 1, 0, 'R')
        pdf.cell(35, 5, f"{shipping_amount:.2f}", 1, 0, 'R')
        pdf.cell(35, 5, f"{total_vat:.2f}", 1, 0, 'R')
        
        if shipping_label:
            pdf.set_xy(140, pdf.get_y())
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(35, 5, shipping_label, 0, 0, 'L')
            pdf.set_font('Arial', '', 8)
            pdf.cell(25, 5, f"{shipping_with_vat:.2f}", 0, 1, 'R')
        else:
            pdf.ln()
        
        pdf.ln(5)
        
        return {'y_end': pdf.get_y()}
    
    @staticmethod
    def create_totals_section(
        pdf,
        subtotal: float,
        shipping_cost: float,
        total_with_vat_sum: float,
        total_vat: float,
        total_doc: float,
        left_col_x: float = 10,
        right_col_x: float = 130,
        label_width: float = 45,
        value_width: float = 25
    ) -> Dict[str, float]:
        """Crea la sezione dei totali finali in due colonne"""
        y_totals = pdf.get_y()
        
        # Colonna sinistra
        pdf.set_xy(left_col_x, y_totals)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(label_width, 5, 'Merce netta', 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(value_width, 5, f"{subtotal:.2f}", 0, 1, 'R')
        
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(label_width, 5, 'Totale imponibile', 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(value_width, 5, f"{subtotal + shipping_cost:.2f}", 0, 1, 'R')
        
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(label_width, 5, 'Spese incasso', 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(value_width, 5, '0,00', 0, 1, 'R')
        
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(label_width, 5, 'Merce lorda', 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(value_width, 5, f"{total_with_vat_sum:.2f}", 0, 1, 'R')
        
        # Colonna destra
        pdf.set_xy(right_col_x, y_totals)
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(label_width, 5, 'Totale IVA', 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(value_width, 5, f"{total_vat:.2f}", 0, 1, 'R')
        
        pdf.set_xy(right_col_x, pdf.get_y())
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(label_width, 5, 'Spese varie', 0, 0, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.cell(value_width, 5, '0,00', 0, 1, 'R')
        
        # Totale documento
        pdf.ln(2)
        pdf.set_xy(right_col_x, pdf.get_y())
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(label_width, 8, 'Totale documento', 0, 0, 'L')
        pdf.cell(value_width, 8, f"{total_doc:.2f} EUR", 0, 1, 'R')
        
        pdf.ln(5)
        
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
    def add_notes(pdf, notes: str, font_size: int = 9) -> Dict[str, float]:
        """Aggiunge una sezione note al PDF"""
        if notes:
            pdf.set_font('Arial', 'B', font_size)
            pdf.cell(0, 5, 'Note:', 0, 1)
            pdf.set_font('Arial', '', font_size)
            pdf.multi_cell(0, 5, notes)
        
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

