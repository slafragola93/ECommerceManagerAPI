from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.repository.preventivo_repository import PreventivoRepository
from src.repository.customer_repository import CustomerRepository
from src.repository.tax_repository import TaxRepository
from src.repository.payment_repository import PaymentRepository
from src.repository.address_repository import AddressRepository
from src.services.routers.order_document_service import OrderDocumentService
from src.core.exceptions import NotFoundException, AlreadyExistsError, ValidationException, ErrorCode
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema,
    PreventivoUpdateSchema,
    PreventivoResponseSchema,
    PreventivoDetailResponseSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema,
    PaymentPreventivoSchema
)
from src.schemas.order_package_schema import OrderPackageResponseSchema
from src.schemas.sectional_schema import SectionalResponseSchema
from src.schemas.preventivo_schema import PreventivoShipmentSchema
from src.schemas.address_schema import AddressResponseSchema
from src.models.customer import Customer
from src.models.address import Address
from src.models.shipping import Shipping
from src.models.app_configuration import AppConfiguration
from src.services.pdf.preventivo_pdf_service import PreventivoPDFService


class PreventivoService:
    """Servizio per gestione preventivi"""
    
    def __init__(self, db: Session):
        self.db = db
        self.preventivo_repo = PreventivoRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.tax_repo = TaxRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.address_repo = AddressRepository(db)
        self.order_doc_service = OrderDocumentService(db)
    
    def create_preventivo(self, preventivo_data: PreventivoCreateSchema, user_id: int) -> PreventivoResponseSchema:
        """Crea nuovo preventivo"""
        # Valida articoli
        self._validate_articoli(preventivo_data.articoli)
        
        # Valida id_payment se fornito
        if preventivo_data.id_payment is not None:
            payment = self.payment_repo.get_by_id(preventivo_data.id_payment)
            if not payment:
                raise NotFoundException(
                    "Payment",
                    preventivo_data.id_payment,
                    {"id_payment": preventivo_data.id_payment}
                )
        
        # Crea preventivo (il repository gestisce customer e address)
        order_document = self.preventivo_repo.create_preventivo(preventivo_data, user_id)
        
        # Recupera customer per nome
        customer = self.customer_repo.get_by_id(order_document.id_customer)
        customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
        
        # Calcola totali
        totals = self.order_doc_service.calculate_totals(order_document.id_order_document, "preventivo")
        
        # Recupera articoli
        articoli = self.order_doc_service.get_articoli_order_document(order_document.id_order_document, "preventivo")
        articoli_data = [self._format_articolo(articolo) for articolo in articoli]
        
        sectional_obj = None
        try:
            if getattr(order_document, "sectional", None):
                sectional_obj = SectionalResponseSchema(
                    id_sectional=order_document.sectional.id_sectional,
                    name=order_document.sectional.name
                )
        except Exception:
            sectional_obj = None

        shipment_obj = None
        try:
            if getattr(order_document, "shipping", None):
                s = order_document.shipping
                tax_rate = 0.0
                if getattr(s, 'id_tax', None):
                    tax_rate = float(self.tax_repo.get_percentage_by_id(int(s.id_tax)))
                shipment_obj = PreventivoShipmentSchema(
                    tax_rate=tax_rate,
                    weight=float(s.weight or 0.0),
                    price_tax_incl=float(s.price_tax_incl or 0.0),
                    price_tax_excl=float(s.price_tax_excl or 0.0),
                    shipping_message=s.shipping_message
                )
        except Exception:
            shipment_obj = None

        payment_obj = None
        try:
            if getattr(order_document, "payment", None) and order_document.payment:
                payment_obj = PaymentPreventivoSchema(
                    id_payment=order_document.payment.id_payment,
                    name=order_document.payment.name
                )
            elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                # Se la relazione non è caricata, recupera direttamente
                payment = self.payment_repo.get_by_id(order_document.id_payment)
                if payment:
                    payment_obj = PaymentPreventivoSchema(
                        id_payment=payment.id_payment,
                        name=payment.name
                    )
        except Exception:
            payment_obj = None

        return PreventivoResponseSchema(
            id_order_document=order_document.id_order_document,
            id_order=order_document.id_order,
            document_number=order_document.document_number,
            id_customer=order_document.id_customer,
            id_address_delivery=order_document.id_address_delivery,
            id_address_invoice=order_document.id_address_invoice,
            sectional=sectional_obj,
            shipping=shipment_obj,
            payment=payment_obj,
            customer_name=customer_name,
            note=order_document.note,
            type_document=order_document.type_document,
            is_invoice_requested=order_document.is_invoice_requested,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=totals["total_finale"],
            total_price_with_tax=totals["total_finale"],
            total_discount=order_document.total_discount,
            apply_discount_to_tax_included=order_document.apply_discount_to_tax_included,
            date_add=order_document.date_add,
            updated_at=order_document.updated_at,
            articoli=articoli_data
        )
    
    def get_preventivo(self, id_order_document: int) -> Optional[PreventivoDetailResponseSchema]:
        """Recupera preventivo per ID con indirizzi completi"""
        order_document = self.preventivo_repo.get_preventivo_by_id(id_order_document)

        if not order_document:
            return None
        
        # Recupera cliente completo
        customer_obj = None
        customer_name = None
        if order_document.id_customer:
            customer = self.customer_repo.get_by_id(order_document.id_customer)
            if customer:
                from src.schemas.customer_schema import CustomerResponseSchema
                customer_obj = CustomerResponseSchema(
                    id_customer=customer.id_customer,
                    id_origin=customer.id_origin,
                    id_lang=customer.id_lang,
                    firstname=customer.firstname,
                    lastname=customer.lastname,
                    email=customer.email,
                    date_add=customer.date_add,
                    addresses=None  # Non includiamo gli indirizzi nel customer del preventivo
                )
                customer_name = f"{customer.firstname} {customer.lastname}"
        
        # Calcola totali (sempre ricalcolati per assicurare correttezza)
        totals = self.order_doc_service.calculate_totals(id_order_document, "preventivo")
        
        # Aggiorna i totali nel database per assicurarsi che siano sempre sincronizzati
        self.order_doc_service.update_document_totals(id_order_document, "preventivo")
        
        # Ricarica il documento dal database per avere i valori aggiornati
        self.db.refresh(order_document)
        
        # Recupera articoli
        articoli = self.order_doc_service.get_articoli_order_document(id_order_document, "preventivo")
        articoli_data = [self._format_articolo(articolo) for articolo in articoli]
        
        # Recupera indirizzi completi
        address_delivery_obj = None
        try:
            if order_document.id_address_delivery:
                address_delivery = self.address_repo.get_by_id(order_document.id_address_delivery)
                if address_delivery:
                    # Costruisci AddressResponseSchema con i dati dell'indirizzo
                    country_obj = None
                    if address_delivery.country:
                        from src.schemas.address_schema import CountryResponseSchema
                        country_obj = CountryResponseSchema(
                            id_country=address_delivery.country.id_country if address_delivery.country else None,
                            name=address_delivery.country.name if address_delivery.country else None,
                            iso_code=address_delivery.country.iso_code if address_delivery.country else None
                        )
                    
                    address_delivery_obj = AddressResponseSchema(
                        id_address=address_delivery.id_address,
                        id_origin=address_delivery.id_origin,
                        id_platform=getattr(address_delivery, 'id_platform', None),
                        customer=None,
                        country=country_obj,
                        company=address_delivery.company,
                        firstname=address_delivery.firstname,
                        lastname=address_delivery.lastname,
                        address1=address_delivery.address1,
                        address2=address_delivery.address2,
                        state=address_delivery.state,
                        postcode=address_delivery.postcode,
                        city=address_delivery.city,
                        phone=address_delivery.phone,
                        mobile_phone=address_delivery.mobile_phone,
                        vat=address_delivery.vat,
                        dni=address_delivery.dni,
                        pec=address_delivery.pec,
                        sdi=address_delivery.sdi,
                        ipa=getattr(address_delivery, 'ipa', None),
                        date_add=address_delivery.date_add
                    )
        except Exception as e:
            # Log dell'errore per debug
            print(f"Errore nel recupero di address_delivery: {str(e)}")
            import traceback
            traceback.print_exc()
            address_delivery_obj = None

        address_invoice_obj = None
        try:
            if order_document.id_address_invoice:
                address_invoice = self.address_repo.get_by_id(order_document.id_address_invoice)
                if address_invoice:
                    # Costruisci AddressResponseSchema con i dati dell'indirizzo
                    country_obj = None
                    if address_invoice.country:
                        from src.schemas.address_schema import CountryResponseSchema
                        country_obj = CountryResponseSchema(
                            id_country=address_invoice.country.id_country if address_invoice.country else None,
                            name=address_invoice.country.name if address_invoice.country else None,
                            iso_code=address_invoice.country.iso_code if address_invoice.country else None
                        )
                    
                    address_invoice_obj = AddressResponseSchema(
                        id_address=address_invoice.id_address,
                        id_origin=address_invoice.id_origin,
                        id_platform=getattr(address_invoice, 'id_platform', None),
                        customer=None,
                        country=country_obj,
                        company=address_invoice.company,
                        firstname=address_invoice.firstname,
                        lastname=address_invoice.lastname,
                        address1=address_invoice.address1,
                        address2=address_invoice.address2,
                        state=address_invoice.state,
                        postcode=address_invoice.postcode,
                        city=address_invoice.city,
                        phone=address_invoice.phone,
                        mobile_phone=address_invoice.mobile_phone,
                        vat=address_invoice.vat,
                        dni=address_invoice.dni,
                        pec=address_invoice.pec,
                        sdi=address_invoice.sdi,
                        ipa=getattr(address_invoice, 'ipa', None),
                        date_add=address_invoice.date_add
                    )
        except Exception as e:
            import traceback
            traceback.print_exc()
            address_invoice_obj = None
        
        sectional_obj = None
        try:
            if getattr(order_document, "sectional", None):
                sectional_obj = SectionalResponseSchema(
                    id_sectional=order_document.sectional.id_sectional,
                    name=order_document.sectional.name
                )
        except Exception:
            sectional_obj = None

        shipment_obj = None
        try:
            if getattr(order_document, "shipping", None):
                s = order_document.shipping
                tax_rate = 0.0
                if getattr(s, 'id_tax', None):
                    tax_rate = float(self.tax_repo.get_percentage_by_id(int(s.id_tax)))
                shipment_obj = PreventivoShipmentSchema(
                    id_tax=int(s.id_tax) if getattr(s, 'id_tax', None) else 0,
                    tax_rate=tax_rate,
                    weight=float(s.weight or 0.0),
                    price_tax_incl=float(s.price_tax_incl or 0.0),
                    price_tax_excl=float(s.price_tax_excl or 0.0),
                    shipping_message=s.shipping_message
                )
        except Exception:
            shipment_obj = None

        payment_obj = None
        try:
            if getattr(order_document, "payment", None) and order_document.payment:
                payment_obj = PaymentPreventivoSchema(
                    id_payment=order_document.payment.id_payment,
                    name=order_document.payment.name
                )
            elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                # Se la relazione non è caricata, recupera direttamente
                payment = self.payment_repo.get_by_id(order_document.id_payment)
                if payment:
                    payment_obj = PaymentPreventivoSchema(
                        id_payment=payment.id_payment,
                        name=payment.name
                    )
        except Exception:
            payment_obj = None

        # Recupera order_packages associati al preventivo
        order_packages_data = []
        try:
            from src.models.order_package import OrderPackage
            packages = self.db.query(OrderPackage).filter(
                OrderPackage.id_order_document == order_document.id_order_document,
                OrderPackage.id_order.is_(None)
            ).all()
            
            for package in packages:
                order_packages_data.append(OrderPackageResponseSchema(
                    id_order_package=package.id_order_package,
                    id_order=package.id_order,
                    id_order_document=package.id_order_document,
                    height=package.height,
                    width=package.width,
                    depth=package.depth,
                    weight=package.weight,
                    length=package.length,
                    value=package.value
                ))
        except Exception as e:
            # Log dell'errore per debug
            print(f"Errore nel recupero di order_packages: {str(e)}")
            import traceback
            traceback.print_exc()
            order_packages_data = []

        return PreventivoDetailResponseSchema(
            id_order_document=order_document.id_order_document,
            id_order=order_document.id_order,
            document_number=order_document.document_number,
            customer=customer_obj,
            address_delivery=address_delivery_obj,
            address_invoice=address_invoice_obj,
            sectional=sectional_obj,
            shipping=shipment_obj,
            payment=payment_obj,
            customer_name=customer_name,
            note=order_document.note,
            is_invoice_requested=order_document.is_invoice_requested,
            type_document=order_document.type_document,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=order_document.total_price_with_tax,
            total_discount=order_document.total_discount,
            apply_discount_to_tax_included=order_document.apply_discount_to_tax_included,
            total_discounts_applied=totals.get("total_discounts_applicati", 0.0),
            articoli=articoli_data,
            order_packages=order_packages_data,
            date_add=order_document.date_add,
            updated_at=order_document.updated_at,
        )
    
    def get_preventivi(self, skip: int = 0, limit: int = 100, search: Optional[str] = None, show_details: bool = False) -> List[PreventivoResponseSchema]:
        """Recupera lista preventivi"""
        order_documents = self.preventivo_repo.get_preventivi(skip, limit, search)
        
        result = []
        for order_document in order_documents:
            # Recupera cliente
            customer = self.customer_repo.get_by_id(order_document.id_customer)
            customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
            
            # Calcola totali
            totals = self.order_doc_service.calculate_totals(order_document.id_order_document, "preventivo")
            
            # Recupera articoli solo se show_details è True
            articoli_data = []
            if show_details:
                articoli = self.order_doc_service.get_articoli_order_document(order_document.id_order_document, "preventivo")
                articoli_data = [self._format_articolo(articolo) for articolo in articoli]
            
            # Recupera order_packages solo se show_details è True
            order_packages_data = []
            if show_details:
                try:
                    from src.models.order_package import OrderPackage
                    packages = self.db.query(OrderPackage).filter(
                        OrderPackage.id_order_document == order_document.id_order_document,
                        OrderPackage.id_order.is_(None)
                    ).all()
                    
                    for package in packages:
                        order_packages_data.append(OrderPackageResponseSchema(
                            id_order_package=package.id_order_package,
                            id_order=package.id_order,
                            id_order_document=package.id_order_document,
                            height=package.height,
                            width=package.width,
                            depth=package.depth,
                            weight=package.weight,
                            length=package.length,
                            value=package.value
                        ))
                except Exception as e:
                    # Log dell'errore per debug
                    print(f"Errore nel recupero di order_packages: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    order_packages_data = []
            sectional_obj = None
            try:
                if getattr(order_document, "sectional", None):
                    sectional_obj = SectionalResponseSchema(
                        id_sectional=order_document.sectional.id_sectional,
                        name=order_document.sectional.name
                    )
            except Exception:
                sectional_obj = None

            shipment_obj = None
            try:
                if getattr(order_document, "shipping", None):
                    s = order_document.shipping
                    tax_rate = 0.0
                    if getattr(s, 'id_tax', None):
                        tax_rate = float(self.tax_repo.get_percentage_by_id(int(s.id_tax)))
                    shipment_obj = PreventivoShipmentSchema(
                        id_tax=int(s.id_tax) if getattr(s, 'id_tax', None) else 0,
                        tax_rate=tax_rate,
                        weight=float(s.weight or 0.0),
                        price_tax_incl=float(s.price_tax_incl or 0.0),
                        price_tax_excl=float(s.price_tax_excl or 0.0),
                        shipping_message=s.shipping_message
                    )
            except Exception:
                shipment_obj = None

            payment_obj = None
            try:
                if getattr(order_document, "payment", None) and order_document.payment:
                    payment_obj = PaymentPreventivoSchema(
                        id_payment=order_document.payment.id_payment,
                        name=order_document.payment.name
                    )
                elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                    # Se la relazione non è caricata, recupera direttamente
                    payment = self.payment_repo.get_by_id(order_document.id_payment)
                    if payment:
                        payment_obj = PaymentPreventivoSchema(
                            id_payment=payment.id_payment,
                            name=payment.name
                        )
            except Exception:
                payment_obj = None

            result.append(PreventivoResponseSchema(
                id_order_document=order_document.id_order_document,
                id_order=order_document.id_order,
                document_number=order_document.document_number,
                id_customer=order_document.id_customer,
                id_address_delivery=order_document.id_address_delivery,
                id_address_invoice=order_document.id_address_invoice,
                sectional=sectional_obj,
                shipping=shipment_obj,
                payment=payment_obj,
                customer_name=customer_name,
                is_invoice_requested=order_document.is_invoice_requested,
                reference=None,  # OrderDocument non ha campo reference
                note=order_document.note,
                status=None,  # OrderDocument non ha campo status
                type_document=order_document.type_document,
                total_imponibile=totals["total_imponibile"],
                total_iva=totals["total_iva"],
                total_finale=order_document.total_price_with_tax,
                total_discount=order_document.total_discount,
                apply_discount_to_tax_included=order_document.apply_discount_to_tax_included,
                articoli=articoli_data,
                order_packages=order_packages_data,
                date_add=order_document.date_add,
                updated_at=order_document.updated_at
            ))
        
        return result
    
    def update_preventivo(self, id_order_document: int, preventivo_data: PreventivoUpdateSchema, user_id: int) -> Optional[PreventivoDetailResponseSchema]:
        """Aggiorna preventivo"""
        # Valida i riferimenti alle entità correlate se specificati
        self._validate_preventivo_references(preventivo_data)
        
        order_document = self.preventivo_repo.update_preventivo(id_order_document, preventivo_data, user_id)
        if not order_document:
            return None
        
        return self.get_preventivo(id_order_document)
    
    def add_articolo(self, id_order_document: int, articolo: ArticoloPreventivoSchema) -> Optional[ArticoloPreventivoSchema]:
        """Aggiunge articolo a preventivo"""
        # Valida articolo
        self._validate_single_articolo(articolo)
        
        order_detail = self.order_doc_service.add_articolo(id_order_document, articolo, "preventivo")
        if not order_detail:
            return None
        
        return self._format_articolo(order_detail)
    
    def update_articolo(self, id_order_detail: int, articolo_data: ArticoloPreventivoUpdateSchema) -> Optional[ArticoloPreventivoSchema]:
        """Aggiorna articolo in preventivo"""
        # Valida articolo se necessario
        if articolo_data.id_tax is not None:
            tax = self.tax_repo.get_by_id(articolo_data.id_tax)
            if not tax:
                raise NotFoundException(
                    "Tax",
                    articolo_data.id_tax,
                    {"id_tax": articolo_data.id_tax}
                )
        
        order_detail = self.order_doc_service.update_articolo(id_order_detail, articolo_data, "preventivo")
        if not order_detail:
            return None
        
        return self._format_articolo(order_detail)
    
    def remove_articolo(self, id_order_detail: int) -> bool:
        """Rimuove articolo da preventivo"""
        return self.order_doc_service.remove_articolo(id_order_detail, "preventivo")
    
    def convert_to_order(self, id_order_document: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Converte preventivo in ordine"""
        # Verifica che il preventivo esista
        preventivo = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if not preventivo:
            raise NotFoundException("Preventivo", id_order_document)
        
        # Controlla se esiste già un ordine collegato a questo preventivo
        existing_order = self.preventivo_repo.check_if_already_converted(id_order_document)
        if existing_order:
            raise AlreadyExistsError(
                f"Preventivo già convertito in ordine ID {existing_order.id_order}",
                entity_type="Order",
                entity_id=existing_order.id_order,
                details={"id_order_document": id_order_document, "id_order": existing_order.id_order}
            )
        
        # Converte in ordine
        order = self.preventivo_repo.convert_to_order(id_order_document, user_id)
        if not order:
            raise ValidationException(
                "Errore durante la conversione del preventivo in ordine",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"id_order_document": id_order_document}
            )
        
        return {
            "id_order": order.id_order,
            "id_order_document": id_order_document,
            "message": "Preventivo convertito in ordine con successo"
        }
    
    def get_totals(self, id_order_document: int) -> Dict[str, float]:
        """Recupera totali calcolati del preventivo"""
        return self.order_doc_service.calculate_totals(id_order_document, "preventivo")
    
    def _validate_articoli(self, articoli: List[ArticoloPreventivoSchema]) -> None:
        """Valida lista articoli"""
        for articolo in articoli:
            self._validate_single_articolo(articolo)
    
    def _validate_single_articolo(self, articolo: ArticoloPreventivoSchema) -> None:
        """Valida singolo articolo"""
        # Verifica che la tassa esista
        tax = self.tax_repo.get_by_id(articolo.id_tax)
        if not tax:
            raise NotFoundException(
                "Tax",
                articolo.id_tax,
                {"id_tax": articolo.id_tax}
            )
        
        # Se è un prodotto esistente, verifica che esista
        if articolo.id_product is not None:
            # Qui potresti aggiungere validazione per prodotti esistenti
            pass
    
    def _format_articolo(self, order_detail) -> ArticoloPreventivoSchema:
        """Formatta articolo per risposta"""
        return ArticoloPreventivoSchema(
            id_order_detail=order_detail.id_order_detail,
            id_product=order_detail.id_product,
            product_name=order_detail.product_name,
            product_reference=order_detail.product_reference,
            product_price=order_detail.product_price,
            product_qty=order_detail.product_qty,
            product_weight=order_detail.product_weight,
            id_tax=order_detail.id_tax,
            reduction_percent=order_detail.reduction_percent,
            reduction_amount=order_detail.reduction_amount,
            rda=order_detail.rda
        )
    
    def _validate_preventivo_references(self, preventivo_data: PreventivoUpdateSchema) -> None:
        """Valida i riferimenti alle entità correlate nel preventivo"""
        # Valida tassa se specificata
        if preventivo_data.id_tax is not None:
            tax = self.tax_repo.get_by_id(preventivo_data.id_tax)
            if not tax:
                raise NotFoundException(
                    "Tax",
                    preventivo_data.id_tax,
                    {"id_tax": preventivo_data.id_tax}
                )
        
        # Valida customer se specificato
        if preventivo_data.id_customer is not None:
            customer = self.customer_repo.get_by_id(preventivo_data.id_customer)
            if not customer:
                raise NotFoundException(
                    "Customer",
                    preventivo_data.id_customer,
                    {"id_customer": preventivo_data.id_customer}
                )
        
        # Valida payment se specificato
        if preventivo_data.id_payment is not None:
            payment = self.payment_repo.get_by_id(preventivo_data.id_payment)
            if not payment:
                raise NotFoundException(
                    "Payment",
                    preventivo_data.id_payment,
                    {"id_payment": preventivo_data.id_payment}
                )
        
        # Note: Per gli altri campi (address, sectional, shipping) potresti aggiungere validazioni simili
        # se necessario, ma per ora lasciamo la validazione al livello del database
    
    def delete_preventivo(self, id_order_document: int) -> bool:
        """
        Elimina un preventivo
        
        Args:
            id_order_document: ID del preventivo da eliminare
            
        Returns:
            bool: True se eliminato con successo, False se non trovato
        """
        return self.preventivo_repo.delete_preventivo(id_order_document)
    
    def duplicate_preventivo(self, id_order_document: int, user_id: int) -> Optional[PreventivoResponseSchema]:
        """
        Duplica un preventivo esistente
        
        Args:
            id_order_document: ID del preventivo da duplicare
            user_id: ID dell'utente che esegue la duplicazione
            
        Returns:
            PreventivoResponseSchema: Il nuovo preventivo duplicato, None se il preventivo originale non esiste
        """
        # Verifica che il preventivo originale esista
        original_preventivo = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if not original_preventivo:
            return None
        
        # Duplica il preventivo
        new_preventivo = self.preventivo_repo.duplicate_preventivo(id_order_document, user_id)
        if not new_preventivo:
            return None
        
        # Restituisce il preventivo duplicato usando la logica esistente
        return self.get_preventivo(new_preventivo.id_order_document)
    
    def generate_preventivo_pdf(self, id_order_document: int) -> bytes:
        """
        Genera il PDF del preventivo
        
        Args:
            id_order_document: ID del preventivo
            
        Returns:
            bytes: Contenuto del PDF
        """
        try:            
            # Recupera i dati del preventivo
            preventivo_data = self.get_preventivo(id_order_document)
            if not preventivo_data:
                raise NotFoundException("Preventivo", id_order_document)
            
            # Recupera OrderDocument per accedere agli ID indirizzi
            order_document = self.preventivo_repo.get_preventivo_by_id(id_order_document)
            if not order_document:
                raise NotFoundException("OrderDocument", id_order_document)
            
            # Recupera dati cliente
            customer_data = None
            if order_document.id_customer:
                customer = self.db.query(Customer).filter(Customer.id_customer == order_document.id_customer).first()
                if customer:
                    customer_data = {
                        "id_customer": customer.id_customer,
                        "firstname": customer.firstname,
                        "lastname": customer.lastname,
                        "email": customer.email
                    }
            
            # Recupera indirizzo di consegna
            address_delivery_data = None
            if order_document.id_address_delivery:
                address = self.db.query(Address).filter(Address.id_address == order_document.id_address_delivery).first()
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
            

            # Recupera dati spedizione
            shipping_data = None
            shipping_vat_percentage = 0
            if order_document.id_shipping:
                shipping = self.db.query(Shipping).filter(Shipping.id_shipping == order_document.id_shipping).first()
                if shipping:
                    if shipping.id_tax:
                        shipping_vat_percentage = float(self.tax_repo.get_percentage_by_id(int(shipping.id_tax)))
                    shipping_data = {
                        "id_shipping": shipping.id_shipping,
                        "price_tax_incl": shipping.price_tax_incl,
                        "price_tax_excl": shipping.price_tax_excl,
                        "weight": shipping.weight,
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
            
            # Usa PreventivoPDFService per generare il PDF
            pdf_service = PreventivoPDFService(
                db_session=self.db,
                preventivo_repo=self.preventivo_repo,
                customer_repo=self.customer_repo,
                tax_repo=self.tax_repo,
                order_doc_service=self.order_doc_service
            )
            
            return pdf_service.generate_pdf(
                preventivo_data=preventivo_data,
                order_document=order_document,
                customer_data=customer_data,
                address_delivery_data=address_delivery_data,
                shipping_data=shipping_data,
                shipping_vat_percentage=shipping_vat_percentage,
                sender_config=sender_config,
                logo_path=logo_path
            )
            
        except ImportError:
            raise Exception("Libreria fpdf2 non installata. Installare con: pip install fpdf2")
        except Exception as e:
            raise Exception(f"Errore durante la generazione del PDF: {str(e)}")