from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
import hashlib
import asyncio
from src.core.settings import get_cache_settings
from datetime import datetime
from src.repository.preventivo_repository import PreventivoRepository
from src.core.cached import cached, invalidate_pattern
from src.repository.customer_repository import CustomerRepository
from src.repository.tax_repository import TaxRepository
from src.repository.payment_repository import PaymentRepository
from src.repository.address_repository import AddressRepository
from src.services.routers.order_document_service import OrderDocumentService
from src.services.routers.product_service import ProductService
from src.repository.product_repository import ProductRepository
from src.core.exceptions import NotFoundException, AlreadyExistsError, ValidationException, ErrorCode
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import (
    extract_preventivo_created_data,
    extract_preventivo_updated_data,
    extract_preventivo_deleted_data,
    extract_preventivo_converted_data,
    extract_bulk_preventivo_deleted_data
)
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema,
    PreventivoUpdateSchema,
    PreventivoResponseSchema,
    PreventivoDetailResponseSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema,
    PaymentPreventivoSchema,
    BulkPreventivoDeleteResponseSchema,
    BulkPreventivoDeleteError,
    BulkPreventivoConvertResponseSchema,
    BulkPreventivoConvertResult,
    BulkPreventivoConvertError,
    BulkRemoveArticoliResponseSchema,
    BulkRemoveArticoliError,
    BulkUpdateArticoliResponseSchema,
    BulkUpdateArticoliError,
    BulkUpdateArticoliItem
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
        # Inizializza ProductService per gestione immagini (DIP - Dependency Inversion)
        self.product_service = ProductService(ProductRepository(db))
    
    @staticmethod
    def _create_params_hash(**params) -> str:
        """
        Crea hash MD5 deterministico dei parametri per chiavi cache.
        Normalizza i parametri (rimuove None, ordina, converte tipi) prima di hashare.
        """
        # Filtra None e normalizza i valori
        normalized = {}
        for key, value in params.items():
            if value is None:
                continue
            # Converti tipi per consistenza
            if isinstance(value, bool):
                normalized[key] = str(value).lower()
            elif isinstance(value, (int, float)):
                normalized[key] = str(value)
            elif isinstance(value, str):
                normalized[key] = value.strip() if value.strip() else ""
            else:
                normalized[key] = str(value)
        
        # Ordina per chiave per consistenza
        sorted_items = sorted(normalized.items())
        # Crea stringa serializzata
        param_str = "|".join(f"{k}={v}" for k, v in sorted_items)
        
        # Hash MD5 deterministico
        return hashlib.md5(param_str.encode('utf-8')).hexdigest()[:8]
    
    def _invalidate_preventivo_cache(self, id_order_document: int, tenant: str = "default", invalidate_lists: bool = True):
        """Helper per invalidare cache preventivo (esegue async in background)"""
        try:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                asyncio.create_task(self._invalidate_preventivo_cache_async(id_order_document, tenant, invalidate_lists))
            else:
                loop.run_until_complete(self._invalidate_preventivo_cache_async(id_order_document, tenant, invalidate_lists))
        except Exception as e:
            # Log errore ma non bloccare l'esecuzione
            pass
    
    async def _invalidate_preventivo_cache_async(self, id_order_document: int, tenant: str = "default", invalidate_lists: bool = True):
        """Invalidazione asincrona cache preventivo"""
        cache_settings = get_cache_settings()
        cache_salt = cache_settings.cache_key_salt
        
        patterns = [
            f"{cache_salt}:preventivo:detail:{tenant}:{id_order_document}:*"
        ]
        if invalidate_lists:
            patterns.append(f"{cache_salt}:preventivo:list:{tenant}:*")
        
        patterns.append(f"{cache_salt}:preventivo:detail:*:{id_order_document}:*")
        if invalidate_lists:
            patterns.append(f"{cache_salt}:preventivo:list:*")
        
        for pattern in patterns:
            try:
                await invalidate_pattern(pattern)
            except Exception:
                pass
    
    def _invalidate_all_preventivi_cache(self, tenant: str = "default"):
        """Helper per invalidare tutta la cache preventivi"""
        try:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                asyncio.create_task(self._invalidate_all_preventivi_cache_async(tenant))
            else:
                loop.run_until_complete(self._invalidate_all_preventivi_cache_async(tenant))
        except Exception:
            pass
    
    async def _invalidate_all_preventivi_cache_async(self, tenant: str = "default"):
        """Invalidazione asincrona completa cache preventivi"""
        cache_settings = get_cache_settings()
        cache_salt = cache_settings.cache_key_salt
        
        pattern = f"{cache_salt}:preventivo:*:{tenant}:*"
        try:
            await invalidate_pattern(pattern)
        except Exception:
            pass
    
    @staticmethod
    def _get_version_from_updated_at(updated_at: Optional[datetime]) -> str:
        """
        Estrae versione da updated_at per chiavi cache.
        Usa data giornaliera (YYYY-MM-DD) invece del timestamp per permettere cache hit durante la giornata.
        """
        if updated_at is None:
            return "0"
        
        try:
            # Converti datetime in data giornaliera (YYYY-MM-DD)
            if isinstance(updated_at, datetime):
                date_str = updated_at.strftime("%Y-%m-%d")
                return date_str
            else:
                # Se non è datetime, prova a parsare come stringa
                if isinstance(updated_at, str):
                    try:
                        dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        return dt.strftime("%Y-%m-%d")
                    except:
                        pass
                # Fallback: usa hash MD5 dei primi 8 caratteri
                return hashlib.md5(str(updated_at).encode('utf-8')).hexdigest()[:8]
        except Exception:
            # Fallback a hash MD5
            return hashlib.md5(str(updated_at).encode('utf-8')).hexdigest()[:8]
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_CREATED,
        data_extractor=extract_preventivo_created_data,
        source="preventivo_service.create_preventivo"
    )
    def create_preventivo(self, preventivo_data: PreventivoCreateSchema, user_id: int, user: dict = None) -> PreventivoResponseSchema:
        """
        Crea nuovo preventivo.
        
        Args:
            preventivo_data: Dati del preventivo da creare
            user_id: ID utente che crea il preventivo
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Preventivo creato con dati completi
        """
        # Valida articoli
        self._validate_articoli(preventivo_data.articoli)
        print(preventivo_data)
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
        
        # Ricarica order_document con le relazioni necessarie (shipping, payment, etc.)
        # Carica esplicitamente la relazione shipping se presente
        if order_document.id_shipping:
            from sqlalchemy.orm import joinedload
            from src.models.order_document import OrderDocument
            order_document = self.db.query(OrderDocument).options(
                joinedload(OrderDocument.shipping)
            ).filter(OrderDocument.id_order_document == order_document.id_order_document).first()
        else:
            self.db.refresh(order_document)
        
        # Recupera customer per nome
        customer = self.customer_repo.get_by_id(order_document.id_customer)
        customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
        
        # Calcola totali
        totals = self.order_doc_service.calculate_totals(order_document.id_order_document, "preventivo")
        
        # Recupera articoli con img_url (PERFORMANCE: batch query)
        articoli = self.order_doc_service.get_articoli_order_document(order_document.id_order_document, "preventivo")
        product_ids = [a.id_product for a in articoli if a.id_product]
        images_map = self.product_service.get_product_images_map(product_ids, self.db)
        articoli_data = [self._format_articolo(articolo, img_url=images_map.get(articolo.id_product)) for articolo in articoli]
        
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
        print(order_document.shipping)
        try:
            if getattr(order_document, "shipping", None):
                s = order_document.shipping
                tax_rate = 0.0
                if getattr(s, 'id_tax', None):
                    tax_rate = float(self.tax_repo.get_percentage_by_id(int(s.id_tax)))
                shipment_obj = PreventivoShipmentSchema(
                    id_shipping=s.id_shipping,
                    id_carrier_api=s.id_carrier_api,
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
                    name=order_document.payment.name,
                    is_complete_payment=order_document.payment.is_complete_payment
                )
            elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                # Se la relazione non è caricata, recupera direttamente
                payment = self.payment_repo.get_by_id(order_document.id_payment)
                if payment:
                    payment_obj = PaymentPreventivoSchema(
                        id_payment=payment.id_payment,
                        name=payment.name,
                        is_complete_payment=payment.is_complete_payment
                    )
        except Exception:
            payment_obj = None

        # Invalidazione cache: invalidare liste (create sempre modifica le liste)
        tenant = f"user_{user_id}"  # Usa user_id come tenant
        self._invalidate_preventivo_cache(order_document.id_order_document, tenant, invalidate_lists=True)
        print(shipment_obj)
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
            is_invoice_requested=order_document.is_invoice_requested,
            is_payed=order_document.is_payed,
            note=order_document.note,
            type_document=order_document.type_document,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=totals["total_finale"],
            total_price_with_tax=totals["total_finale"],
            total_discount=order_document.total_discount,
            date_add=order_document.date_add,
            updated_at=order_document.updated_at,
            articoli=articoli_data
        )
    
    def _get_preventivo_sync(self, id_order_document: int) -> Optional[PreventivoDetailResponseSchema]:
        """Recupera preventivo per ID con indirizzi completi (metodo sincrono interno)"""
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
        # IMPORTANTE: skip_shipping_weight_update=True per preservare il peso dello shipping passato esplicitamente
        self.order_doc_service.update_document_totals(id_order_document, "preventivo", skip_shipping_weight_update=True)
        
        # Ricarica il documento dal database per avere i valori aggiornati
        self.db.refresh(order_document)
        
        # Recupera articoli con img_url (PERFORMANCE: batch query)
        articoli = self.order_doc_service.get_articoli_order_document(id_order_document, "preventivo")
        product_ids = [a.id_product for a in articoli if a.id_product]
        images_map = self.product_service.get_product_images_map(product_ids, self.db)
        articoli_data = [self._format_articolo(articolo, img_url=images_map.get(articolo.id_product)) for articolo in articoli]
        
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
                    print(f"shipping weight: {s.weight}")
                shipment_obj = PreventivoShipmentSchema(
                    id_shipping=s.id_shipping,
                    id_carrier_api=s.id_carrier_api,
                    id_tax=int(s.id_tax) if getattr(s, 'id_tax', None) else 0,
                    tax_rate=tax_rate,
                    weight=float(s.weight or 0.0),
                    price_tax_incl=float(s.price_tax_incl or 0.0),
                    price_tax_excl=float(s.price_tax_excl or 0.0),
                    shipping_message=s.shipping_message
                )
        except Exception:
            shipment_obj = None
        print(order_document.shipping)
        print(shipment_obj)
        print(order_document.shipping.weight)
        print(shipment_obj.weight)
        payment_obj = None
        try:
            if getattr(order_document, "payment", None) and order_document.payment:
                payment_obj = PaymentPreventivoSchema(
                    id_payment=order_document.payment.id_payment,
                    name=order_document.payment.name,
                    is_complete_payment=order_document.payment.is_complete_payment
                )
            elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                # Se la relazione non è caricata, recupera direttamente
                payment = self.payment_repo.get_by_id(order_document.id_payment)
                if payment:
                    payment_obj = PaymentPreventivoSchema(
                        id_payment=payment.id_payment,
                        name=payment.name,
                        is_complete_payment=payment.is_complete_payment
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
            is_payed=order_document.is_payed,
            type_document=order_document.type_document,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=order_document.total_price_with_tax,
            total_discount=order_document.total_discount,
            total_discounts_applied=totals.get("total_discounts_applicati", 0.0),
            articoli=articoli_data,
            order_packages=order_packages_data,
            date_add=order_document.date_add,
            updated_at=order_document.updated_at,
        )
    
    # Cache temporaneamente disabilitata per debug
    # @cached(
    #     preset="preventivo",
    #     key=lambda *args, **kwargs: PreventivoService._get_cache_key_preventivo_detail_static(args, kwargs),
    #     tenant_from_user=False
    # )
    async def get_preventivo(self, id_order_document: int, user=None) -> Optional[PreventivoDetailResponseSchema]:
        """Recupera preventivo per ID con indirizzi completi (con caching)"""
        # Esegui il metodo sincrono in un thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._get_preventivo_sync, id_order_document)
        return result
    
    def _get_preventivi_sync(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None, 
        show_details: bool = False,
        sectionals_ids: Optional[str] = None,
        payments_ids: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[PreventivoResponseSchema]:
        """Recupera lista preventivi (metodo sincrono interno)"""
        order_documents = self.preventivo_repo.get_preventivi(
            skip, limit, search,
            sectionals_ids=sectionals_ids,
            payments_ids=payments_ids,
            date_from=date_from,
            date_to=date_to
        )
        
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
                product_ids = [a.id_product for a in articoli if a.id_product]
                images_map = self.product_service.get_product_images_map(product_ids, self.db)
                articoli_data = [self._format_articolo(articolo, img_url=images_map.get(articolo.id_product)) for articolo in articoli]
            
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
                        id_shipping=s.id_shipping,
                        id_carrier_api=s.id_carrier_api,
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
                        name=order_document.payment.name,
                        is_complete_payment=order_document.payment.is_complete_payment
                    )
                elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                    # Se la relazione non è caricata, recupera direttamente
                    payment = self.payment_repo.get_by_id(order_document.id_payment)
                    if payment:
                        payment_obj = PaymentPreventivoSchema(
                            id_payment=payment.id_payment,
                            name=payment.name,
                            is_complete_payment=payment.is_complete_payment
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
                is_payed=order_document.is_payed,
                reference=None,  # OrderDocument non ha campo reference
                note=order_document.note,
                status=None,  # OrderDocument non ha campo status
                type_document=order_document.type_document,
                total_imponibile=totals["total_imponibile"],
                total_iva=totals["total_iva"],
                total_finale=order_document.total_price_with_tax,
                total_discount=order_document.total_discount,
                articoli=articoli_data,
                order_packages=order_packages_data,
                date_add=order_document.date_add,
                updated_at=order_document.updated_at
            ))
        
        return result
    
    def _get_cache_key_preventivo_detail(self, id_order_document: int, user=None, **kwargs) -> str:
        """Genera chiave cache per dettaglio preventivo con versione"""
        # Tenant comune per tutti gli utenti (preventivi condivisi)
        tenant = "default"
        
        # Recupera updated_at dal database per la versione
        order_document = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if order_document and order_document.updated_at:
            version = self._get_version_from_updated_at(order_document.updated_at)
        else:
            version = "0"
        
        # Le chiavi cache includono il cache_key_salt come prefisso
        cache_settings = get_cache_settings()
        cache_salt = cache_settings.cache_key_salt
        
        return f"{cache_salt}:preventivo:detail:{tenant}:{id_order_document}:{version}"
    
    @staticmethod
    def _get_cache_key_preventivo_detail_static(args: tuple, kwargs: dict) -> str:
        """Helper statico per generare chiave cache dettaglio preventivo"""
        # Estrai self da args
        if len(args) < 1:
            return None
        self = args[0]
        # id_order_document può essere in args[1] o in kwargs
        id_order_document = args[1] if len(args) > 1 else kwargs.get('id_order_document')
        if id_order_document is None:
            return None
        # user è sempre in kwargs se specificato
        user = kwargs.get('user')
        
        # Tenant comune per tutti gli utenti (preventivi condivisi)
        tenant = "default"
        
        # Recupera updated_at dal database per la versione
        order_document = self.preventivo_repo.get_preventivo_by_id(id_order_document)
        if order_document and order_document.updated_at:
            version = PreventivoService._get_version_from_updated_at(order_document.updated_at)
        else:
            version = "0"
        
        # Le chiavi cache includono il cache_key_salt come prefisso
        cache_settings = get_cache_settings()
        cache_salt = cache_settings.cache_key_salt
        
        return f"{cache_salt}:preventivo:detail:{tenant}:{id_order_document}:{version}"
    
    def _get_cache_key_preventivi_list(
        self, 
        skip: int, 
        limit: int, 
        search: Optional[str], 
        show_details: bool, 
        user=None, 
        sectionals_ids: Optional[str] = None,
        payments_ids: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        **kwargs
    ) -> str:
        """Genera chiave cache per lista preventivi con params_hash"""
        # Tenant comune per tutti gli utenti (preventivi condivisi)
        tenant = "default"
        
        # Calcola page da skip e limit
        page = (skip // limit) + 1 if limit > 0 else 1
        
        # Crea params_hash da tutti i parametri
        params = {
            "search": search or "",
            "show_details": show_details,
            "sectionals_ids": sectionals_ids or "",
            "payments_ids": payments_ids or "",
            "date_from": date_from or "",
            "date_to": date_to or ""
        }
        params_hash = self._create_params_hash(**params)
        
        # Le chiavi cache includono il cache_key_salt come prefisso
        cache_settings = get_cache_settings()
        cache_salt = cache_settings.cache_key_salt
        
        return f"{cache_salt}:preventivo:list:{tenant}:{page}:{limit}:{params_hash}"
    
    @staticmethod
    def _get_cache_key_preventivi_list_static(args: tuple, kwargs: dict) -> str:
        """Helper statico per generare chiave cache lista preventivi"""
        # Estrai parametri da args (self è args[0])
        if len(args) < 1:
            return None
        self = args[0]
        # I parametri possono essere in args o kwargs
        skip = args[1] if len(args) > 1 else kwargs.get('skip', 0)
        limit = args[2] if len(args) > 2 else kwargs.get('limit', 100)
        search = args[3] if len(args) > 3 else kwargs.get('search')
        show_details = args[4] if len(args) > 4 else kwargs.get('show_details', False)
        sectionals_ids = args[5] if len(args) > 5 else kwargs.get('sectionals_ids')
        payments_ids = args[6] if len(args) > 6 else kwargs.get('payments_ids')
        date_from = args[7] if len(args) > 7 else kwargs.get('date_from')
        date_to = args[8] if len(args) > 8 else kwargs.get('date_to')
        user = kwargs.get('user')
        
        # Tenant comune per tutti gli utenti (preventivi condivisi)
        tenant = "default"
        
        # Calcola page da skip e limit
        page = (skip // limit) + 1 if limit > 0 else 1
        
        # Crea params_hash da tutti i parametri
        params = {
            "search": search or "",
            "show_details": show_details,
            "sectionals_ids": sectionals_ids or "",
            "payments_ids": payments_ids or "",
            "date_from": date_from or "",
            "date_to": date_to or ""
        }
        params_hash = PreventivoService._create_params_hash(**params)
        
        # Le chiavi cache includono il cache_key_salt come prefisso
        
        cache_settings = get_cache_settings()
        cache_salt = cache_settings.cache_key_salt
        
        return f"{cache_salt}:preventivo:list:{tenant}:{page}:{limit}:{params_hash}"
    
    # Cache temporaneamente disabilitata per debug
    # @cached(
    #     preset="preventivi_list",
    #     key=lambda *args, **kwargs: PreventivoService._get_cache_key_preventivi_list_static(args, kwargs),
    #     tenant_from_user=False
    # )
    async def get_preventivi(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None, 
        show_details: bool = False,
        sectionals_ids: Optional[str] = None,
        payments_ids: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        user=None
    ) -> List[PreventivoResponseSchema]:
        """Recupera lista preventivi (con caching)"""
        # Esegui il metodo sincrono in un thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            self._get_preventivi_sync, 
            skip, limit, search, show_details,
            sectionals_ids, payments_ids, date_from, date_to
        )
        return result
    
    def get_preventivi_stats(
        self,
        search: Optional[str] = None,
        sectionals_ids: Optional[str] = None,
        payments_ids: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calcola statistiche preventivi con filtri applicati"""
        return self.preventivo_repo.get_preventivi_stats(
            search=search,
            sectionals_ids=sectionals_ids,
            payments_ids=payments_ids,
            date_from=date_from,
            date_to=date_to
        )
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_UPDATED,
        data_extractor=extract_preventivo_updated_data,
        source="preventivo_service.update_preventivo"
    )
    def update_preventivo(self, id_order_document: int, preventivo_data: PreventivoUpdateSchema, user_id: int, user: dict = None) -> Optional[PreventivoDetailResponseSchema]:
        """
        Aggiorna preventivo con supporto completo per entità nidificate.
        
        Args:
            id_order_document: ID del preventivo da aggiornare
            preventivo_data: Nuovi dati del preventivo
            user_id: ID utente che aggiorna
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Preventivo aggiornato con dettagli
        """
        # Valida i riferimenti alle entità correlate (incluse quelle nidificate)
        self._validate_preventivo_update_references(preventivo_data)
        
        # Chiama repository con nuova logica che gestisce entità nidificate
        order_document = self.preventivo_repo.update_preventivo(id_order_document, preventivo_data, user_id)
        if not order_document:
            return None
        
        # Invalidazione cache: invalidare dettaglio (tutte versioni) e liste
        tenant = f"user_{user_id}"
        self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        
        # Chiama il metodo sync direttamente (non async per compatibilità)
        return self._get_preventivo_sync(id_order_document)
    
    def add_articolo(self, id_order_document: int, articolo: ArticoloPreventivoSchema) -> Optional[ArticoloPreventivoSchema]:
        """
        Aggiunge articolo a preventivo.
        
        Args:
            id_order_document: ID del preventivo
            articolo: Dati articolo da aggiungere
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Articolo aggiunto
        """
        # Valida articolo
        self._validate_single_articolo(articolo)
        
        order_detail = self.order_doc_service.add_articolo(id_order_document, articolo, "preventivo")
        if not order_detail:
            return None
        
        # Invalidazione cache: invalidare dettaglio e liste
        tenant = "default"
        self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        
        return self._format_articolo(order_detail)
    
    def update_articolo(self, id_order_detail: int, articolo_data: ArticoloPreventivoUpdateSchema, user: dict = None) -> Optional[ArticoloPreventivoSchema]:
        """
        Aggiorna articolo in preventivo.
        
        Args:
            id_order_detail: ID dell'articolo da aggiornare
            articolo_data: Nuovi dati dell'articolo
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Articolo aggiornato
        """
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
        
        # Invalidazione cache: invalidare dettaglio e liste
        id_order_document = order_detail.id_order_document if hasattr(order_detail, 'id_order_document') else None
        if id_order_document:
            tenant = "default"
            self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        
        return self._format_articolo(order_detail)
    
    def remove_articolo(self, id_order_detail: int, user: dict = None) -> bool:
        """
        Rimuove articolo da preventivo.
        
        Args:
            id_order_detail: ID dell'articolo da rimuovere
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            True se rimosso con successo
        """
        # Recupera id_order_document prima di rimuovere
        from src.models.order_detail import OrderDetail
        order_detail = self.db.query(OrderDetail).filter(OrderDetail.id_order_detail == id_order_detail).first()
        id_order_document = order_detail.id_order_document if order_detail else None
        
        result = self.order_doc_service.remove_articolo(id_order_detail, "preventivo")
        
        # Invalidazione cache: invalidare dettaglio e liste
        if result and id_order_document:
            tenant = "default"
            self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        
        return result
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_CONVERTED,
        data_extractor=extract_preventivo_converted_data,
        source="preventivo_service.convert_to_order"
    )
    def convert_to_order(self, id_order_document: int, user_id: int, user: dict = None) -> Optional[Dict[str, Any]]:
        """
        Converte preventivo in ordine.
        
        Args:
            id_order_document: ID del preventivo da convertire
            user_id: ID utente che converte
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Dictionary con id_order e messaggio
        """
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
        
        # Invalidazione cache: invalidare dettaglio e liste
        tenant = f"user_{user_id}"
        self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        
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
    
    def _format_articolo(self, order_detail, img_url: Optional[str] = None) -> ArticoloPreventivoSchema:
        """
        Formatta articolo per risposta con img_url.
        Segue OCP: aperto all'estensione (img_url) senza modificare logica base.
        Segue DIP: dipende da ProductService (abstraction) per recuperare immagini.
        """
        # Fallback image se non fornita
        if img_url is None and order_detail.id_product:
            # Usa ProductService per recuperare immagine (DIP - Dependency Inversion)
            images_map = self.product_service.get_product_images_map([order_detail.id_product], self.db)
            img_url = images_map.get(order_detail.id_product, "media/product_images/fallback/product_not_found.jpg")
        elif img_url is None:
            img_url = "media/product_images/fallback/product_not_found.jpg"
        
        return ArticoloPreventivoSchema(
            id_order_detail=order_detail.id_order_detail,
            id_product=order_detail.id_product,
            product_name=order_detail.product_name,
            product_reference=order_detail.product_reference,
            unit_price_with_tax=order_detail.unit_price_with_tax,
            total_price_net=order_detail.total_price_net,
            total_price_with_tax=order_detail.total_price_with_tax,
            product_qty=order_detail.product_qty,
            product_weight=order_detail.product_weight,
            id_tax=order_detail.id_tax,
            reduction_percent=order_detail.reduction_percent,
            reduction_amount=order_detail.reduction_amount,
            rda=order_detail.rda,
            note=order_detail.note,
            img_url=img_url
        )
    
    def _validate_preventivo_references(self, preventivo_data: PreventivoUpdateSchema) -> None:
        """Valida i riferimenti alle entità correlate nel preventivo (campi semplici)"""
        # Valida payment se specificato
        if preventivo_data.id_payment is not None:
            payment = self.payment_repo.get_by_id(preventivo_data.id_payment)
            if not payment:
                raise NotFoundException(
                    "Payment",
                    preventivo_data.id_payment,
                    {"id_payment": preventivo_data.id_payment}
                )
    
    def _validate_preventivo_update_references(self, preventivo_data: PreventivoUpdateSchema) -> None:
        """Valida tutti i riferimenti nelle entità nidificate per update"""
        # Valida campi semplici (riusa metodo esistente)
        self._validate_preventivo_references(preventivo_data)
        
        # Valida customer.id se presente e non null
        if preventivo_data.customer and preventivo_data.customer.id is not None:
            customer = self.customer_repo.get_by_id(preventivo_data.customer.id)
            if not customer:
                raise NotFoundException("Customer", preventivo_data.customer.id, {"id": preventivo_data.customer.id})
        
        # Valida address_delivery.id se presente e non null
        if preventivo_data.address_delivery and preventivo_data.address_delivery.id is not None:
            address = self.address_repo.get_by_id(preventivo_data.address_delivery.id)
            if not address:
                raise NotFoundException("Address", preventivo_data.address_delivery.id, {"id": preventivo_data.address_delivery.id})
        
        # Valida address_invoice.id se presente e non null
        if preventivo_data.address_invoice and preventivo_data.address_invoice.id is not None:
            address = self.address_repo.get_by_id(preventivo_data.address_invoice.id)
            if not address:
                raise NotFoundException("Address", preventivo_data.address_invoice.id, {"id": preventivo_data.address_invoice.id})
        
        # Valida sectional.id se presente e non null
        if preventivo_data.sectional and preventivo_data.sectional.id is not None:
            from src.models.sectional import Sectional
            sectional = self.db.query(Sectional).filter(Sectional.id_sectional == preventivo_data.sectional.id).first()
            if not sectional:
                raise NotFoundException("Sectional", preventivo_data.sectional.id, {"id": preventivo_data.sectional.id})
        
        # Valida shipping.id se presente e non null
        if preventivo_data.shipping and preventivo_data.shipping.id is not None:
            from src.models.shipping import Shipping
            shipping = self.db.query(Shipping).filter(Shipping.id_shipping == preventivo_data.shipping.id).first()
            if not shipping:
                raise NotFoundException("Shipping", preventivo_data.shipping.id, {"id": preventivo_data.shipping.id})
        
        # Valida articoli (id_tax obbligatorio per nuovi, id_order_detail per update)
        if preventivo_data.articoli:
            for articolo in preventivo_data.articoli:
                # Se è un nuovo articolo (id_order_detail null), id_tax è obbligatorio
                if articolo.id_order_detail is None:
                    if articolo.id_tax is None:
                        raise ValidationException(
                            "id_tax obbligatorio per nuovi articoli",
                            ErrorCode.VALIDATION_ERROR,
                            {"articolo": articolo.model_dump() if hasattr(articolo, 'model_dump') else str(articolo)}
                        )
                    # Valida che id_tax esista
                    tax = self.tax_repo.get_by_id(articolo.id_tax)
                    if not tax:
                        raise NotFoundException("Tax", articolo.id_tax, {"id_tax": articolo.id_tax})
                else:
                    # Se è un update, verifica che id_order_detail esista
                    from src.models.order_detail import OrderDetail
                    order_detail = self.db.query(OrderDetail).filter(
                        OrderDetail.id_order_detail == articolo.id_order_detail
                    ).first()
                    if not order_detail:
                        raise NotFoundException("OrderDetail", articolo.id_order_detail, {"id_order_detail": articolo.id_order_detail})
        
        # Valida order_packages (id_order_package per update)
        if preventivo_data.order_packages:
            for package in preventivo_data.order_packages:
                if package.id_order_package is not None:
                    # Verifica che il package esista
                    from src.models.order_package import OrderPackage
                    order_package = self.db.query(OrderPackage).filter(
                        OrderPackage.id_order_package == package.id_order_package
                    ).first()
                    if not order_package:
                        raise NotFoundException("OrderPackage", package.id_order_package, {"id_order_package": package.id_order_package})
        

    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_DELETED,
        data_extractor=extract_preventivo_deleted_data,
        source="preventivo_service.delete_preventivo"
    )
    def delete_preventivo(self, id_order_document: int, user: dict = None) -> bool:
        """
        Elimina un preventivo.
        
        Args:
            id_order_document: ID del preventivo da eliminare
            user: Contesto utente per eventi (tenant, user_id)
            
        Returns:
            bool: True se eliminato con successo, False se non trovato
        """
        result = self.preventivo_repo.delete_preventivo(id_order_document)
        
        # Invalidazione cache: invalidare dettaglio e liste
        if result:
            tenant = "default"  # Non abbiamo user_id qui
            self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        
        return result
    
    def duplicate_preventivo(self, id_order_document: int, user_id: int, user: dict = None) -> Optional[PreventivoResponseSchema]:
        """
        Duplica un preventivo esistente.
        
        Args:
            id_order_document: ID del preventivo da duplicare
            user_id: ID dell'utente che esegue la duplicazione
            user: Contesto utente per eventi (tenant, user_id)
            
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
        
        # Invalidazione cache: invalidare liste (duplicate modifica le liste)
        tenant = f"user_{user_id}"
        self._invalidate_preventivo_cache(new_preventivo.id_order_document, tenant, invalidate_lists=True)
        
        # Recupera il preventivo duplicato e formatta come PreventivoResponseSchema
        order_document = self.preventivo_repo.get_preventivo_by_id(new_preventivo.id_order_document)
        if not order_document:
            return None
        
        # Recupera cliente per nome
        customer = self.customer_repo.get_by_id(order_document.id_customer)
        customer_name = f"{customer.firstname} {customer.lastname}" if customer else None
        
        # Calcola totali
        totals = self.order_doc_service.calculate_totals(order_document.id_order_document, "preventivo")
        
        # Recupera articoli
        articoli = self.order_doc_service.get_articoli_order_document(order_document.id_order_document, "preventivo")
        product_ids = [a.id_product for a in articoli if a.id_product]
        images_map = self.product_service.get_product_images_map(product_ids, self.db)
        articoli_data = [self._format_articolo(articolo, img_url=images_map.get(articolo.id_product)) for articolo in articoli]
        
        # Recupera order_packages
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
        except Exception:
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
                    name=order_document.payment.name,
                    is_complete_payment=order_document.payment.is_complete_payment
                )
            elif getattr(order_document, "id_payment", None) and order_document.id_payment:
                payment = self.payment_repo.get_by_id(order_document.id_payment)
                if payment:
                    payment_obj = PaymentPreventivoSchema(
                        id_payment=payment.id_payment,
                        name=payment.name,
                        is_complete_payment=payment.is_complete_payment
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
            is_invoice_requested=order_document.is_invoice_requested,
            is_payed=order_document.is_payed,
            reference=None,
            note=order_document.note,
            type_document=order_document.type_document,
            total_imponibile=totals["total_imponibile"],
            total_iva=totals["total_iva"],
            total_finale=totals["total_finale"],
            total_price_with_tax=totals["total_finale"],
            total_discount=order_document.total_discount,
            articoli=articoli_data,
            order_packages=order_packages_data,
            date_add=order_document.date_add,
            updated_at=order_document.updated_at
        )
    
    async def generate_preventivo_pdf(self, id_order_document: int) -> bytes:
        """
        Genera il PDF del preventivo
        
        Args:
            id_order_document: ID del preventivo
            
        Returns:
            bytes: Contenuto del PDF
        """
        try:            
            # Recupera i dati del preventivo
            preventivo_data = await self.get_preventivo(id_order_document)
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
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_BULK_DELETED,
        data_extractor=extract_bulk_preventivo_deleted_data,
        source="preventivo_service.bulk_delete_preventivi"
    )
    def bulk_delete_preventivi(self, ids: List[int], user: dict = None) -> BulkPreventivoDeleteResponseSchema:
        """
        Elimina più preventivi in modo massivo.
        
        Args:
            ids: Lista di ID preventivi da eliminare
            user: Contesto utente per eventi (tenant, user_id)
            
        Returns:
            BulkPreventivoDeleteResponseSchema: Risposta con successi, fallimenti e summary
        """
        successful: List[int] = []
        failed: List[BulkPreventivoDeleteError] = []
        
        for id_order_document in ids:
            try:
                success = self.delete_preventivo(id_order_document)
                if success:
                    successful.append(id_order_document)
                else:
                    failed.append(BulkPreventivoDeleteError(
                        id_order_document=id_order_document,
                        error="NOT_FOUND",
                        reason=f"Preventivo {id_order_document} non trovato"
                    ))
            except Exception as e:
                self.db.rollback()
                failed.append(BulkPreventivoDeleteError(
                    id_order_document=id_order_document,
                    error="DELETE_ERROR",
                    reason=f"Errore durante eliminazione: {str(e)}"
                ))
        
        total = len(ids)
        successful_count = len(successful)
        failed_count = len(failed)
        
        # Invalidazione cache: per ogni ID eliminato + invalidazione generale
        tenant = "default"  # Non abbiamo user_id qui
        for id_order_document in successful:
            self._invalidate_preventivo_cache(id_order_document, tenant, invalidate_lists=True)
        # Invalidazione completa alla fine per sicurezza
        self._invalidate_all_preventivi_cache(tenant)
        
        return BulkPreventivoDeleteResponseSchema(
            successful=successful,
            failed=failed,
            summary={
                "total": total,
                "successful_count": successful_count,
                "failed_count": failed_count
            }
        )
    
    def bulk_convert_to_orders(self, ids: List[int], user_id: int, user: dict = None) -> BulkPreventivoConvertResponseSchema:
        """
        Converte più preventivi in ordini in modo massivo.
        
        Args:
            ids: Lista di ID preventivi da convertire
            user_id: ID utente che converte
            user: Contesto utente per eventi (tenant, user_id)
            
        Returns:
            BulkPreventivoConvertResponseSchema: Risposta con successi, fallimenti e summary
        """
        successful: List[BulkPreventivoConvertResult] = []
        failed: List[BulkPreventivoConvertError] = []
        
        for id_order_document in ids:
            try:
                order = self.preventivo_repo.convert_to_order(id_order_document, user_id)
                if order:
                    # Recupera il preventivo per ottenere document_number
                    preventivo = self.preventivo_repo.get_preventivo_by_id(id_order_document)
                    successful.append(BulkPreventivoConvertResult(
                        id_order_document=id_order_document,
                        id_order=order.id_order,
                        document_number=preventivo.document_number if preventivo else 0
                    ))
                else:
                    failed.append(BulkPreventivoConvertError(
                        id_order_document=id_order_document,
                        error="NOT_FOUND",
                        reason=f"Preventivo {id_order_document} non trovato"
                    ))
            except Exception as e:
                self.db.rollback()
                error_msg = str(e)
                # Determina il tipo di errore
                if "non trovato" in error_msg.lower() or "not found" in error_msg.lower():
                    error_type = "NOT_FOUND"
                elif "campi obbligatori mancanti" in error_msg.lower() or "missing" in error_msg.lower():
                    error_type = "VALIDATION_ERROR"
                else:
                    error_type = "CONVERSION_ERROR"
                
                failed.append(BulkPreventivoConvertError(
                    id_order_document=id_order_document,
                    error=error_type,
                    reason=error_msg
                ))
        
        total = len(ids)
        successful_count = len(successful)
        failed_count = len(failed)
        
        # Invalidazione cache: per ogni ID convertito + invalidazione generale
        tenant = f"user_{user_id}"
        for result in successful:
            self._invalidate_preventivo_cache(result.id_order_document, tenant, invalidate_lists=True)
        # Invalidazione completa alla fine per sicurezza
        self._invalidate_all_preventivi_cache(tenant)
        
        return BulkPreventivoConvertResponseSchema(
            successful=successful,
            failed=failed,
            summary={
                "total": total,
                "successful_count": successful_count,
                "failed_count": failed_count
            }
        )
    
    def bulk_remove_articoli(self, ids: List[int], user: dict = None) -> BulkRemoveArticoliResponseSchema:
        """
        Elimina più articoli in modo massivo.
        Riutilizza remove_articolo per ogni ID (rispetta OCP - Open/Closed Principle).
        
        Args:
            user: Contesto utente per eventi (tenant, user_id)
            ids: Lista di ID order_detail da eliminare
            
        Returns:
            BulkRemoveArticoliResponseSchema: Risposta con successi, fallimenti e summary
        """
        successful: List[int] = []
        failed: List[BulkRemoveArticoliError] = []
        
        for id_order_detail in ids:
            try:
                # Riutilizza il metodo esistente (OCP - non modifica codice esistente)
                success = self.remove_articolo(id_order_detail)
                if success:
                    successful.append(id_order_detail)
                else:
                    failed.append(BulkRemoveArticoliError(
                        id_order_detail=id_order_detail,
                        error="NOT_FOUND",
                        reason=f"Articolo {id_order_detail} non trovato"
                    ))
            except Exception as e:
                self.db.rollback()
                error_msg = str(e)
                # Determina il tipo di errore
                if "non trovato" in error_msg.lower() or "not found" in error_msg.lower():
                    error_type = "NOT_FOUND"
                else:
                    error_type = "REMOVE_ERROR"
                
                failed.append(BulkRemoveArticoliError(
                    id_order_detail=id_order_detail,
                    error=error_type,
                    reason=error_msg
                ))
        
        total = len(ids)
        successful_count = len(successful)
        failed_count = len(failed)
        
        # La cache viene invalidata automaticamente da remove_articolo per ogni articolo
        # Non serve invalidazione aggiuntiva qui (evita duplicazione logica - SRP)
        
        return BulkRemoveArticoliResponseSchema(
            successful=successful,
            failed=failed,
            summary={
                "total": total,
                "successful_count": successful_count,
                "failed_count": failed_count
            }
        )
    
    def bulk_update_articoli(self, articoli: List[BulkUpdateArticoliItem], user: dict = None) -> BulkUpdateArticoliResponseSchema:
        """
        Aggiorna più articoli in modo massivo.
        Riutilizza update_articolo per ogni articolo (rispetta OCP - Open/Closed Principle).
        
        Args:
            articoli: Lista di articoli da aggiornare (contenenti id_order_detail e dati da aggiornare)
            user: Contesto utente per eventi (tenant, user_id)
            
        Returns:
            BulkUpdateArticoliResponseSchema: Risposta con successi, fallimenti e summary
        """
        successful: List[int] = []
        failed: List[BulkUpdateArticoliError] = []
        
        for articolo_item in articoli:
            id_order_detail = articolo_item.id_order_detail
            try:
                # Crea ArticoloPreventivoUpdateSchema dai dati dell'item (escludendo id_order_detail)
                articolo_data = ArticoloPreventivoUpdateSchema(
                    product_name=articolo_item.product_name,
                    product_reference=articolo_item.product_reference,
                    product_price=articolo_item.product_price,
                    product_weight=articolo_item.product_weight,
                    product_qty=articolo_item.product_qty,
                    id_tax=articolo_item.id_tax,
                    reduction_percent=articolo_item.reduction_percent,
                    reduction_amount=articolo_item.reduction_amount,
                    rda=articolo_item.rda,
                    note=articolo_item.note
                )
                
                # Riutilizza il metodo esistente (OCP - non modifica codice esistente)
                result = self.update_articolo(id_order_detail, articolo_data)
                if result:
                    successful.append(id_order_detail)
                else:
                    failed.append(BulkUpdateArticoliError(
                        id_order_detail=id_order_detail,
                        error="NOT_FOUND",
                        reason=f"Articolo {id_order_detail} non trovato"
                    ))
            except Exception as e:
                self.db.rollback()
                error_msg = str(e)
                # Determina il tipo di errore
                if "non trovato" in error_msg.lower() or "not found" in error_msg.lower():
                    error_type = "NOT_FOUND"
                elif "validation" in error_msg.lower() or "invalid" in error_msg.lower():
                    error_type = "VALIDATION_ERROR"
                else:
                    error_type = "UPDATE_ERROR"
                
                failed.append(BulkUpdateArticoliError(
                    id_order_detail=id_order_detail,
                    error=error_type,
                    reason=error_msg
                ))
        
        total = len(articoli)
        successful_count = len(successful)
        failed_count = len(failed)
        
        # La cache viene invalidata automaticamente da update_articolo per ogni articolo
        # Non serve invalidazione aggiuntiva qui (evita duplicazione logica - SRP)
        
        return BulkUpdateArticoliResponseSchema(
            successful=successful,
            failed=failed,
            summary={
                "total": total,
                "successful_count": successful_count,
                "failed_count": failed_count
            }
        )