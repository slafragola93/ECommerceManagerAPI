from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from src.models.order_document import OrderDocument
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.customer import Customer
from src.models.address import Address
from src.models.tax import Tax
from src.models.product import Product
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema, 
    PreventivoUpdateSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema
)
from src.services.tool import generate_preventivo_reference, calculate_order_totals, apply_order_totals_to_order
from datetime import datetime


class PreventivoRepository:
    """Repository per gestione preventivi"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_next_document_number(self, type_document: str = "preventivo") -> str:
        """Genera il prossimo numero documento sequenziale"""
        # Trova l'ultimo numero per questo tipo di documento
        last_doc = self.db.query(OrderDocument).filter(
            OrderDocument.type_document == type_document
        ).order_by(OrderDocument.document_number.desc()).first()
        
        if last_doc and last_doc.document_number:
            try:
                # Estrai numero e incrementa
                last_number = int(last_doc.document_number)
                return str(last_number + 1).zfill(6)  # Formato 6 cifre con zeri
            except ValueError:
                pass
        
        # Se non ci sono documenti o errore, inizia da 1
        return "000001"
    
    def create_preventivo(self, preventivo_data: PreventivoCreateSchema, user_id: int) -> OrderDocument:
        """Crea un nuovo preventivo"""
        # Genera numero documento
        document_number = self.get_next_document_number("preventivo")
        
        # Gestisci customer
        customer_id = self._handle_customer(preventivo_data, user_id)
        
        # Gestisci addresses
        delivery_address_id = self._handle_delivery_address(preventivo_data, customer_id, user_id)
        invoice_address_id = self._handle_invoice_address(preventivo_data, customer_id, user_id)
        
        # Se address_invoice non è specificato, usa address_delivery
        if invoice_address_id is None:
            invoice_address_id = delivery_address_id
        
        
        # Determina id_tax (usa la tassa più comune tra gli articoli)
        id_tax = None
        if preventivo_data.articoli:
            # Usa la tassa del primo articolo come default
            id_tax = preventivo_data.articoli[0].id_tax
        
        # Crea OrderDocument per preventivo
        order_document = OrderDocument(
            type_document="preventivo",
            document_number=document_number,
            id_customer=customer_id,
            id_address_delivery=delivery_address_id,
            id_address_invoice=invoice_address_id,
            id_tax=id_tax,
            note=preventivo_data.note
        )
        

        
        # Calcola totali prima di aggiungere OrderDocument
        total_weight, total_price = self._calculate_totals_from_articoli(preventivo_data.articoli)
        order_document.total_weight = total_weight
        order_document.total_price = total_price
        
        self.db.add(order_document)
        self.db.flush()  # Per ottenere l'ID
        
        
        # Aggiungi articoli dopo aver ottenuto l'ID
        if preventivo_data.articoli:
            for articolo in preventivo_data.articoli:
                self._create_order_detail(order_document.id_order_document, articolo)
        
        self.db.commit()
        
        return order_document
    
    def _create_order_detail(self, id_order_document: int, articolo: ArticoloPreventivoSchema) -> OrderDetail:
        """Crea order detail per articolo preventivo"""
        # Gestisci prodotto
        product_id = self._handle_product(articolo)
        
        # Se c'è id_product, recupera i dati dal prodotto esistente
        if articolo.id_product:
            product = self.db.query(Product).filter(Product.id_product == articolo.id_product).first()
            product_name = product.name if product else "Prodotto Sconosciuto"
            product_reference = product.reference if product else None
            product_price = articolo.product_price or 0.0  # Usa il prezzo fornito nell'articolo
            product_qty = articolo.product_qty or 1.0
        else:
            # Usa i valori forniti per prodotto personalizzato
            product_name = articolo.product_name or "Prodotto Personalizzato"
            product_reference = articolo.product_reference
            product_price = articolo.product_price or 0.0
            product_qty = articolo.product_qty or 1.0
        
        # Calcola prezzi
        tax = self.db.query(Tax).filter(Tax.id_tax == articolo.id_tax).first()
        tax_rate = tax.percentage if tax else 0.0
        
        prezzo_totale_riga = product_price * product_qty * (1 + tax_rate / 100)
        
        order_detail = OrderDetail(
            id_origin=0,  # Per articoli preventivo
            id_order=0,  # Per articoli preventivo
            id_fiscal_document=0,  # Per articoli preventivo
            id_order_document=id_order_document,
            id_product=product_id,
            product_name=product_name,
            product_reference=product_reference,
            product_qty=product_qty,
            product_weight=articolo.product_weight or 0.0,
            product_price=product_price,
            id_tax=articolo.id_tax,
            reduction_percent=articolo.reduction_percent or 0.0,
            reduction_amount=articolo.reduction_amount or 0.0
        )
        
        self.db.add(order_detail)
        return order_detail
    
    def get_preventivo_by_id(self, id_order_document: int) -> Optional[OrderDocument]:
        """Recupera preventivo per ID"""
        return self.db.query(OrderDocument).filter(
            and_(
                OrderDocument.id_order_document == id_order_document,
                OrderDocument.type_document == "preventivo"
            )
        ).first()
    
    def get_preventivi(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[OrderDocument]:
        """Recupera lista preventivi con filtri"""
        query = self.db.query(OrderDocument).filter(
            OrderDocument.type_document == "preventivo"
        )
        
        if search:
            query = query.filter(
                or_(
                    OrderDocument.document_number.ilike(f"%{search}%"),
                    OrderDocument.note.ilike(f"%{search}%")
                )
            )
        
        return query.order_by(OrderDocument.date_add.desc()).offset(skip).limit(limit).all()
    
    def update_preventivo(self, id_order_document: int, preventivo_data: PreventivoUpdateSchema, user_id: int) -> Optional[OrderDocument]:
        """Aggiorna preventivo"""
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        # Aggiorna campi
        # if preventivo_data.reference is not None:
        #     preventivo.reference = preventivo_data.reference
        if preventivo_data.note is not None:
            preventivo.note = preventivo_data.note
        # if preventivo_data.status is not None:
        #     preventivo.status = preventivo_data.status
        
        # preventivo.updated_by = user_id
        preventivo.updated_at = datetime.now()
        
        self.db.commit()
        return preventivo
    
    def add_articolo(self, id_order_document: int, articolo: ArticoloPreventivoSchema) -> Optional[OrderDetail]:
        """Aggiunge articolo a preventivo"""
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        order_detail = self._create_order_detail(id_order_document, articolo)
        
        # Aggiorna updated_at del preventivo
        preventivo.updated_at = datetime.now()
        
        self.db.commit()
        
        # Ricalcola totali dopo il commit
        self._calculate_totals(id_order_document)
        
        return order_detail
    
    def update_articolo(self, id_order_detail: int, articolo_data: ArticoloPreventivoUpdateSchema) -> Optional[OrderDetail]:
        """Aggiorna articolo in preventivo"""
        order_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not order_detail:
            return None
        
        # Aggiorna campi
        if articolo_data.product_name is not None:
            order_detail.product_name = articolo_data.product_name
        if articolo_data.product_reference is not None:
            order_detail.product_reference = articolo_data.product_reference
        if articolo_data.product_price is not None:
            order_detail.product_price = articolo_data.product_price
        if articolo_data.product_qty is not None:
            order_detail.product_qty = articolo_data.product_qty
        if articolo_data.id_tax is not None:
            order_detail.id_tax = articolo_data.id_tax
        
        # Aggiorna updated_at del preventivo
        preventivo = self.get_preventivo_by_id(order_detail.id_order_document)
        if preventivo:
            preventivo.updated_at = datetime.now()
        
        self.db.commit()
        
        # Ricalcola totali dopo il commit
        self._calculate_totals(order_detail.id_order_document)
        
        return order_detail
    
    def remove_articolo(self, id_order_detail: int) -> bool:
        """Rimuove articolo da preventivo"""
        order_detail = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).first()
        
        if not order_detail:
            return False
        
        # Aggiorna updated_at del preventivo prima di rimuovere l'articolo
        preventivo = self.get_preventivo_by_id(order_detail.id_order_document)
        if preventivo:
            preventivo.updated_at = datetime.now()
        
        self.db.delete(order_detail)
        self.db.commit()
        
        # Ricalcola totali dopo la rimozione e il commit
        self._calculate_totals(order_detail.id_order_document)
        
        return True
    
    def get_articoli_preventivo(self, id_order_document: int) -> List[OrderDetail]:
        """Recupera articoli di un preventivo"""
        return self.db.query(OrderDetail).filter(
            OrderDetail.id_order_document == id_order_document
        ).all()
    
    def calculate_totals(self, id_order_document: int) -> Dict[str, float]:
        """Calcola totali del preventivo"""
        articoli = self.get_articoli_preventivo(id_order_document)
        
        total_imponibile = 0.0
        total_iva = 0.0
        
        for articolo in articoli:
            # Recupera tassa
            tax = self.db.query(Tax).filter(Tax.id_tax == articolo.id_tax).first()
            tax_rate = tax.percentage if tax else 0.0
            
            # Calcola prezzi
            prezzo_netto = articolo.product_price * articolo.product_qty
            prezzo_iva = prezzo_netto * (tax_rate / 100)
            
            total_imponibile += prezzo_netto
            total_iva += prezzo_iva
        
        total_finale = total_imponibile + total_iva
        
        return {
            "total_imponibile": round(total_imponibile, 2),
            "total_iva": round(total_iva, 2),
            "total_finale": round(total_finale, 2)
        }
    
    def convert_to_order(self, id_order_document: int, conversion_data: Dict[str, Any], user_id: int) -> Optional[Order]:
        """Converte preventivo in ordine"""
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        # Crea ordine basandosi sul modello Order corretto
        order = Order(
            id_origin=0,  # Ordine creato dall'app
            id_customer=preventivo.id_customer,
            id_address_delivery=conversion_data.get('id_address_delivery', preventivo.id_address_delivery),
            id_address_invoice=conversion_data.get('id_address_invoice', preventivo.id_address_invoice),
            reference=generate_preventivo_reference(preventivo.document_number),
            id_platform=conversion_data.get('id_platform', 1),  # Default 1
            id_payment=conversion_data.get('id_payment'),
            id_shipping=conversion_data.get('id_shipping'),
            id_sectional=conversion_data.get('id_sectional'),
            id_order_state=conversion_data.get('id_order_state', 1),  # Default 1 (pending)
            is_invoice_requested=conversion_data.get('is_invoice_requested', False),
            is_payed=conversion_data.get('is_payed', False),
            payment_date=conversion_data.get('payment_date'),
            total_weight=preventivo.total_weight or 0.0,
            total_price=preventivo.total_price or 0.0,
            total_discounts=conversion_data.get('total_discounts', 0.0),
            cash_on_delivery=conversion_data.get('cash_on_delivery', 0.0),
            insured_value=conversion_data.get('insured_value', 0.0),
            privacy_note=conversion_data.get('privacy_note'),
            general_note=preventivo.note,
            delivery_date=conversion_data.get('delivery_date')
        )
        
        self.db.add(order)
        self.db.flush()
        
        # Copia articoli dal preventivo all'ordine
        articoli = self.get_articoli_preventivo(id_order_document)
        for articolo in articoli:
            new_detail = OrderDetail(
                id_order=order.id_order,
                id_order_document=id_order_document,
                id_product=articolo.id_product,
                product_name=articolo.product_name,
                product_reference=articolo.product_reference,
                product_qty=articolo.product_qty,
                product_price=articolo.product_price,
                id_tax=articolo.id_tax,
                reduction_percent=articolo.reduction_percent,
                reduction_amount=articolo.reduction_amount
            )
            self.db.add(new_detail)
        
        # Aggiorna stato preventivo (se il campo esiste)
        # preventivo.status = "converted"
        # preventivo.updated_by = user_id
        preventivo.updated_at = datetime.now()
        
        self.db.commit()
        return order
    
    def _handle_customer(self, preventivo_data: PreventivoCreateSchema, user_id: int) -> int:
        """Gestisce customer: crea se necessario, restituisce ID"""
        if preventivo_data.customer.id:
            # Verifica che il customer esista
            customer = self.db.query(Customer).filter(Customer.id_customer == preventivo_data.customer.id).first()
            if not customer:
                raise ValueError(f"Customer con ID {preventivo_data.customer.id} non trovato")
            return preventivo_data.customer.id
        
        elif preventivo_data.customer.data:
            # Crea nuovo customer
            customer = Customer(
                id_origin=preventivo_data.customer.data.id_origin,
                id_lang=preventivo_data.customer.data.id_lang,
                firstname=preventivo_data.customer.data.firstname,
                lastname=preventivo_data.customer.data.lastname,
                email=preventivo_data.customer.data.email
            )
            self.db.add(customer)
            self.db.flush()
            return customer.id_customer
        
        else:
            raise ValueError("Deve essere specificato o id o data per customer")
    
    def _handle_delivery_address(self, preventivo_data: PreventivoCreateSchema, customer_id: int, user_id: int) -> Optional[int]:
        """Gestisce delivery address: crea se necessario, restituisce ID"""
        if not preventivo_data.address_delivery:
            return None
            
        if preventivo_data.address_delivery.id:
            # Verifica che l'address esista
            address = self.db.query(Address).filter(Address.id_address == preventivo_data.address_delivery.id).first()
            if not address:
                raise ValueError(f"Address con ID {preventivo_data.address_delivery.id} non trovato")
            return preventivo_data.address_delivery.id
        
        elif preventivo_data.address_delivery.data:
            # Crea nuovo address
            address = Address(
                id_origin=preventivo_data.address_delivery.data.id_origin,
                id_country=preventivo_data.address_delivery.data.id_country,
                id_customer=customer_id,
                company=preventivo_data.address_delivery.data.company,
                firstname=preventivo_data.address_delivery.data.firstname,
                lastname=preventivo_data.address_delivery.data.lastname,
                address1=preventivo_data.address_delivery.data.address1,
                address2=preventivo_data.address_delivery.data.address2,
                state=preventivo_data.address_delivery.data.state,
                postcode=preventivo_data.address_delivery.data.postcode,
                city=preventivo_data.address_delivery.data.city,
                phone=preventivo_data.address_delivery.data.phone,
                mobile_phone=preventivo_data.address_delivery.data.mobile_phone,
                vat=preventivo_data.address_delivery.data.vat,
                dni=preventivo_data.address_delivery.data.dni,
                pec=preventivo_data.address_delivery.data.pec,
                sdi=preventivo_data.address_delivery.data.sdi,
                ipa=preventivo_data.address_delivery.data.ipa
            )
            self.db.add(address)
            self.db.flush()
            return address.id_address
        
        return None
    
    def _handle_invoice_address(self, preventivo_data: PreventivoCreateSchema, customer_id: int, user_id: int) -> Optional[int]:
        """Gestisce invoice address: crea se necessario, restituisce ID"""
        if not preventivo_data.address_invoice:
            return None
            
        if preventivo_data.address_invoice.id:
            # Verifica che l'address esista
            address = self.db.query(Address).filter(Address.id_address == preventivo_data.address_invoice.id).first()
            if not address:
                raise ValueError(f"Address con ID {preventivo_data.address_invoice.id} non trovato")
            return preventivo_data.address_invoice.id
        
        elif preventivo_data.address_invoice.data:
            # Crea nuovo address
            address = Address(
                id_origin=preventivo_data.address_invoice.data.id_origin,
                id_country=preventivo_data.address_invoice.data.id_country,
                id_customer=customer_id,
                company=preventivo_data.address_invoice.data.company,
                firstname=preventivo_data.address_invoice.data.firstname,
                lastname=preventivo_data.address_invoice.data.lastname,
                address1=preventivo_data.address_invoice.data.address1,
                address2=preventivo_data.address_invoice.data.address2,
                state=preventivo_data.address_invoice.data.state,
                postcode=preventivo_data.address_invoice.data.postcode,
                city=preventivo_data.address_invoice.data.city,
                phone=preventivo_data.address_invoice.data.phone,
                mobile_phone=preventivo_data.address_invoice.data.mobile_phone,
                vat=preventivo_data.address_invoice.data.vat,
                dni=preventivo_data.address_invoice.data.dni,
                pec=preventivo_data.address_invoice.data.pec,
                sdi=preventivo_data.address_invoice.data.sdi,
                ipa=preventivo_data.address_invoice.data.ipa
            )
            self.db.add(address)
            self.db.flush()
            return address.id_address
        
        return None
    
    def _handle_product(self, articolo: ArticoloPreventivoSchema) -> Optional[int]:
        """Gestisce prodotto: usa esistente o crea nuovo con id_origin=0"""
        if articolo.id_product:
            # Verifica che il prodotto esista
            product = self.db.query(Product).filter(Product.id_product == articolo.id_product).first()
            if not product:
                raise ValueError(f"Prodotto con ID {articolo.id_product} non trovato")
            return articolo.id_product
        else:
            # Crea nuovo prodotto personalizzato con id_origin=0
            # Usa i valori forniti o valori di default
            product_name = articolo.product_name or "Prodotto Personalizzato"
            product_reference = articolo.product_reference or f"PREV-{product_name[:10]}"
            
            product = Product(
                id_origin=0,  # Prodotto creato per preventivo
                id_category=None,  # Categoria di default
                id_brand=None,  # Brand di default
                name=product_name,
                sku=product_reference,
                reference=product_reference
            )
            self.db.add(product)
            self.db.flush()
            return product.id_product
    
    def _calculate_totals_from_articoli(self, articoli: List[ArticoloPreventivoSchema]) -> tuple[float, float]:
        """Calcola totali da una lista di articoli usando le funzioni pure"""
        if not articoli:
            return 0.0, 0.0
        
        # Converte ArticoloPreventivoSchema in oggetti simili a OrderDetail
        class MockOrderDetail:
            def __init__(self, articolo):
                self.product_price = articolo.product_price
                self.product_qty = articolo.product_qty
                self.product_weight = articolo.product_weight
                self.id_tax = articolo.id_tax
                self.reduction_percent = articolo.reduction_percent
                self.reduction_amount = articolo.reduction_amount
        
        mock_articoli = [MockOrderDetail(articolo) for articolo in articoli]
        
        # Recupera le percentuali delle tasse
        tax_percentages = self._get_tax_percentages_preventivo(mock_articoli)
        
        # Calcola i totali usando le funzioni pure
        totals = calculate_order_totals(mock_articoli, tax_percentages)
        
        return totals['total_weight'], totals['total_price_with_tax']
    
    def _calculate_totals(self, id_order_document: int):
        """Calcola totali del preventivo basandosi sugli articoli usando le funzioni pure"""
        # Recupera tutti gli articoli del preventivo
        articoli = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_document == id_order_document
        ).all()
        
        if not articoli:
            # Se non ci sono articoli, azzera i totali
            order_document = self.db.query(OrderDocument).filter(
                OrderDocument.id_order_document == id_order_document
            ).first()
            if order_document:
                order_document.total_weight = 0.0
                order_document.total_price = 0.0
                self.db.commit()
            return
        
        # Recupera le percentuali delle tasse
        tax_percentages = self._get_tax_percentages_preventivo(articoli)
        
        # Calcola i totali usando le funzioni pure
        totals = calculate_order_totals(articoli, tax_percentages)
        
        # Aggiorna OrderDocument con i totali
        order_document = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        if order_document:
            # Usa il prezzo con tasse per i preventivi
            order_document.total_weight = totals['total_weight']
            order_document.total_price = totals['total_price_with_tax']
            self.db.commit()

    def _get_tax_percentages_preventivo(self, articoli: list) -> dict:
        """
        Recupera le percentuali delle tasse per gli articoli del preventivo
        
        Args:
            articoli: Lista di OrderDetail objects
            
        Returns:
            dict: Dizionario {id_tax: percentage}
        """
        tax_ids = set()
        for articolo in articoli:
            if hasattr(articolo, 'id_tax') and articolo.id_tax:
                tax_ids.add(articolo.id_tax)
        
        if not tax_ids:
            return {}
        
        taxes = self.db.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
        return {tax.id_tax: tax.percentage for tax in taxes}
