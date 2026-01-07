import logging
from typing import Optional, List
from src.services.core.tool import format_datetime_ddmmyyyy_hhmmss
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import desc, func, select, or_, String
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, joinedload
from .address_repository import AddressRepository
from .api_carrier_repository import ApiCarrierRepository
from .customer_repository import CustomerRepository
from .lang_repository import LangRepository
from .order_detail_repository import OrderDetailRepository
from .order_package_repository import OrderPackageRepository
from .order_state_repository import OrderStateRepository
from .payment_repository import PaymentRepository
from .platform_repository import PlatformRepository
from .sectional_repository import SectionalRepository
from .shipping_repository import ShippingRepository
from .shipping_state_repository import ShippingStateRepository
from .tax_repository import TaxRepository
from .app_configuration_repository import AppConfigurationRepository
from .. import AddressSchema, SectionalSchema, ShippingSchema, OrderPackageSchema, OrderDetail
from ..models import Order, OrderState, Shipping, Address
from ..models.customer import Customer
from ..models.payment import Payment
from ..models.product import Product
from ..models.order_detail import OrderDetail as OrderDetailModel
from ..models.carrier import Carrier
from ..models.relations.relations import orders_history
from src.schemas.customer_schema import *
from ..schemas.order_schema import OrderSchema, OrderResponseSchema, AllOrderResponseSchema, OrderIdSchema, OrderUpdateSchema
from ..services import QueryUtils
from ..repository.interfaces.order_repository_interface import IOrderRepository


logger = logging.getLogger(__name__)


class OrderRepository(IOrderRepository):
    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

        self.address_repository = AddressRepository(session)
        self.shipping_repository = ShippingRepository(session)
        self.sectional_repository = SectionalRepository(session)
        self.order_state_repository = OrderStateRepository(session)
        self.tax_repository = TaxRepository(session)
        self.customer_repository = CustomerRepository(session)
        self.lang_repository = LangRepository(session)
        self.api_carrier_repository = ApiCarrierRepository(session)
        self.shipping_state_repository = ShippingStateRepository(session)
        self.order_package_repository = OrderPackageRepository(session)
        self.order_detail_repository = OrderDetailRepository(session)
        self.platform_repository = PlatformRepository(session)
        self.payment_repository = PaymentRepository(session)
        self.app_configuration_repository = AppConfigurationRepository(session)

    def get_all(self,
                orders_ids: Optional[str] = None,
                customers_ids: Optional[str] = None,
                order_states_ids: Optional[str] = None,
                shipping_states_ids: Optional[str] = None,
                delivery_countries_ids: Optional[str] = None,
                store_ids: Optional[str] = "1",
                platforms_ids: Optional[str] = None,
                payments_ids: Optional[str] = None,
                ecommerce_states_ids: Optional[str] = None,
                search: Optional[str] = None,
                is_payed: Optional[bool] = None,
                is_invoice_requested: Optional[bool] = None,
                date_from: Optional[str] = None,
                date_to: Optional[str] = None,
                show_details: bool = False,
                page: int = 1, 
                limit: int = 10
                ):
        """
        Recupera tutti gli ordini con filtri opzionali
        """
        # Usa joinedload per caricare carrier ed evitare N+1 queries
        query = self.session.query(Order).options(joinedload(Order.carrier))
        
        # LEFT JOINs per la ricerca rapida (solo se necessario)
        needs_search_joins = search is not None
        if needs_search_joins:
            query = query.outerjoin(Address, Order.id_address_delivery == Address.id_address)
            query = query.outerjoin(Customer, Order.id_customer == Customer.id_customer)
            query = query.outerjoin(Payment, Order.id_payment == Payment.id_payment)
            query = query.outerjoin(Shipping, Order.id_shipping == Shipping.id_shipping)
            query = query.outerjoin(OrderDetailModel, Order.id_order == OrderDetailModel.id_order)
            query = query.outerjoin(Product, OrderDetailModel.id_product == Product.id_product)
        
        try:
            # Filtri per ID
            if orders_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order', orders_ids)
            if customers_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_customer', customers_ids)
            if order_states_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order_state', order_states_ids)
            if ecommerce_states_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_ecommerce_state', ecommerce_states_ids)
            if store_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_store', store_ids)
            if platforms_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_platform', platforms_ids)
            if payments_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_payment', payments_ids)
            if shipping_states_ids:
                ids = QueryUtils.parse_int_list(shipping_states_ids)
                if not needs_search_joins:
                    query = query.join(Shipping, Order.id_shipping == Shipping.id_shipping)
                query = query.filter(Shipping.id_shipping_state.in_(ids))
            if delivery_countries_ids:
                ids = QueryUtils.parse_int_list(delivery_countries_ids)
                if not needs_search_joins:
                    query = query.join(Address, Order.id_address_delivery == Address.id_address)
                query = query.filter(Address.id_country.in_(ids))
            
            # Filtri booleani
            if is_payed is not None:
                query = query.filter(Order.is_payed == is_payed)
            if is_invoice_requested is not None:
                query = query.filter(Order.is_invoice_requested == is_invoice_requested)
            
            # Filtri per data (se implementati)
            if date_from:
                query = query.filter(Order.date_add >= date_from)
            if date_to:
                query = query.filter(Order.date_add <= date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        # Usa distinct per evitare duplicati quando ci sono JOINs multipli (es. OrderDetail)
        if needs_search_joins:
            query = query.distinct()
        
        orders_result = query.order_by(desc(Order.id_order)).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()
        
        return orders_result

    def get_count(self,
                  orders_ids: Optional[str] = None,
                  customers_ids: Optional[str] = None,
                  order_states_ids: Optional[str] = None,
                  shipping_states_ids: Optional[str] = None,
                  delivery_countries_ids: Optional[str] = None,
                  store_ids: Optional[str] = "1",
                  platforms_ids: Optional[str] = None,
                  payments_ids: Optional[str] = None,
                  ecommerce_states_ids: Optional[str] = None,
                  search: Optional[str] = None,
                  is_payed: Optional[bool] = None,
                  is_invoice_requested: Optional[bool] = None,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None
                  ) -> int:
        """
        Conta il numero totale di ordini con i filtri applicati
        """
        # Usa distinct count se ci sono JOINs che possono creare duplicati
        if search is not None:
            query = self.session.query(func.count(func.distinct(Order.id_order)))
        else:
            query = self.session.query(func.count(Order.id_order))
        
        # LEFT JOINs per la ricerca rapida (solo se necessario)
        needs_search_joins = search is not None
        if needs_search_joins:
            query = query.outerjoin(Address, Order.id_address_delivery == Address.id_address)
            query = query.outerjoin(Customer, Order.id_customer == Customer.id_customer)
            query = query.outerjoin(Payment, Order.id_payment == Payment.id_payment)
            query = query.outerjoin(Shipping, Order.id_shipping == Shipping.id_shipping)
            query = query.outerjoin(OrderDetailModel, Order.id_order == OrderDetailModel.id_order)
            query = query.outerjoin(Product, OrderDetailModel.id_product == Product.id_product)
        
        try:
            # Applica gli stessi filtri di get_all
            if orders_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order', orders_ids)
            if customers_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_customer', customers_ids)
            if order_states_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order_state', order_states_ids)
            if ecommerce_states_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_ecommerce_state', ecommerce_states_ids)
            if store_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_store', store_ids)
            if platforms_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_platform', platforms_ids)
            if payments_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_payment', payments_ids)
            if shipping_states_ids:
                ids = QueryUtils.parse_int_list(shipping_states_ids)
                if not needs_search_joins:
                    query = query.join(Shipping, Order.id_shipping == Shipping.id_shipping)
                query = query.filter(Shipping.id_shipping_state.in_(ids))
            if delivery_countries_ids:
                ids = QueryUtils.parse_int_list(delivery_countries_ids)
                if not needs_search_joins:
                    query = query.join(Address, Order.id_address_delivery == Address.id_address)
                query = query.filter(Address.id_country.in_(ids))
            
            # Ricerca rapida
            if search:
                search_conditions = []
                search_lower = f"%{search.lower()}%"
                
                # Address fields (gestisce NULL con coalesce)
                search_conditions.append(func.cast(func.coalesce(Address.id_address, 0), String).ilike(search_lower))
                search_conditions.append(func.coalesce(Address.firstname, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Address.lastname, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Address.address1, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Address.postcode, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Address.vat, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Address.pec, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Address.sdi, '').ilike(search_lower))
                
                # Customer fields
                search_conditions.append(func.coalesce(Customer.firstname, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Customer.lastname, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Customer.email, '').ilike(search_lower))
                
                # Order fields
                search_conditions.append(func.coalesce(Order.reference, '').ilike(search_lower))
                search_conditions.append(func.coalesce(Order.internal_reference, '').ilike(search_lower))
                
                # Payment fields
                search_conditions.append(func.coalesce(Payment.name, '').ilike(search_lower))
                
                # Product fields
                search_conditions.append(func.coalesce(Product.name, '').ilike(search_lower))
                
                # Shipping fields
                search_conditions.append(func.coalesce(Shipping.tracking, '').ilike(search_lower))
                
                query = query.filter(or_(*search_conditions))
            
            # Filtri booleani
            if is_payed is not None:
                query = query.filter(Order.is_payed == is_payed)
            if is_invoice_requested is not None:
                query = query.filter(Order.is_invoice_requested == is_invoice_requested)
            
            # Filtri per data
            if date_from:
                query = query.filter(Order.date_add >= date_from)
            if date_to:
                query = query.filter(Order.date_add <= date_to)
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        return query.scalar() or 0

    def get_by_id(self, _id: int) -> Order:
        """Recupera un ordine per ID con eager loading di ecommerce_order_state"""
        return self.session.query(Order).options(
            joinedload(Order.ecommerce_order_state)
        ).filter(Order.id_order == _id).first()

    def get_order_history_by_id_order(self, id_order: int) -> list[dict]:
        """Restituisce la cronologia dell'ordine in formato [{state, data}]."""
        try:
            from src.services.core.tool import format_datetime_ddmmyyyy_hhmm
            rows = (
                self.session
                .query(
                    orders_history.c.id_order,
                    orders_history.c.date_add,
                    OrderState.name.label('state_name')
                )
                .outerjoin(OrderState, OrderState.id_order_state == orders_history.c.id_order_state)
                .filter(orders_history.c.id_order == id_order)
                .order_by(orders_history.c.date_add)
                .all()
            )
            return [{"state": r.state_name, "data": format_datetime_ddmmyyyy_hhmm(r.date_add)} for r in rows]
        except Exception:
            return []
    
    def generate_shipping(self, data: OrderSchema) -> int:
        """
        Genera una spedizione di default basata sull'indirizzo di consegna.
        IMPORTANTE: Questo metodo viene chiamato solo UNA volta durante la creazione dell'ordine.
        """
        # Debug per capire se è un oggetto o un ID
        if hasattr(data.address_delivery, 'id_country'):
            country_id = data.address_delivery.id_country
        elif isinstance(data.address_delivery, int):
            # Se è un ID, dobbiamo recuperare l'address dal database per ottenere il country_id
            address_obj = self.address_repository.get_by_id(data.address_delivery)
            if address_obj:
                country_id = address_obj.id_country if hasattr(address_obj, 'id_country') else 1
            else:
                country_id = 1  # Default fallback
        else:
            country_id = 1  # Default fallback
        
        id_tax = self.tax_repository.define_tax(country_id)
        
        # Crea shipping con parametri di default
        return self.shipping_repository.create_and_get_id(ShippingSchema(
            id_carrier_api=1,
            id_shipping_state=1,
            id_tax=id_tax,
            tracking=None,
            weight=0.0,
            price_tax_incl=0.0,
            price_tax_excl=0.0
        ))

    def create(self, data: OrderSchema):
        order = Order(
            **data.model_dump(exclude=['address_delivery', 'address_invoice', 'customer', 'shipping', 'sectional', 'order_details']))

        if isinstance(data.customer, CustomerSchema):
            # Controlla se esiste già un customer con questa email (case-insensitive)
            existing_customer = self.customer_repository.get_by_email(data.customer.email)
            
            if existing_customer:
                # Usa il customer esistente invece di crearne uno nuovo
                order.id_customer = existing_customer.id_customer
            else:
                # Crea nuovo customer solo se l'email non esiste
                order.id_customer = QueryUtils.create_and_set_id(
                    repository=self.customer_repository, 
                    schema_datas=data,
                    field_name="customer"
                )
        else:
            # E' stato passato l'ID per intero, no oggetto
            # Converti 0 a None per foreign key
            order.id_customer = data.customer if data.customer and data.customer > 0 else 0

        if isinstance(data.address_delivery, AddressSchema):
            order.id_address_delivery = self.address_repository.get_or_create_address(
                address_data=data.address_delivery,
                customer_id=order.id_customer)
        # Altrimenti è ID
        else:
            # Converti 0 a None per foreign key
            order.id_address_delivery = data.address_delivery if data.address_delivery and data.address_delivery > 0 else 0

        # Setta l'ID dell'indirizzo, se non e' stato passato l'oggetto è stato passato l'ID
        if isinstance(data.address_invoice, AddressSchema):
            order.id_address_invoice = self.address_repository.get_or_create_address(address_data=data.address_invoice,
                                                                                     customer_id=order.id_customer)
        else:
            # Converti 0 a None per foreign key
            order.id_address_invoice = data.address_invoice if data.address_invoice and data.address_invoice > 0 else 0

        # Gestione shipping: distingue tra None/0, int (ID esistente), e ShippingSchema (nuovo)
        # IMPORTANTE: Verifica esplicita per evitare creazioni multiple
        logger.warning(f"[DEBUG] create order - data.shipping type: {type(data.shipping)}, value: {data.shipping}")
        
        if isinstance(data.shipping, ShippingSchema):
            # Se price_tax_excl non fornito ma price_tax_incl sì, calcolalo
            shipping_data = data.shipping.model_dump()
            if (shipping_data.get('price_tax_excl') is None or shipping_data.get('price_tax_excl') == 0) and shipping_data.get('price_tax_incl'):
                from src.services.core.tool import get_tax_percentage_by_address_delivery_id, calculate_price_without_tax
                if order.id_address_delivery:
                    tax_percentage = get_tax_percentage_by_address_delivery_id(self.session, order.id_address_delivery, default=22.0)
                    shipping_data['price_tax_excl'] = calculate_price_without_tax(shipping_data['price_tax_incl'], tax_percentage)
                else:
                    # Se non c'è address_delivery ancora, usa default
                    tax_percentage = self.tax_repository.get_default_tax_percentage_from_app_config(default=22.0)
                    shipping_data['price_tax_excl'] = calculate_price_without_tax(shipping_data['price_tax_incl'], tax_percentage)
            order.id_shipping = self.shipping_repository.create_and_get_id(data=shipping_data)
            logger.warning(f"[DEBUG] create order - shipping creato con ID: {order.id_shipping}")
        elif isinstance(data.shipping, int) and data.shipping > 0:
            logger.warning(f"[DEBUG] create order - usando shipping esistente con ID: {data.shipping}")
            # Se è un ID valido, usa la spedizione esistente
            order.id_shipping = data.shipping
        else:
            logger.warning(f"[DEBUG] create order - shipping None/0, chiamando generate_shipping")
            # Se shipping è None, 0, o altro valore non valido, genera una spedizione di default
            # (solo UNA volta)
            order.id_shipping = self.generate_shipping(data)
            logger.warning(f"[DEBUG] create order - shipping generato con ID: {order.id_shipping}")

        if isinstance(data.sectional, SectionalSchema):
            order.id_sectional = QueryUtils.create_and_set_id(repository=self.sectional_repository,
                                                              schema_datas=data,
                                                              field_name="sectional")
        elif isinstance(data.sectional, int):
            # Se è un ID, usa direttamente l'ID
            # Converti 0 a None per foreign key
            order.id_sectional = data.sectional if data.sectional and data.sectional > 0 else 0


        # Set stato di default per l'ordine
        order.order_states = [self.order_state_repository.get_by_id(1)]

        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        
        # Genera internal_reference se non esiste
        if not order.internal_reference and order.id_address_delivery:
            try:
                from src.services.core.tool import generate_internal_reference
                from src.repository.country_repository import CountryRepository
                
                # Recupera country ISO code dall'indirizzo di consegna
                address = self.address_repository.get_by_id(order.id_address_delivery)
                if address and address.id_country:
                    country_repo = CountryRepository(self.session)
                    country = country_repo.get_by_id(address.id_country)
                    if country and hasattr(country, 'iso_code'):
                        country_iso = country.iso_code
                    else:
                        country_iso = "IT"  # Default
                else:
                    country_iso = "IT"  # Default
                
                # Genera internal_reference
                internal_ref = generate_internal_reference(country_iso, self.app_configuration_repository)
                order.internal_reference = internal_ref
                
                # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
                
                order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())
                
                # Salva l'aggiornamento
                self.session.commit()
                
            except Exception as e:
                # Se fallisce, continua senza internal_reference
                print(f"Warning: Could not generate internal_reference for order {order.id_order}: {str(e)}")
        
        # Creazione di Order Details se presenti
        created_order_details = []
        if data.order_details:
            for detail in data.order_details:
                # Aggiungi l'id_order a ogni detail
                detail_data = detail.model_dump()
                detail_data['id_order'] = order.id_order
                created_detail = self.order_detail_repository.create(detail_data)
                created_order_details.append(created_detail)
        
        # Calcola i totali se non sono stati passati e ci sono order_details
        if created_order_details:
            from src.services.core.tool import calculate_order_totals
            from src.models.tax import Tax
            
            # Raccogli gli ID delle tasse dagli order details
            tax_ids = set()
            for detail in created_order_details:
                if hasattr(detail, 'id_tax') and detail.id_tax:
                    tax_ids.add(detail.id_tax)
            
            # Recupera le percentuali delle tasse
            tax_percentages = {}
            if tax_ids:
                taxes = self.session.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
                tax_percentages = {tax.id_tax: tax.percentage for tax in taxes}
            
            # Calcola i totali
            totals = calculate_order_totals(created_order_details, tax_percentages)
            
            # Se i valori non sono stati passati (sono None o 0), usa i valori calcolati
            if not order.total_weight or order.total_weight == 0:
                order.total_weight = totals['total_weight']
            
            if not order.total_price_with_tax or order.total_price_with_tax == 0:
                # Aggiungi il costo della spedizione con tasse
                shipping_cost_with_tax = 0.0
                if order.id_shipping:
                    shipping = self.shipping_repository.get_by_id(order.id_shipping)
                    if shipping and shipping.price_tax_incl:
                        shipping_cost_with_tax = float(shipping.price_tax_incl)
                
                total_with_shipping = totals['total_price_with_tax'] + shipping_cost_with_tax
                
                # Sottrai gli sconti se presenti
                discount = order.total_discounts if order.total_discounts else 0.0
                order.total_price_with_tax = total_with_shipping - discount
            
            # Calcola total_price_net se non fornito
            if order.total_price_net is None or order.total_price_net == 0:
                # Calcola total_price_net sommando i netti degli order_detail e aggiungendo shipping_cost_excl
                shipping_cost_excl = 0.0
                if order.id_shipping:
                    shipping = self.shipping_repository.get_by_id(order.id_shipping)
                    if shipping and shipping.price_tax_excl:
                        shipping_cost_excl = float(shipping.price_tax_excl)
                
                total_price_net_products = sum(
                    float(od.total_price_net) if hasattr(od, 'total_price_net') and od.total_price_net is not None else 0.0
                    for od in created_order_details
                )
                discount = order.total_discounts if order.total_discounts else 0.0
                order.total_price_net = total_price_net_products + shipping_cost_excl - discount
            
            # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
            order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())
            
            # Salva i totali calcolati
            self.session.add(order)
            self.session.commit()
            
            # Aggiorna customs_value della spedizione se None
            if order.id_shipping:
                self.shipping_repository.update_customs_value_from_order(order.id_shipping)
        
        # Creazione di Order Package
        order_package_data = OrderPackageSchema(
            id_order=order.id_order,
            height=10.0,
            width=10.0,
            depth=10.0,
            weight=10.0,
            length=10.0,
            value=10.0
        )
        self.order_package_repository.create(order_package_data.model_dump())
        
        # Aggiorna peso spedizione automaticamente (solo se ordine in stato 1)
        if created_order_details:
            logger.warning(f"[DEBUG] OrderRepository.create - aggiornando peso spedizione per order {order.id_order}")
            from src.services.routers.order_document_service import OrderDocumentService
            order_doc_service = OrderDocumentService(self.session)
            order_doc_service.update_shipping_weight_from_articles(
                id_order=order.id_order,
                check_order_state=True
            )
        
        logger.warning(f"[DEBUG] OrderRepository.create completato - order.id_order: {order.id_order}, order.id_shipping: {order.id_shipping}")
        
        return order.id_order

    def update(self, edited_order: Order, data: OrderSchema | OrderUpdateSchema):

        entity_updated = data.model_dump(exclude_unset=True)
        old_state_id = edited_order.id_order_state
        state_changed = False
        
        # Estrai order_packages se presente (non è un campo dell'Order, va gestito separatamente)
        order_packages = entity_updated.pop('order_packages', None)

        for key, value in entity_updated.items():
            if not hasattr(edited_order, key) or value is None:
                continue

            if key in ['id_customer', 'id_address_delivery', 'id_address_invoice',
                       'id_store', 'id_payment', 'id_shipping', 'id_sectional']:
                if value == 0:
                    setattr(edited_order, key, 0)
                else:
                    setattr(edited_order, key, value)
            else:
                setattr(edited_order, key, value)

            if key == 'id_order_state' and value != old_state_id:
                state_changed = True

        # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
        edited_order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())

        self.session.add(edited_order)
        self.session.commit()
        
        # Gestisci order_packages (smart merge) - DOPO commit ordine
        if order_packages is not None:
            self._handle_order_packages_smart_merge(edited_order.id_order, order_packages)

        # Event emission is now handled by the @emit_event_on_success decorator
        # in the router layer to avoid duplication and centralize event handling

        return edited_order

    def set_price(self, id_order: int, order_details: list[OrderDetail]):
        from src.services.core.tool import calculate_order_totals
        from src.models.tax import Tax
        
        order = self.get_by_id(_id=id_order)

        if order is None:
            raise HTTPException(status_code=404, detail="Ordine non trovato")

        # Recupera le percentuali delle tasse
        tax_ids = set()
        for order_detail in order_details:
            if hasattr(order_detail, 'id_tax') and order_detail.id_tax:
                tax_ids.add(order_detail.id_tax)
        
        tax_percentages = {}
        if tax_ids:
            taxes = self.session.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
            tax_percentages = {tax.id_tax: tax.percentage for tax in taxes}

        # Calcola i totali usando le funzioni pure
        totals = calculate_order_totals(order_details, tax_percentages)
        order.total_price_with_tax = totals['total_price_with_tax']
        # Calcola total_price_net se necessario
        if order.total_price_net is None or order.total_price_net == 0:
            from src.services.core.tool import get_tax_percentage_by_address_delivery_id, calculate_price_without_tax
            if order.id_address_delivery:
                tax_percentage = get_tax_percentage_by_address_delivery_id(self.session, order.id_address_delivery, default=22.0)
                order.total_price_net = calculate_price_without_tax(order.total_price_with_tax, tax_percentage) if order.total_price_with_tax > 0 else 0.0

        # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
        order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())

        self.session.add(order)
        self.session.commit()

    def set_weight(self, id_order: int, order_details: list[OrderDetail]):
        order = self.get_by_id(_id=id_order)
        order.total_weight = sum(order_detail.product_weight * order_detail.product_qty for order_detail in order_details)

        # Aggiorna updated_at con formato DD-MM-YYYY hh:mm:ss
        order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())

        self.session.add(order)
        self.session.commit()

        # Allinea il peso della spedizione se presente
        try:
            if getattr(order, 'id_shipping', None):
                from src.repository.shipping_repository import ShippingRepository
                shipping_repo = ShippingRepository(self.session)
                shipping_repo.update_weight(order.id_shipping, order.total_weight)

        except Exception:
            # Non bloccare il flusso per errori non critici di sync peso
            pass


    def update_order_status(self, id_order: int, id_order_state: int) -> bool:
        """
        Aggiorna lo stato di un ordine e aggiunge alla cronologia.
        
        Args:
            id_order: ID dell'ordine
            id_order_state: Nuovo ID stato ordine
            
        Returns:
            bool: True se aggiornato con successo
            
        Raises:
            ValueError: Se l'id_order_state non esiste nella tabella order_states
        """
        order = self.get_by_id(id_order)
        if not order:
            return False
        
        # Valida che l'id_order_state esista
        order_state = self.session.query(OrderState).filter(
            OrderState.id_order_state == id_order_state
        ).first()
        if not order_state:
            raise ValueError(f"Stato ordine {id_order_state} non esiste nella tabella order_states")
        
        order.id_order_state = id_order_state
        
        # Aggiorna updated_at
        order.updated_at = format_datetime_ddmmyyyy_hhmmss(datetime.now())
        
        # Aggiungi nuovo stato alla cronologia
        order_history_insert = orders_history.insert().values(
            id_order=id_order,
            id_order_state=id_order_state,
            date_add=datetime.now()
        )
        self.session.execute(order_history_insert)
        
        self.session.add(order)
        self.session.commit()
        
        return True

    def delete(self, order: Order) -> bool:
        """
        Elimina un ordine dal database
        """
        self.session.delete(order)
        self.session.commit()
        return True
    
    def bulk_create_csv_import(self, data_list: List, id_store: int = None, batch_size: int = 1000) -> int:
        """
        Bulk insert orders da CSV import con gestione id_store.
        
        Args:
            data_list: Lista OrderSchema da inserire
            id_store: ID store per uniqueness check
            batch_size: Dimensione batch (default: 1000)
            
        Returns:
            Numero orders inseriti
        """
        if not data_list:
            return 0
        
        try:
            from sqlalchemy import and_, text
            from src.models.order import Order
            
            # Get existing (id_origin, id_store) pairs
            origin_ids = [data.id_origin for data in data_list if hasattr(data, 'id_origin') and data.id_origin]
            
            if origin_ids:
                placeholders = ','.join([f':id_{i}' for i in range(len(origin_ids))])
                params = {f'id_{i}': origin for i, origin in enumerate(origin_ids)}
                if id_store:
                    params['id_store'] = id_store
                    query = text(f"SELECT id_origin FROM orders WHERE id_origin IN ({placeholders}) AND id_store = :id_store")
                else:
                    query = text(f"SELECT id_origin FROM orders WHERE id_origin IN ({placeholders})")
                result = self.session.execute(query, params)
                existing_origins = {row[0] for row in result}
            else:
                existing_origins = set()
            
            # Filter new orders
            new_orders_data = [data for data in data_list if hasattr(data, 'id_origin') and data.id_origin not in existing_origins]
            
            if not new_orders_data:
                return 0
            
            # Batch insert
            total_inserted = 0
            for i in range(0, len(new_orders_data), batch_size):
                batch = new_orders_data[i:i + batch_size]
                orders = [Order(**o.model_dump() if hasattr(o, 'model_dump') else o) for o in batch]
                self.session.bulk_save_objects(orders)
                total_inserted += len(orders)
            
            self.session.commit()
            return total_inserted
            
        except Exception as e:
            self.session.rollback()
            from src.core.exceptions import InfrastructureException
            raise InfrastructureException(f"Database error bulk creating orders: {str(e)}")

    def formatted_output(self, order: Order, show_details: bool = False, include_order_history: bool = True):
        """
        Formatta l'output di un ordine con le relazioni popolate tramite query separate
        
        Args:
            order: Oggetto Order da formattare
            show_details: Se True, include dettagli completi delle relazioni
            include_order_history: Se True, include order_history nella risposta (default: True)
        """
        # Helper per formattare gli indirizzi
        def format_address(address_id):
            if not address_id:
                return None
            address = self.address_repository.get_by_id(address_id)
            if not address:
                return None
            return {
                "id_address": address.id_address,
                "id_origin": address.id_origin,
                "country": {
                    "id_country": address.country.id_country,
                    "name": address.country.name,
                    "iso_code": address.country.iso_code
                } if address.country else None,
                "company": address.company,
                "firstname": address.firstname,
                "lastname": address.lastname,
                "address1": address.address1,
                "address2": address.address2,
                "state": address.state,
                "postcode": address.postcode,
                "city": address.city,
                "phone": address.phone,
                "mobile_phone": address.mobile_phone,
                "vat": address.vat,
                "dni": address.dni,
                "pec": address.pec,
                "sdi": address.sdi,
                "date_add": address.date_add.strftime('%d-%m-%Y') if address.date_add else None
            }
        
        # Helper per formattare il customer
        def format_customer(customer_id):
            if not customer_id:
                return None
            customer = self.customer_repository.get_by_id(customer_id)
            if not customer:
                return None
            
            # Recupera i dati della lingua
            lang = None
            if customer.id_lang:
                lang_obj = self.lang_repository.get_by_id(customer.id_lang)
                if lang_obj:
                    lang = {
                        "id_lang": lang_obj.id_lang,
                        "name": lang_obj.name,
                        "iso_code": lang_obj.iso_code
                    }
            
            return {
                "id_customer": customer.id_customer,
                "id_origin": customer.id_origin,
                "lang": lang,
                "firstname": customer.firstname,
                "lastname": customer.lastname,
                "email": customer.email,
                "date_add": customer.date_add
            }
        
        # Helper per formattare lo shipping
        def format_shipping(shipping_id):
            if not shipping_id:
                return None
            shipping = self.shipping_repository.get_by_id(shipping_id)
            if not shipping:
                return None
            
            # Recupera i dati del carrier_api
            carrier_api = None
            if shipping.id_carrier_api:
                carrier_api_obj = self.api_carrier_repository.get_by_id(shipping.id_carrier_api)
                if carrier_api_obj:
                    carrier_api = {
                        "id_carrier_api": carrier_api_obj.id_carrier_api,
                        "name": carrier_api_obj.name
                    }
            
            # Recupera i dati dello shipping_state
            shipping_state = None
            if shipping.id_shipping_state:
                shipping_state_obj = self.shipping_state_repository.get_by_id(shipping.id_shipping_state)
                if shipping_state_obj:
                    shipping_state = {
                        "id_shipping_state": shipping_state_obj.id_shipping_state,
                        "name": shipping_state_obj.name
                    }
            
            # Recupera i dati della tax
            tax = None
            if shipping.id_tax:
                tax_obj = self.tax_repository.get_by_id(shipping.id_tax)
                if tax_obj:
                    tax = {
                        "id_tax": tax_obj.id_tax,
                        "code": tax_obj.code,
                        "percentage": tax_obj.percentage,
                        "name": tax_obj.name
                    }
            
            return {
                "id_shipping": shipping.id_shipping,
                "carrier_api": carrier_api,
                "shipping_state": shipping_state,
                "tax": tax,
                "tracking": shipping.tracking,
                "weight": shipping.weight,
                "price_tax_incl": shipping.price_tax_incl,
                "price_tax_excl": shipping.price_tax_excl
            }
        
        # Helper per formattare il sectional
        def format_sectional(sectional_id):
            if not sectional_id:
                return None
            sectional = self.sectional_repository.get_by_id(sectional_id)
            if not sectional:
                return None
            return {
                "id_sectional": sectional.id_sectional,
                "name": sectional.name
            }
        
        # Helper per formattare l'order state corrente
        def format_order_state(order_state_id):
            if not order_state_id:
                return None
            order_state = self.order_state_repository.get_by_id(order_state_id)
            if not order_state:
                return None
            return {
                "id_order_state": order_state.id_order_state,
                "name": order_state.name
            }
        
        # Helper per formattare gli order states
        def format_order_states(order_id):
            if not order_id:
                return None
            # Recupera gli order states per questo ordine con date_add
            order_states = self.session.query(OrderState, orders_history.c.date_add).join(
                orders_history, OrderState.id_order_state == orders_history.c.id_order_state
            ).filter(orders_history.c.id_order == order_id).all()
            
            if not order_states:
                return None
            return [{
                "id_order_state": state.id_order_state,
                "name": state.name,
                "date": date_add
            } for state, date_add in order_states]
        
        # Helper per formattare l'order history
        def format_order_history(order_id):
            """Formatta la cronologia ordine con order_state.name e order_history.date_add"""
            if not order_id:
                return []
            # Recupera gli order states per questo ordine con date_add
            history_records = self.session.query(
                OrderState.name,
                orders_history.c.date_add
            ).join(
                orders_history, OrderState.id_order_state == orders_history.c.id_order_state
            ).filter(
                orders_history.c.id_order == order_id
            ).order_by(
                orders_history.c.date_add
            ).all()
            
            if not history_records:
                return []
            
            return [{
                "name": name,
                "date_add": format_datetime_ddmmyyyy_hhmmss(date_add) if date_add else None
            } for name, date_add in history_records]
        
        # Helper per formattare i dettagli dell'ordine
        def format_order_details(order_id):
            if not order_id:
                return []
            order_details = self.order_detail_repository.get_by_order_id(order_id)
            if not order_details:
                return []
            
            # Recupera immagini prodotti in batch (performance optimization)
            product_ids = [detail.id_product for detail in order_details if detail.id_product]
            images_map = {}
            if product_ids:
                from src.models.product import Product
                products = self.session.query(Product.id_product, Product.img_url).filter(
                    Product.id_product.in_(product_ids)
                ).all()
                fallback_img_url = "media/product_images/fallback/product_not_found.jpg"
                images_map = {
                    product.id_product: product.img_url if product.img_url else fallback_img_url
                    for product in products
                }
            
            # Formatta output con img_url
            return [
                self.order_detail_repository.formatted_output(
                    detail, 
                    img_url=images_map.get(detail.id_product) if detail.id_product else None
                ) 
                for detail in order_details
            ]
        
        # Helper per formattare la piattaforma
        def format_platform(platform_id):
            if not platform_id:
                return None
            platform = self.platform_repository.get_by_id(platform_id)
            if not platform:
                return None
            return {
                "name": platform.name
            }
        
        # Helper per formattare il pagamento
        def format_payment(payment_id):
            if not payment_id:
                return None
            payment = self.payment_repository.get_by_id(payment_id)
            if not payment:
                return None
            return {
                "id_payment": payment.id_payment,
                "name": payment.name
            }
        
        # Helper per formattare i packages dell'ordine
        def format_order_packages(order_id):
            if not order_id:
                return []
            from src.models.order_package import OrderPackage
            packages = self.session.query(
                OrderPackage.id_order_package,
                OrderPackage.height,
                OrderPackage.width,
                OrderPackage.depth,
                OrderPackage.weight,
                OrderPackage.value
            ).filter(
                OrderPackage.id_order == order_id
            ).all()
            if not packages:
                return []
            return [{
                "id_order_package": pkg.id_order_package,
                "height": pkg.height,
                "width": pkg.width,
                "depth": pkg.depth,
                "weight": pkg.weight,
                "value": pkg.value
            } for pkg in packages]
        
        # Helper per formattare lo stato e-commerce
        def format_ecommerce_order_state(order):
            """Formatta lo stato e-commerce usando la relationship già caricata"""
            if not order.id_ecommerce_state:
                return None
            # Usa la relationship per evitare query N+1 (già caricata con joinedload)
            if hasattr(order, 'ecommerce_order_state') and order.ecommerce_order_state:
                return {
                    "id": order.id_ecommerce_state,
                    "name": order.ecommerce_order_state.name
                }
            return None
        
        # Helper per formattare il carrier e-commerce
        def format_ecommerce_carrier(order):
            """Formatta il carrier e-commerce usando la relationship già caricata"""
            if not order.id_carrier:
                return None
            # Usa la relationship per evitare query N+1 (già caricata con joinedload)
            if hasattr(order, 'carrier') and order.carrier:
                return {
                    "name": order.carrier.name
                }
            return None
        
        # Base response con campi essenziali
        response = {
            "id_order": order.id_order,
            "id_origin": order.id_origin,
            "reference": order.reference,
            "id_address_delivery": order.id_address_delivery,
            "id_address_invoice": order.id_address_invoice,
            "id_customer": order.id_customer,
            "id_store": order.id_store,
            "id_payment": order.id_payment,
            "id_shipping": order.id_shipping,
            "id_sectional": order.id_sectional,
            "id_order_state": order.id_order_state,
            "order_state": format_order_state(order.id_order_state),
            "is_invoice_requested": order.is_invoice_requested,
            "is_payed": order.is_payed,
            "payment_date": order.payment_date,
            "total_weight": order.total_weight,
            "total_price_with_tax": order.total_price_with_tax,
            "total_price_net": order.total_price_net,
            "total_discounts": order.total_discounts,
            "cash_on_delivery": order.cash_on_delivery,
            "insured_value": order.insured_value,
            "privacy_note": order.privacy_note,
            "general_note": order.general_note,
            "delivery_date": order.delivery_date,
            "date_add": order.date_add,
            "ecommerce_order_state": format_ecommerce_order_state(order),
            "ecommerce_carrier": format_ecommerce_carrier(order)
        }
        
        # Aggiungi order_history solo se richiesto
        if include_order_history:
            response["order_history"] = format_order_history(order.id_order)
        
        # Se show_details è True, aggiungi le relazioni popolate
        if show_details:
            # Rimuovi i campi ID duplicati (usa pop con default per evitare errori)
            response.pop("id_address_delivery", None)
            response.pop("id_address_invoice", None)
            response.pop("id_customer", None)
            response.pop("id_store", None)
            response.pop("id_payment", None)
            response.pop("id_shipping", None)
            response.pop("id_sectional", None)
            response.pop("id_order_state", None)
            response.update({
                "address_delivery": format_address(order.id_address_delivery),
                "address_invoice": format_address(order.id_address_invoice),
                "customer": format_customer(order.id_customer),
                # store non incluso nella risposta - è solo un dato DB
                "payment": format_payment(order.id_payment),
                "shipping": format_shipping(order.id_shipping),
                "sectional": format_sectional(order.id_sectional),
                "order_state": format_order_state(order.id_order_state),
                "order_details": format_order_details(order.id_order),
                "order_packages": format_order_packages(order.id_order),
                "ecommerce_order_state": format_ecommerce_order_state(order)
            })

        
        return response
    
    def get_by_origin_id(self, id_origin: int) -> Optional[Order]:
        """Get order by origin ID (PrestaShop ID)"""
        try:
            return self.session.query(Order).filter(Order.id_origin == id_origin).first()
        except Exception as e:
            return None
    
    def get_id_by_origin_id(self, id_origin: int) -> Optional[int]:
        """Get order ID by origin ID (PrestaShop ID)"""
        try:
            return self.session.query(Order.id_order).filter(Order.id_origin == id_origin).scalar()
        except Exception as e:
            return None
    
    def get_shipment_data(self, order_id: int) -> Row:
        """Retrieve only fields needed for shipment creation"""
        stmt = select(
            Order.id_order,
            Order.internal_reference,
            Order.id_address_delivery,
            Order.id_shipping,
            Order.total_weight,
            Order.total_price_with_tax,
            Order.total_price_net,
            Order.cash_on_delivery,
            Order.insured_value
        ).where(Order.id_order == order_id)
        
        result = self.session.execute(stmt).first()
        if not result:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        
        return result
    
    def _handle_order_packages_smart_merge(self, id_order: int, packages: List) -> None:
        """
        Smart merge per order_packages:
        1. Identifica packages da UPDATE (id_order_package presente nella lista)
        2. Identifica packages da CREATE (id_order_package null nella lista)
        3. Identifica packages da DELETE (esistenti nel DB ma non nella lista)
        """
        from src.models.order_package import OrderPackage
        
        # Recupera packages esistenti per questo ordine
        existing_packages = self.session.query(OrderPackage).filter(
            OrderPackage.id_order == id_order,
            OrderPackage.id_order_document.is_(None)
        ).all()
        existing_ids = {p.id_order_package for p in existing_packages}
        
        # IDs nella lista fornita (packages è una lista di dict)
        provided_ids = {
            p.get('id_order_package') 
            for p in packages 
            if isinstance(p, dict) and p.get('id_order_package') is not None
        }
        
        # 1. UPDATE + CREATE
        for package_data in packages:
            if not isinstance(package_data, dict):
                continue
                
            id_order_package = package_data.get('id_order_package')
            if id_order_package is not None:
                # UPDATE esistente
                package = self.session.query(OrderPackage).filter(
                    OrderPackage.id_order_package == id_order_package
                ).first()
                if package:
                    if 'height' in package_data and package_data['height'] is not None:
                        package.height = package_data['height']
                    if 'width' in package_data and package_data['width'] is not None:
                        package.width = package_data['width']
                    if 'depth' in package_data and package_data['depth'] is not None:
                        package.depth = package_data['depth']
                    if 'length' in package_data and package_data['length'] is not None:
                        package.length = package_data['length']
                    if 'weight' in package_data and package_data['weight'] is not None:
                        package.weight = package_data['weight']
                    if 'value' in package_data and package_data['value'] is not None:
                        package.value = package_data['value']
            else:
                # CREATE nuovo
                new_package = OrderPackage(
                    id_order=id_order,
                    id_order_document=None,
                    height=package_data.get('height') or 10.0,
                    width=package_data.get('width') or 10.0,
                    depth=package_data.get('depth') or 10.0,
                    length=package_data.get('length') or 10.0,
                    weight=package_data.get('weight') or 0.0,
                    value=package_data.get('value') or 0.0
                )
                self.session.add(new_package)
        
        # 2. DELETE packages non presenti nella lista
        ids_to_delete = existing_ids - provided_ids
        for id_to_delete in ids_to_delete:
            package = self.session.query(OrderPackage).filter(
                OrderPackage.id_order_package == id_to_delete
            ).first()
            if package:
                self.session.delete(package)
        
        self.session.commit()