from typing import List, Optional, Dict, Any
from fastapi import HTTPException
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
from src.models.product import Product
from src.services.core.query_utils import QueryUtils
from src.services.routers.order_document_service import OrderDocumentService
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema, 
    PreventivoUpdateSchema,
    ArticoloPreventivoSchema
)
from src.schemas.address_schema import AddressSchema
from src.services.core.tool import generate_preventivo_reference, calculate_order_totals
from .order_repository import OrderRepository
from .payment_repository import PaymentRepository
from src.schemas.order_schema import OrderSchema
from datetime import datetime


class PreventivoRepository:
    """Repository per gestione preventivi"""
    
    def __init__(self, db: Session):
        self.db = db
        self.order_repository = OrderRepository(db)
        self.payment_repository = PaymentRepository(db)
    
    def get_next_document_number(self, type_document: str = "preventivo") -> int:
        """Genera il prossimo numero documento sequenziale"""
        # Trova l'ultimo numero per questo tipo di documento
        last_doc = self.db.query(OrderDocument).filter(
            OrderDocument.type_document == type_document
        ).order_by(OrderDocument.document_number.desc()).first()
        
        if last_doc and last_doc.document_number:
            try:
                # Restituisce direttamente l'intero incrementato
                return int(last_doc.document_number) + 1
            except (ValueError, TypeError):
                pass
        
        # Se non ci sono documenti o errore, inizia da 1
        return 1
    
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
        
        # Logica per is_payed
        is_payed_value = None
        if preventivo_data.is_payed is not None:
            # Se esplicitamente passato, usa quel valore
            is_payed_value = preventivo_data.is_payed
        elif preventivo_data.id_payment:
            # Se non passato ma c'è id_payment, verifica is_complete_payment
            is_complete = self.payment_repository.is_complete_payment(preventivo_data.id_payment)
            if is_complete:
                is_payed_value = True
        
        # Crea OrderDocument per preventivo
        order_document = OrderDocument(
            type_document="preventivo",
            document_number=document_number,
            id_customer=customer_id,
            id_address_delivery=delivery_address_id,
            id_address_invoice=invoice_address_id,
            id_sectional=sectional_id,
            id_payment=preventivo_data.id_payment if preventivo_data.id_payment else None,
            is_invoice_requested=preventivo_data.is_invoice_requested,  # Default per preventivi
            is_payed=is_payed_value,
            note=preventivo_data.note,
            total_discount=preventivo_data.total_discount if preventivo_data.total_discount is not None else 0.0,
            total_weight=0.0,  # Verrà calcolato da update_document_totals
            total_price_with_tax=0.0  # Verrà calcolato da update_document_totals
        )
        
        
        # Crea Shipping se presente (i totali verranno calcolati dopo)
        shipping_id = None
        if preventivo_data.shipping:
            # Recupera il peso passato (se None, usa 0.0)
            weight = preventivo_data.shipping.weight
            # Crea oggetto Shipping
            shipping = Shipping(
                id_carrier_api=preventivo_data.shipping.id_carrier_api,
                id_shipping_state=1, 
                id_tax=preventivo_data.shipping.id_tax,
                tracking=None,
                weight=float(weight),  # Forza conversione a float
                price_tax_incl=preventivo_data.shipping.price_tax_incl,
                price_tax_excl=preventivo_data.shipping.price_tax_excl,
                shipping_message=preventivo_data.shipping.shipping_message
            )
            self.db.add(shipping)
            self.db.flush()  # Per ottenere l'ID
            shipping_id = shipping.id_shipping

        order_document.id_shipping = shipping_id
        
        self.db.add(order_document)
        self.db.flush()  # Per ottenere l'ID
        
        
        # Aggiungi articoli dopo aver ottenuto l'ID
        if preventivo_data.articoli:
            for articolo in preventivo_data.articoli:
                self._create_order_detail(order_document.id_order_document, articolo)
        
        # Crea order_packages se presenti
        if preventivo_data.order_packages:
            from src.models.order_package import OrderPackage
            for package_data in preventivo_data.order_packages:
                order_package = OrderPackage(
                    id_order_document=order_document.id_order_document,
                    id_order=None,
                    height=package_data.height,
                    width=package_data.width,
                    depth=package_data.depth,
                    length=package_data.length,
                    weight=package_data.weight,
                    value=package_data.value
                )
                self.db.add(order_package)
        
        self.db.commit()

        # Ricalcola i totali usando il metodo centralizzato che include lo sconto totale
        from src.services.routers.order_document_service import OrderDocumentService
        order_doc_service = OrderDocumentService(self.db)
        # Se il peso è stato passato (anche se è 0), non aggiornare il peso della shipping
        skip_shipping_weight_update = (preventivo_data.shipping and preventivo_data.shipping.weight is not None)
        order_doc_service.update_document_totals(order_document.id_order_document, "preventivo", skip_shipping_weight_update=skip_shipping_weight_update)
    
        
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
            product_weight=articolo.product_weight,
            product_price=product_price,
            id_tax=articolo.id_tax,
            reduction_percent=articolo.reduction_percent or 0.0,
            reduction_amount=articolo.reduction_amount or 0.0,
            note=articolo.note
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
    
    def get_preventivi(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None,
        sectionals_ids: Optional[str] = None,
        payments_ids: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[OrderDocument]:
        """Recupera lista preventivi con filtri"""
        
        query = self.db.query(OrderDocument).filter(
            OrderDocument.type_document == "preventivo"
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
    
    def update_preventivo(self, id_order_document: int, preventivo_data: PreventivoUpdateSchema, user_id: int) -> Optional[OrderDocument]:
        """
        Aggiorna preventivo con supporto completo per entità nidificate.
        Orchestratore principale che coordina tutti gli handler.
        """
        # 1. Verifica che non sia convertito (VALIDAZIONE IMPORTANTE)
        self._check_preventivo_not_converted(id_order_document)
        
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        # Traccia se total_discount è stato modificato
        discount_changed = False
        previous_total_discount = preventivo.total_discount if hasattr(preventivo, 'total_discount') else 0.0
        
        # 2. Gestisci customer (se fornito)
        if preventivo_data.customer is not None:
            customer_id = self._handle_customer_update(preventivo_data.customer, preventivo.id_customer, user_id)
            preventivo.id_customer = customer_id
        
        # 3. Gestisci address_delivery (se fornito)
        if preventivo_data.address_delivery is not None:
            delivery_id = self._handle_address_update(
                preventivo_data.address_delivery,
                preventivo.id_address_delivery,
                preventivo.id_customer,
                user_id
            )
            preventivo.id_address_delivery = delivery_id
        
        # 4. Gestisci address_invoice (se fornito)
        if preventivo_data.address_invoice is not None:
            invoice_id = self._handle_address_update(
                preventivo_data.address_invoice,
                preventivo.id_address_invoice,
                preventivo.id_customer,
                user_id
            )
            preventivo.id_address_invoice = invoice_id
        
        # 5. Gestisci sectional (se fornito)
        if preventivo_data.sectional is not None:
            sectional_id = self._handle_sectional_update(preventivo_data.sectional, user_id)
            preventivo.id_sectional = sectional_id
        
        # 6. Gestisci shipping (se fornito)
        if preventivo_data.shipping is not None:
            shipping_id = self._handle_shipping_update(preventivo_data.shipping, preventivo.id_shipping)
            preventivo.id_shipping = shipping_id
        
        # 7. Aggiorna campi semplici (codice esistente)
        if preventivo_data.id_payment is not None:
            preventivo.id_payment = preventivo_data.id_payment
        if preventivo_data.is_invoice_requested is not None:
            preventivo.is_invoice_requested = preventivo_data.is_invoice_requested
        if preventivo_data.is_payed is not None:
            preventivo.is_payed = preventivo_data.is_payed
        if preventivo_data.note is not None:
            preventivo.note = preventivo_data.note
        if preventivo_data.total_discount is not None:
            preventivo.total_discount = preventivo_data.total_discount
            if preventivo.total_discount != previous_total_discount:
                discount_changed = True
        
        # Aggiorna timestamp
        preventivo.updated_at = datetime.now()
        
        self.db.commit()
        
        # 8. Gestisci articoli (smart merge) - DOPO commit preventivo
        if preventivo_data.articoli is not None:
            self._handle_articoli_smart_merge(id_order_document, preventivo_data.articoli)
        
        # 9. Gestisci order_packages (smart merge) - DOPO commit preventivo
        if preventivo_data.order_packages is not None:
            self._handle_order_packages_smart_merge(id_order_document, preventivo_data.order_packages)
        
        # 10. Ricalcola totali (sempre dopo modifiche articoli o se discount cambiato)
        if preventivo_data.articoli is not None or discount_changed:
            from src.services.routers.order_document_service import OrderDocumentService
            order_doc_service = OrderDocumentService(self.db)
            # IMPORTANTE: skip_shipping_weight_update=True per preservare il peso dello shipping passato esplicitamente
            order_doc_service.update_document_totals(id_order_document, "preventivo", skip_shipping_weight_update=True)
        
        return preventivo
    
    # METODI DEPRECATI - Centralizzati in OrderDocumentService
    # def add_articolo, update_articolo, remove_articolo sono ora gestiti da OrderDocumentService
    
    
    
    def convert_to_order(self, id_order_document: int, user_id: int) -> Optional[Order]:
        """Converte preventivo in ordine"""
        preventivo = self.get_preventivo_by_id(id_order_document)
        if not preventivo:
            return None
        
        # Validazione campi obbligatori per la conversione
        missing_fields = []
        if not preventivo.id_address_delivery or preventivo.id_address_delivery <= 0:
            missing_fields.append("id_address_delivery")
        if not preventivo.id_address_invoice or preventivo.id_address_invoice <= 0:
            missing_fields.append("id_address_invoice")
        if not preventivo.id_customer or preventivo.id_customer <= 0:
            missing_fields.append("id_customer")
        if not preventivo.id_shipping or preventivo.id_shipping <= 0:
            missing_fields.append("id_shipping")
        
        if missing_fields:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail=f"Impossibile convertire il preventivo: campi obbligatori mancanti: {', '.join(missing_fields)}"
            )
        
        # Calcola total_price_tax_excl corretto (prodotti + spedizione senza IVA)
        total_price_tax_excl = self._calculate_total_tax_excl_for_order(preventivo)

        # Crea ordine utilizzando OrderRepository per sfruttare tutte le funzioni collegate
        order_data = OrderSchema(
            id_origin=0,  # Ordine creato dall'app
            customer=preventivo.id_customer,
            address_delivery=preventivo.id_address_delivery or 0,  # Default 0 se None
            address_invoice=preventivo.id_address_invoice or 0,  # Default 0 se None
            reference=generate_preventivo_reference(preventivo.document_number),
            id_platform=0,  # Ordine creato dall'app, non da piattaforma esterna
            shipping=preventivo.id_shipping or 0,  # Usa spedizione del preventivo, altrimenti 0
            sectional=preventivo.id_sectional or 0,  # Usa sectional del preventivo, altrimenti 0
            id_order_state=1,  # Default 1 (pending)
            is_invoice_requested=preventivo.is_invoice_requested,
            is_payed=preventivo.is_payed if preventivo.is_payed is not None else False,
            payment_date=None,
            total_weight=preventivo.total_weight or 0.0,
            total_price_tax_excl=total_price_tax_excl,  # Include prodotti + spedizione senza IVA
            total_paid=preventivo.total_price_with_tax,  # total_paid = total_price_with_tax del preventivo
            total_discounts=preventivo.total_discount,  # Porta lo sconto totale dal preventivo
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
        
        # Sposta i package dal preventivo all'ordine
        from src.models.order_package import OrderPackage
        packages = self.db.query(OrderPackage).filter(
            OrderPackage.id_order_document == id_order_document,
            OrderPackage.id_order.is_(None)
        ).all()
        
        if packages:
            # Se ci sono package associati al preventivo, spostali all'ordine
            for package in packages:
                package.id_order = order.id_order
                package.id_order_document = None
            
            self.db.commit()
        # Se non ci sono package, OrderRepository avrà già creato un package di default
        
        # Imposta il total_price_tax_excl corretto dopo aver creato tutti gli articoli
        order.total_price_tax_excl = total_price_tax_excl
        self.db.flush()

        # Ricalcola i totali ordine con il servizio dedicato per garantire coerenza
        from src.services.routers.order_service import OrderService
        OrderService(self.order_repository).recalculate_totals_for_order(order.id_order)
        
        # Aggiorna il preventivo con l'ID dell'ordine creato
        preventivo.id_order = order.id_order
        # preventivo.status = "converted"
        # preventivo.updated_by = user_id
        preventivo.updated_at = datetime.now()
        
        self.db.commit()
        return order
    
    def _handle_customer(self, preventivo_data: PreventivoCreateSchema, user_id: int) -> int:
        """Gestisce customer: crea se necessario, restituisce ID. Se l'email esiste già, restituisce il customer esistente."""
        if preventivo_data.customer.id:
            # Verifica che il customer esista
            customer = self.db.query(Customer).filter(Customer.id_customer == preventivo_data.customer.id).first()
            if not customer:
                raise ValueError(f"Customer con ID {preventivo_data.customer.id} non trovato")
            return preventivo_data.customer.id
        
        elif preventivo_data.customer.data:
            # Controlla se esiste già un customer con questa email (case-insensitive)
            existing_customer = self.db.query(Customer).filter(
                func.lower(Customer.email) == func.lower(preventivo_data.customer.data.email)
            ).first()
            
            if existing_customer:
                # Restituisce il customer esistente invece di crearne uno nuovo
                return existing_customer.id_customer
            
            # Crea nuovo customer solo se l'email non esiste
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
                # Converti Decimal a float per evitare TypeError
                preventivo.total_price_with_tax += float(shipping.price_tax_incl)
        
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
                total_tax_excl += float(articolo.product_price) * int(articolo.product_qty)
        
        # Calcola totale spedizione senza IVA
        if preventivo.id_shipping:
            shipping = self.db.query(Shipping).filter(
                Shipping.id_shipping == preventivo.id_shipping
            ).first()
            if shipping and shipping.price_tax_excl:
                # Converti Decimal a float
                total_tax_excl += float(shipping.price_tax_excl)
        
        return total_tax_excl
    
    def _handle_customer_update(self, customer_field, current_customer_id: int, user_id: int) -> int:
        """
        Gestisce update customer con struttura unificata.
        - Se id presente e non null: aggiorna customer esistente con i campi forniti
        - Se id null: crea nuovo customer
        """
        if customer_field.id is not None:
            # UPDATE customer esistente
            customer = self.db.query(Customer).filter(Customer.id_customer == customer_field.id).first()
            if not customer:
                raise ValueError(f"Customer con ID {customer_field.id} non trovato")
            
            # Aggiorna solo i campi forniti
            if customer_field.firstname is not None:
                customer.firstname = customer_field.firstname
            if customer_field.lastname is not None:
                customer.lastname = customer_field.lastname
            if customer_field.email is not None:
                customer.email = customer_field.email
            if customer_field.id_lang is not None:
                customer.id_lang = customer_field.id_lang
            if customer_field.company is not None:
                customer.company = customer_field.company
            if customer_field.id_origin is not None:
                customer.id_origin = customer_field.id_origin
            
            self.db.commit()
            return customer.id_customer
        else:
            # CREATE nuovo customer (riusa logica esistente ma senza deduplica per email)
            customer = Customer(
                id_origin=customer_field.id_origin or 0,
                id_lang=customer_field.id_lang,
                firstname=customer_field.firstname,
                lastname=customer_field.lastname,
                email=customer_field.email,
                company=customer_field.company
            )
            self.db.add(customer)
            self.db.flush()
            return customer.id_customer
    
    def _handle_address_update(self, address_field, current_address_id: Optional[int], customer_id: int, user_id: int) -> int:
        """
        Gestisce update address con struttura unificata.
        - Se id presente e non null: aggiorna address esistente con i campi forniti
        - Se id null: crea nuovo address
        """
        if address_field.id is not None:
            # UPDATE address esistente
            address = self.db.query(Address).filter(Address.id_address == address_field.id).first()
            if not address:
                raise ValueError(f"Address con ID {address_field.id} non trovato")
            
            # Aggiorna solo i campi forniti
            if address_field.firstname is not None:
                address.firstname = address_field.firstname
            if address_field.lastname is not None:
                address.lastname = address_field.lastname
            if address_field.address1 is not None:
                address.address1 = address_field.address1
            if address_field.address2 is not None:
                address.address2 = address_field.address2
            if address_field.city is not None:
                address.city = address_field.city
            if address_field.postcode is not None:
                address.postcode = address_field.postcode
            if address_field.state is not None:
                address.state = address_field.state
            if address_field.phone is not None:
                address.phone = address_field.phone
            if address_field.mobile_phone is not None:
                address.mobile_phone = address_field.mobile_phone
            if address_field.id_country is not None:
                address.id_country = address_field.id_country
            if address_field.company is not None:
                address.company = address_field.company
            if address_field.vat is not None:
                address.vat = address_field.vat
            if address_field.dni is not None:
                address.dni = address_field.dni
            if address_field.pec is not None:
                address.pec = address_field.pec
            if address_field.sdi is not None:
                address.sdi = address_field.sdi
            if address_field.ipa is not None:
                address.ipa = address_field.ipa
            if address_field.id_origin is not None:
                address.id_origin = address_field.id_origin
            if address_field.id_platform is not None:
                address.id_platform = address_field.id_platform
            
            self.db.commit()
            return address.id_address
        else:
            # CREATE nuovo address
            address = Address(
                id_customer=customer_id,
                id_origin=address_field.id_origin or 0,
                id_country=address_field.id_country,
                id_platform=address_field.id_platform or 0,
                firstname=address_field.firstname,
                lastname=address_field.lastname,
                address1=address_field.address1,
                address2=address_field.address2,
                city=address_field.city,
                postcode=address_field.postcode,
                state=address_field.state,
                phone=address_field.phone,
                mobile_phone=address_field.mobile_phone,
                company=address_field.company,
                vat=address_field.vat,
                dni=address_field.dni,
                pec=address_field.pec,
                sdi=address_field.sdi,
                ipa=address_field.ipa
            )
            self.db.add(address)
            self.db.flush()
            return address.id_address
    
    def _handle_sectional_update(self, sectional_field, user_id: int) -> Optional[int]:
        """
        Gestisce update sectional con struttura unificata.
        - Se id presente e non null: aggiorna sectional esistente
        - Se id null: cerca per nome o crea nuovo
        """
        if sectional_field.id is not None:
            # UPDATE sectional esistente
            sectional = self.db.query(Sectional).filter(Sectional.id_sectional == sectional_field.id).first()
            if not sectional:
                raise ValueError(f"Sectional con ID {sectional_field.id} non trovato")
            
            if sectional_field.name is not None:
                sectional.name = sectional_field.name
            
            self.db.commit()
            return sectional.id_sectional
        else:
            # CREATE nuovo sectional (cerca prima per nome per evitare duplicati)
            if sectional_field.name:
                existing = self.db.query(Sectional).filter(Sectional.name == sectional_field.name).first()
                if existing:
                    return existing.id_sectional
            
            sectional = Sectional(name=sectional_field.name)
            self.db.add(sectional)
            self.db.flush()
            return sectional.id_sectional
    
    def _handle_shipping_update(self, shipping_field, current_shipping_id: Optional[int]) -> Optional[int]:
        """
        Gestisce update shipping con struttura unificata.
        - Se id presente e non null: aggiorna shipping esistente
        - Se id null: crea nuovo shipping
        """
        if shipping_field.id is not None:
            # UPDATE shipping esistente
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == shipping_field.id).first()
            if not shipping:
                raise ValueError(f"Shipping con ID {shipping_field.id} non trovato")
            
            if shipping_field.price_tax_excl is not None:
                shipping.price_tax_excl = shipping_field.price_tax_excl
            if shipping_field.price_tax_incl is not None:
                shipping.price_tax_incl = shipping_field.price_tax_incl
            if shipping_field.id_carrier_api is not None:
                shipping.id_carrier_api = shipping_field.id_carrier_api
            if shipping_field.id_tax is not None:
                shipping.id_tax = shipping_field.id_tax
            if shipping_field.shipping_message is not None:
                shipping.shipping_message = shipping_field.shipping_message
            
            self.db.commit()
            return shipping.id_shipping
        else:
            # CREATE nuovo shipping
            shipping = Shipping(
                id_carrier_api=shipping_field.id_carrier_api,
                id_shipping_state=1,
                id_tax=shipping_field.id_tax,
                tracking=None,
                weight=0.0,
                price_tax_excl=shipping_field.price_tax_excl,
                price_tax_incl=shipping_field.price_tax_incl,
                shipping_message=shipping_field.shipping_message
            )
            self.db.add(shipping)
            self.db.flush()
            return shipping.id_shipping
    
    def _handle_articoli_smart_merge(self, id_order_document: int, articoli: List) -> None:
        """
        Smart merge per articoli:
        1. Identifica articoli da UPDATE (id_order_detail presente nella lista)
        2. Identifica articoli da CREATE (id_order_detail null nella lista)
        3. Identifica articoli da DELETE (esistenti nel DB ma non nella lista)
        4. RIUTILIZZA: OrderDocumentService.update_articolo, add_articolo, remove_articolo
        """
        from src.services.routers.order_document_service import OrderDocumentService
        from src.schemas.preventivo_schema import ArticoloPreventivoUpdateSchema, ArticoloPreventivoSchema
        
        order_doc_service = OrderDocumentService(self.db)
        
        # Recupera articoli esistenti
        existing_articoli = self.db.query(OrderDetail).filter(
            OrderDetail.id_order_document == id_order_document,
            OrderDetail.id_order == 0
        ).all()
        existing_ids = {a.id_order_detail for a in existing_articoli}
        
        # IDs nella lista fornita
        provided_ids = {a.id_order_detail for a in articoli if a.id_order_detail is not None}
        
        # 1. UPDATE + CREATE
        for articolo_data in articoli:
            if articolo_data.id_order_detail is not None:
                # UPDATE esistente (riusa update_articolo)
                update_schema = ArticoloPreventivoUpdateSchema(
                    product_name=articolo_data.product_name,
                    product_reference=articolo_data.product_reference,
                    product_price=articolo_data.product_price,
                    product_weight=articolo_data.product_weight,
                    product_qty=articolo_data.product_qty,
                    id_tax=articolo_data.id_tax,
                    reduction_percent=articolo_data.reduction_percent,
                    reduction_amount=articolo_data.reduction_amount,
                    rda=articolo_data.rda,
                    note=articolo_data.note
                )
                order_doc_service.update_articolo(articolo_data.id_order_detail, update_schema, "preventivo")
            else:
                # CREATE nuovo (riusa add_articolo)
                create_schema = ArticoloPreventivoSchema(
                    id_product=articolo_data.id_product,
                    product_name=articolo_data.product_name,
                    product_reference=articolo_data.product_reference,
                    product_price=articolo_data.product_price or 0.0,
                    product_qty=articolo_data.product_qty or 1,
                    id_tax=articolo_data.id_tax,
                    product_weight=articolo_data.product_weight or 0.0,
                    reduction_percent=articolo_data.reduction_percent or 0.0,
                    reduction_amount=articolo_data.reduction_amount or 0.0,
                    rda=articolo_data.rda,
                    note=articolo_data.note
                )
                order_doc_service.add_articolo(id_order_document, create_schema, "preventivo")
        
        # 2. DELETE articoli non presenti nella lista
        ids_to_delete = existing_ids - provided_ids
        for id_to_delete in ids_to_delete:
            order_doc_service.remove_articolo(id_to_delete, "preventivo")
    
    def _handle_order_packages_smart_merge(self, id_order_document: int, packages: List) -> None:
        """
        Smart merge per order_packages:
        1. Identifica packages da UPDATE (id_order_package presente nella lista)
        2. Identifica packages da CREATE (id_order_package null nella lista)
        3. Identifica packages da DELETE (esistenti nel DB ma non nella lista)
        """
        from src.models.order_package import OrderPackage
        
        # Recupera packages esistenti
        existing_packages = self.db.query(OrderPackage).filter(
            OrderPackage.id_order_document == id_order_document,
            OrderPackage.id_order.is_(None)
        ).all()
        existing_ids = {p.id_order_package for p in existing_packages}
        
        # IDs nella lista fornita
        provided_ids = {p.id_order_package for p in packages if p.id_order_package is not None}
        
        # 1. UPDATE + CREATE
        for package_data in packages:
            if package_data.id_order_package is not None:
                # UPDATE esistente
                package = self.db.query(OrderPackage).filter(
                    OrderPackage.id_order_package == package_data.id_order_package
                ).first()
                if package:
                    if package_data.height is not None:
                        package.height = package_data.height
                    if package_data.width is not None:
                        package.width = package_data.width
                    if package_data.depth is not None:
                        package.depth = package_data.depth
                    if package_data.length is not None:
                        package.length = package_data.length
                    if package_data.weight is not None:
                        package.weight = package_data.weight
                    if package_data.value is not None:
                        package.value = package_data.value
            else:
                # CREATE nuovo
                new_package = OrderPackage(
                    id_order_document=id_order_document,
                    id_order=None,
                    height=package_data.height or 10.0,
                    width=package_data.width or 10.0,
                    depth=package_data.depth or 10.0,
                    length=package_data.length or 10.0,
                    weight=package_data.weight or 0.0,
                    value=package_data.value or 0.0
                )
                self.db.add(new_package)
        
        # 2. DELETE packages non presenti nella lista
        ids_to_delete = existing_ids - provided_ids
        for id_to_delete in ids_to_delete:
            package = self.db.query(OrderPackage).filter(
                OrderPackage.id_order_package == id_to_delete
            ).first()
            if package:
                self.db.delete(package)
        
        self.db.commit()
    
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
                    date_add=datetime.now()
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