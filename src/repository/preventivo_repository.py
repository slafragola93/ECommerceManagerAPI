from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from src.models.order_document import OrderDocument
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.customer import Customer
from src.models.address import Address
from src.models.tax import Tax
from src.models.shipping import Shipping
from src.models.sectional import Sectional
from src.services.core.tool import calculate_amount_with_percentage
from src.models.product import Product
from src.services.routers.order_document_service import OrderDocumentService
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema, 
    PreventivoUpdateSchema,
    ArticoloPreventivoSchema
)
from src.schemas.address_schema import AddressSchema
from src.services.core.tool import generate_preventivo_reference, calculate_order_totals
from .order_repository import OrderRepository
from src.schemas.order_schema import OrderSchema
from datetime import datetime


class PreventivoRepository:
    """Repository per gestione preventivi"""
    
    def __init__(self, db: Session):
        self.db = db
        self.order_repository = OrderRepository(db)
    
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
        
        # Gestisci sectional
        sectional_id = self._handle_sectional(preventivo_data, user_id)
        
        # Gestisci addresses
        delivery_address_id = self._handle_delivery_address(preventivo_data, customer_id, user_id)
        invoice_address_id = self._handle_invoice_address(preventivo_data, customer_id, user_id, delivery_address_id)
        
        # Se address_invoice non è specificato, usa address_delivery
        if invoice_address_id is None:
            invoice_address_id = delivery_address_id
        
        # Crea OrderDocument per preventivo
        order_document = OrderDocument(
            type_document="preventivo",
            document_number=document_number,
            id_customer=customer_id,
            id_address_delivery=delivery_address_id,
            id_address_invoice=invoice_address_id,
            id_sectional=sectional_id,
            is_invoice_requested=preventivo_data.is_invoice_requested,  # Default per preventivi
            note=preventivo_data.note
        )
        
        
        # Calcola totali prima di aggiungere OrderDocument
        total_weight, total_price_with_tax = self._calculate_totals_from_articoli_with_tax(preventivo_data.articoli)
        
        # Crea Shipping se presente e aggiungi al totale
        shipping_id = None
        if preventivo_data.shipping:
            # Crea oggetto Shipping
            shipping = Shipping(
                id_carrier_api=preventivo_data.shipping.id_carrier_api,  # Non necessario per preventivi
                id_shipping_state=1, 
                id_tax=preventivo_data.shipping.id_tax,
                tracking=None,
                weight=total_weight,  # Imposta automaticamente dal total_weight dei prodotti
                price_tax_incl=preventivo_data.shipping.price_tax_incl,
                price_tax_excl=preventivo_data.shipping.price_tax_excl,
                shipping_message=preventivo_data.shipping.shipping_message
            )
            self.db.add(shipping)
            self.db.flush()  # Per ottenere l'ID
            shipping_id = shipping.id_shipping
            
            # Aggiungi le spese di spedizione al totale
            total_price_with_tax += preventivo_data.shipping.price_tax_incl
        
        order_document.total_weight = total_weight
        order_document.total_price_with_tax = total_price_with_tax
        order_document.id_shipping = shipping_id
        
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
        
        # Crea direttamente l'OrderDetail
        order_detail = OrderDetail(
            id_origin=0,  # Per articoli preventivo
            id_order=0,  # Per articoli preventivo
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
        self.db.flush()  # Per ottenere l'ID
        
        return order_detail
    
    def get_preventivo_by_id(self, id_order_document: int) -> Optional[OrderDocument]:
        """Recupera preventivo per ID"""
        return self.db.query(OrderDocument).filter(
            and_(
                OrderDocument.id_order_document == id_order_document
            )
        ).first()
    
    def _check_preventivo_not_converted(self, id_order_document: int):
        """Verifica che il preventivo non sia stato convertito in ordine"""
        # Recupera solo il campo id_order per verificare se è stato convertito
        result = self.db.query(OrderDocument.id_order).filter(
                OrderDocument.id_order_document == id_order_document
        ).first()
        if not result:
            raise ValueError(f"Preventivo con ID {id_order_document} non trovato")
        
        if result.id_order != 0 and result.id_order is not None:
            raise ValueError("Il preventivo è stato già convertito in ordine. Per tanto, non è possibile effettuare modifiche.")
    
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
        
        # Aggiorna campi modificabili
        if preventivo_data.id_order is not None:
            preventivo.id_order = preventivo_data.id_order
        if preventivo_data.id_tax is not None:
            preventivo.id_tax = preventivo_data.id_tax
        if preventivo_data.id_address_delivery is not None:
            preventivo.id_address_delivery = preventivo_data.id_address_delivery
        if preventivo_data.id_address_invoice is not None:
            preventivo.id_address_invoice = preventivo_data.id_address_invoice
        if preventivo_data.id_customer is not None:
            preventivo.id_customer = preventivo_data.id_customer
        if preventivo_data.id_sectional is not None:
            preventivo.id_sectional = preventivo_data.id_sectional
        if preventivo_data.id_shipping is not None:
            preventivo.id_shipping = preventivo_data.id_shipping
        if preventivo_data.is_invoice_requested is not None:
            preventivo.is_invoice_requested = preventivo_data.is_invoice_requested
        if preventivo_data.note is not None:
            preventivo.note = preventivo_data.note
        
        # Aggiorna timestamp
        preventivo.updated_at = datetime.now()
        
        self.db.commit()
        return preventivo
    
    # METODI DEPRECATI - Centralizzati in OrderDocumentService
    # def add_articolo, update_articolo, remove_articolo sono ora gestiti da OrderDocumentService
    
    
    
    def convert_to_order(self, id_order_document: int, user_id: int) -> Optional[Order]:
        """Converte preventivo in ordine"""
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        # Calcola total_price_tax_excl corretto (prodotti + spedizione senza IVA)
        total_price_tax_excl = self._calculate_total_tax_excl_for_order(preventivo)

        # Crea ordine utilizzando OrderRepository per sfruttare tutte le funzioni collegate
        order_data = OrderSchema(
            id_origin=0,  # Ordine creato dall'app
            customer=preventivo.id_customer,
            address_delivery=preventivo.id_address_delivery or 0,  # Default 0 se None
            address_invoice=preventivo.id_address_invoice or 0,  # Default 0 se None
            reference=generate_preventivo_reference(preventivo.document_number),
            id_platform=1,  # Default 1
            shipping=preventivo.id_shipping or 0,  # Usa spedizione del preventivo, altrimenti 0
            sectional=preventivo.id_sectional or 0,  # Usa sectional del preventivo, altrimenti 0
            id_order_state=1,  # Default 1 (pending)
            is_invoice_requested=preventivo.is_invoice_requested,
            is_payed=0,
            payment_date=None,
            total_weight=preventivo.total_weight or 0.0,
            total_price_tax_excl=total_price_tax_excl,  # Include prodotti + spedizione senza IVA
            total_paid=preventivo.total_price_with_tax,  # total_paid = total_price_with_tax del preventivo
            total_discounts=0.0,
            cash_on_delivery=0.0
        )
        
        # Utilizza OrderRepository per creare l'ordine con tutte le funzioni collegate
        order_id = self.order_repository.create(order_data)
        
        # Recupera l'ordine creato
        order = self.db.query(Order).filter(Order.id_order == order_id).first()
        
        order_doc_service = OrderDocumentService(self.db)
        articoli = order_doc_service.get_articoli_order_document(id_order_document, "preventivo")
        for articolo in articoli:
            # Crea order detail utilizzando lo schema e il repository
            from src.schemas.order_detail_schema import OrderDetailSchema
            detail_data = OrderDetailSchema(
                id_origin=articolo.id_origin,
                id_order=order.id_order,
                id_order_document=0,
                id_product=articolo.id_product or 0,  # Default 0 se None
                product_name=articolo.product_name,
                product_reference=articolo.product_reference or "",
                product_qty=articolo.product_qty,
                product_weight=articolo.product_weight or 0.0,
                product_price=articolo.product_price or 0.0,
                id_tax=articolo.id_tax or 0,
                reduction_percent=articolo.reduction_percent or 0.0,
                reduction_amount=articolo.reduction_amount or 0.0
            )
            self.order_repository.order_detail_repository.create(detail_data.model_dump())
        
        # Imposta il total_price_tax_excl corretto dopo aver creato tutti gli articoli
        order.total_price_tax_excl = total_price_tax_excl
        self.db.flush()
        
        # Aggiorna il preventivo con l'ID dell'ordine creato
        preventivo.id_order = order.id_order
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
    
    def _handle_sectional(self, preventivo_data: PreventivoCreateSchema, user_id: int) -> Optional[int]:
        """Gestisce sectional: usa esistente per nome o crea nuovo, restituisce ID"""
        if not preventivo_data.sectional:
            return None
        
        if preventivo_data.sectional.id:
            # Verifica che il sectional esista
            sectional = self.db.query(Sectional).filter(Sectional.id_sectional == preventivo_data.sectional.id).first()
            if not sectional:
                raise ValueError(f"Sectional con ID {preventivo_data.sectional.id} non trovato")
            return preventivo_data.sectional.id
        
        elif preventivo_data.sectional.data:
            # Cerca prima se esiste un sectional con lo stesso nome
            existing_sectional = self.db.query(Sectional).filter(
                Sectional.name == preventivo_data.sectional.data.name
            ).first()
            
            if existing_sectional:
                # Usa il sectional esistente
                return existing_sectional.id_sectional
            
            # Crea nuovo sectional se non esiste
            sectional = Sectional(
                name=preventivo_data.sectional.data.name
            )
            self.db.add(sectional)
            self.db.flush()
            return sectional.id_sectional
        
        return None
    
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
            # Crea nuovo address - ignora id_customer dall'input e usa sempre customer_id generato
            address = Address(
                id_origin=preventivo_data.address_delivery.data.id_origin,
                id_country=preventivo_data.address_delivery.data.id_country,
                id_customer=customer_id,  # Usa sempre l'ID del customer creato/esistente
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
    
    def _handle_invoice_address(self, preventivo_data: PreventivoCreateSchema, customer_id: int, user_id: int, delivery_address_id: Optional[int] = None) -> Optional[int]:
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
            # Controlla se invoice_address è uguale a delivery_address
            if (preventivo_data.address_delivery and 
                preventivo_data.address_delivery.data and 
                self._are_addresses_equal(preventivo_data.address_invoice.data, preventivo_data.address_delivery.data)):
                # Se gli indirizzi sono uguali, usa lo stesso ID
                return delivery_address_id
            # Crea nuovo address - ignora id_customer dall'input e usa sempre customer_id generato
            address = Address(
                id_origin=preventivo_data.address_invoice.data.id_origin,
                id_country=preventivo_data.address_invoice.data.id_country,
                id_customer=customer_id,  # Usa sempre l'ID del customer creato/esistente
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
    
    def _are_addresses_equal(self, addr1: AddressSchema, addr2: AddressSchema) -> bool:
        """
        Confronta due indirizzi per vedere se sono uguali
        
        Args:
            addr1: Primo indirizzo
            addr2: Secondo indirizzo
            
        Returns:
            bool: True se gli indirizzi sono uguali, False altrimenti
        """
        # Confronta i campi principali dell'indirizzo
        return (
            addr1.firstname == addr2.firstname and
            addr1.lastname == addr2.lastname and
            addr1.address1 == addr2.address1 and
            addr1.address2 == addr2.address2 and
            addr1.city == addr2.city and
            addr1.postcode == addr2.postcode and
            addr1.state == addr2.state and
            addr1.id_country == addr2.id_country and
            addr1.company == addr2.company and
            addr1.phone == addr2.phone
        )
    
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
    
    def _calculate_totals_from_articoli_with_tax(self, articoli: List[ArticoloPreventivoSchema]) -> tuple[float, float]:
        """Calcola totali da una lista di articoli con IVA inclusa"""
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
            OrderDetail.id_order_document == id_order_document,
            OrderDetail.id_order == 0  # Solo articoli del preventivo, non dell'ordine
        ).all()
        if not articoli:
            # Se non ci sono articoli, azzera i totali
            order_document = self.db.query(OrderDocument).filter(
                OrderDocument.id_order_document == id_order_document
            ).first()
            if order_document:
                order_document.total_weight = 0.0
                order_document.total_price_with_tax = 0.0
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
            order_document.total_price_with_tax = totals['total_price_with_tax']
            self.db.commit()

    def _recalculate_preventivo_totals(self, id_order_document: int):
        """Ricalcola completamente i totali del preventivo includendo articoli + spedizione"""
        # Recupera il preventivo
        preventivo = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        if not preventivo:
            return
        
        # Ricalcola totali degli articoli
        self._calculate_totals(id_order_document)
        
        # Recupera il preventivo aggiornato
        preventivo = self.db.query(OrderDocument).filter(
            OrderDocument.id_order_document == id_order_document
        ).first()
        
        # Aggiungi la spedizione se presente
        if preventivo.id_shipping:
            shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == preventivo.id_shipping
            ).first()
            if shipping and shipping.price_tax_incl:
                preventivo.total_price_with_tax += shipping.price_tax_incl
        
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
    
    def check_if_already_converted(self, id_order_document: int) -> Optional[Order]:
        """Verifica se il preventivo è già stato convertito in ordine"""
        # Cerca il preventivo
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        # Se il preventivo ha un id_order > 0, è stato convertito
        if preventivo.id_order and preventivo.id_order > 0:
            existing_order = self.db.query(Order).filter(
                Order.id_order == preventivo.id_order
            ).first()
            return existing_order
        
        # Non è stato convertito
        return None
    
    def delete_preventivo(self, id_order_document: int) -> bool:
        """
        Elimina un preventivo e tutti i suoi articoli
        
        Args:
            id_order_document: ID del preventivo da eliminare
            
        Returns:
            bool: True se eliminato con successo, False se non trovato
        """
        preventivo = self.db.query(OrderDocument).filter(
            and_(
                OrderDocument.id_order_document == id_order_document
            )
        ).first()
        
        if not preventivo:
            return False
        
        # Elimina tutti gli articoli associati
        self.db.query(OrderDetail).filter(
            OrderDetail.id_order_document == id_order_document
        ).delete()
        
        # Elimina il preventivo
        self.db.delete(preventivo)
        self.db.commit()
        
        return True
    
    def _calculate_total_tax_excl_for_order(self, preventivo) -> float:
        """
        Calcola il totale senza IVA per un ordine basato sui dati del preventivo.
        Include sia i prodotti che la spedizione.
        
        Args:
            preventivo: Oggetto OrderDocument del preventivo
            
        Returns:
            float: Totale senza IVA (prodotti + spedizione)
        """
        # Recupera tutti gli articoli del preventivo
        articoli = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_document == preventivo.id_order_document,
            OrderDetail.id_order == 0  # Solo articoli del preventivo, non dell'ordine
        ).all()
        
        # Calcola totale prodotti senza IVA
        total_tax_excl = 0.0
        if articoli:
            for articolo in articoli:
                total_tax_excl += articolo.product_price * articolo.product_qty
        
        # Calcola totale spedizione senza IVA
        if preventivo.id_shipping:
            shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == preventivo.id_shipping
            ).first()

            total_tax_excl += shipping.price_tax_excl
        
        return total_tax_excl
    
    def duplicate_preventivo(self, id_order_document: int, user_id: int) -> Optional[OrderDocument]:
        """
        Duplica un preventivo esistente creando una copia con le stesse caratteristiche
        
        Args:
            id_order_document: ID del preventivo da duplicare
            user_id: ID dell'utente che esegue la duplicazione
            
        Returns:
            OrderDocument: Il nuovo preventivo duplicato, None se il preventivo originale non esiste
        """
        # Recupera il preventivo originale
        original_preventivo = self.get_preventivo_by_id(id_order_document)
        if not original_preventivo:
            return None
        
        # Genera nuovo numero documento
        new_document_number = self.get_next_document_number("preventivo")
        
        # Crea una nuova spedizione copiando i dati dell'originale
        new_shipping_id = None
        if original_preventivo.id_shipping:
            original_shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == original_preventivo.id_shipping
            ).first()
            
            if original_shipping:
                new_shipping = Shipping(
                    id_carrier_api=original_shipping.id_carrier_api,
                    id_shipping_state=original_shipping.id_shipping_state,
                    id_tax=original_shipping.id_tax,
                    tracking=None,  # Reset tracking per la nuova spedizione
                    weight=original_shipping.weight,
                    price_tax_incl=original_shipping.price_tax_incl,
                    price_tax_excl=original_shipping.price_tax_excl,
                    shipping_message=original_shipping.shipping_message,
                    date_add=datetime.now().date()
                )
                self.db.add(new_shipping)
                self.db.flush()  # Per ottenere l'ID
                new_shipping_id = new_shipping.id_shipping
        
        # Crea nuovo OrderDocument copiando i dati dell'originale
        new_preventivo = OrderDocument(
            type_document="preventivo",
            document_number=new_document_number,
            id_customer=original_preventivo.id_customer,
            id_address_delivery=original_preventivo.id_address_delivery,
            id_address_invoice=original_preventivo.id_address_invoice,
            id_sectional=original_preventivo.id_sectional,
            id_shipping=new_shipping_id,  # Usa la nuova spedizione creata
            is_invoice_requested=original_preventivo.is_invoice_requested,
            note=f"Copia di {original_preventivo.document_number}" + (f" - {original_preventivo.note}" if original_preventivo.note else ""),
            total_weight=original_preventivo.total_weight,
            total_price_with_tax=original_preventivo.total_price_with_tax
        )
        
        self.db.add(new_preventivo)
        self.db.flush()  # Per ottenere l'ID
        
        # Copia tutti gli articoli del preventivo originale senza ricalcolare i totali
        original_articoli = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_document == id_order_document,
            OrderDetail.id_order == 0  # Solo articoli del preventivo, non dell'ordinem
        ).all()
        
        for articolo in original_articoli:
            # Crea direttamente l'OrderDetail senza utilizzare OrderDetailRepository
            # per evitare il ricalcolo automatico dei totali
            new_articolo = OrderDetail(
                id_origin=articolo.id_origin,
                id_order=0,  # Per articoli preventivo
                id_order_document=new_preventivo.id_order_document,
                id_product=articolo.id_product,
                product_name=articolo.product_name,
                product_reference=articolo.product_reference,
                product_qty=articolo.product_qty,
                product_weight=articolo.product_weight,
                product_price=articolo.product_price,
                id_tax=articolo.id_tax,
                reduction_percent=articolo.reduction_percent,
                reduction_amount=articolo.reduction_amount
            )
            
            # Aggiungi direttamente alla sessione senza ricalcolare i totali
            self.db.add(new_articolo)
        
        self.db.commit()
        
        # I totali del preventivo sono già stati copiati dall'originale
        # Non è necessario ricalcolarli perché sono identici all'originale
        
        return new_preventivo