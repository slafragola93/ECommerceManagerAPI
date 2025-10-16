from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
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
from .. import AddressSchema, SectionalSchema, ShippingSchema, OrderPackageSchema, OrderDetail
from ..models import Order, OrderState
from ..models.relations.relations import orders_history
from src.schemas.customer_schema import *
from ..schemas.order_schema import OrderSchema, OrderResponseSchema, AllOrderResponseSchema, OrderIdSchema, OrderUpdateSchema
from ..services import QueryUtils


class OrderRepository:
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

    def get_all(self,
                orders_ids: Optional[str] = None,
                customers_ids: Optional[str] = None,
                order_states_ids: Optional[str] = None,
                platforms_ids: Optional[str] = None,
                payments_ids: Optional[str] = None,
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
        query = self.session.query(Order)
        
        try:
            # Filtri per ID
            if orders_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order', orders_ids)
            if customers_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_customer', customers_ids)
            if order_states_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order_state', order_states_ids)
            if platforms_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_platform', platforms_ids)
            if payments_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_payment', payments_ids)
            
            # Filtri booleani
            if is_payed is not None:
                query = query.filter(Order.is_payed == is_payed)
            if is_invoice_requested is not None:
                query = query.filter(Order.is_invoice_requested == is_invoice_requested)
            
            # Filtri per data (se implementati)
            # if date_from:
            #     query = query.filter(Order.date_add >= date_from)
            # if date_to:
            #     query = query.filter(Order.date_add <= date_to)
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        orders_result = query.order_by(desc(Order.id_order)).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()
        
        return orders_result

    def get_count(self,
                  orders_ids: Optional[str] = None,
                  customers_ids: Optional[str] = None,
                  order_states_ids: Optional[str] = None,
                  platforms_ids: Optional[str] = None,
                  payments_ids: Optional[str] = None,
                  is_payed: Optional[bool] = None,
                  is_invoice_requested: Optional[bool] = None,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None
                  ) -> int:
        """
        Conta il numero totale di ordini con i filtri applicati
        """
        query = self.session.query(func.count(Order.id_order))
        
        try:
            # Applica gli stessi filtri di get_all
            if orders_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order', orders_ids)
            if customers_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_customer', customers_ids)
            if order_states_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_order_state', order_states_ids)
            if platforms_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_platform', platforms_ids)
            if payments_ids:
                query = QueryUtils.filter_by_id(query, Order, 'id_payment', payments_ids)
            
            if is_payed is not None:
                query = query.filter(Order.is_payed == is_payed)
            if is_invoice_requested is not None:
                query = query.filter(Order.is_invoice_requested == is_invoice_requested)
                
        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
        
        return query.scalar()

    def get_by_id(self, _id: int) -> Order:
        """Recupera un ordine per ID"""
        return self.session.query(Order).filter(Order.id_order == _id).first()
    
    def generate_shipping(self, data: OrderSchema) -> int:
        """Genera una spedizione di default basata sull'indirizzo di consegna"""
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
        
        return self.shipping_repository.create_and_get_id(ShippingSchema(
            id_carrier_api=1,
            id_shipping_state=1,
            id_tax=self.tax_repository.define_tax(country_id),
            tracking=None,
            weight=0.0,
            price_tax_incl=0.0,
            price_tax_excl=0.0
        ))

    def create(self, data: OrderSchema):
        
        order = Order(
            **data.model_dump(exclude=['address_delivery', 'address_invoice', 'customer', 'shipping', 'sectional']))

        if isinstance(data.customer, CustomerSchema):
            # Se cliente non esiste in DB viene creato altrimenti se esiste si setta l'ID
            customer = self.customer_repository.get_by_email(data.customer.email)

            order.id_customer = QueryUtils.create_and_set_id(repository=self.customer_repository, schema_datas=data,
                                                             field_name="customer") if customer is None else customer.id_customer
        else:
            # E' stato passato l'ID per intero, no oggetto
            order.id_customer = data.customer

        if isinstance(data.address_delivery, AddressSchema):
            order.id_address_delivery = self.address_repository.get_or_create_address(
                address_data=data.address_delivery,
                customer_id=order.id_customer)
        # Altrimenti è ID
        else:
            order.id_address_delivery = data.address_delivery

        # Setta l'ID dell'indirizzo, se non e' stato passato l'oggetto è stato passato l'ID
        if isinstance(data.address_invoice, AddressSchema):
            order.id_address_invoice = self.address_repository.get_or_create_address(address_data=data.address_invoice,
                                                                                     customer_id=order.id_customer)
        else:
            order.id_address_invoice = data.address_invoice

        if data.shipping:
            if isinstance(data.shipping, ShippingSchema):
                order.id_shipping = self.shipping_repository.create_and_get_id(data=data.shipping)
            elif isinstance(data.shipping, int):
                # Se è un ID, usa la spedizione esistente
                order.id_shipping = data.shipping
        else:
            # Genera una spedizione di default
            order.id_shipping = self.generate_shipping(data)

        if isinstance(data.sectional, SectionalSchema):
            order.id_sectional = QueryUtils.create_and_set_id(repository=self.sectional_repository,
                                                              schema_datas=data,
                                                              field_name="sectional")
        elif isinstance(data.sectional, int):
            # Se è un ID, usa direttamente l'ID
            order.id_sectional = data.sectional

        # Set stato di default per l'ordine
        order.order_states = [self.order_state_repository.get_by_id(1)]

        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        
        # Creazione di Order Package
        order_package_data = OrderPackageSchema(id_order=order.id_order,
                                               height=0.0,
                                               width=0.0,
                                               depth=0.0,
                                               weight=0.0,
                                               value=0.0)
        self.order_package_repository.create(order_package_data.model_dump())
        
        return order.id_order

    # def update_order_status(self, id_order: int, id_order_state: int):
    #     order_history = OrderHistory(id_order=id_order, id_order_state=id_order_state)
    #
    #     self.session.add(order_history)
    #     self.session.commit()
    #     self.session.refresh(order_history)

    def update(self, edited_order: Order, data: OrderSchema | OrderUpdateSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_order, key) and value is not None:
                setattr(edited_order, key, value)

        self.session.add(edited_order)
        self.session.commit()

    def set_price(self, id_order: int, order_details: list[OrderDetail]):
        from src.services.tool import calculate_order_totals
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
        order.total_price_tax_excl = totals['total_price']
        order.total_paid = totals['total_price_with_tax']

        self.session.add(order)
        self.session.commit()

    def set_weight(self, id_order: int, order_details: list[OrderDetail]):
        order = self.get_by_id(_id=id_order)

        if order_details is None:
            raise HTTPException(status_code=404, detail="Ordine non trovato")
        order.total_weight = sum(order_detail.product_weight * order_detail.product_qty for order_detail in order_details)

        self.session.add(order)
        self.session.commit()

    def delete(self, order: Order) -> bool:
        """
        Elimina un ordine dal database
        """
        self.session.delete(order)
        self.session.commit()
        return True

    def formatted_output(self, order: Order, show_details: bool = False):
        """
        Formatta l'output di un ordine con le relazioni popolate tramite query separate
        
        Args:
            order: Oggetto Order da formattare
            show_details: Se True, include dettagli completi delle relazioni
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
        
        # Helper per formattare i dettagli dell'ordine
        def format_order_details(order_id):
            if not order_id:
                return []
            order_details = self.order_detail_repository.get_by_order_id(order_id)
            if not order_details:
                return []
            return [self.order_detail_repository.formatted_output(detail) for detail in order_details]
        
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
        
        # Base response con campi essenziali
        response = {
            "id_order": order.id_order,
            "id_origin": order.id_origin,
            "reference": order.reference,
            "id_address_delivery": order.id_address_delivery,
            "id_address_invoice": order.id_address_invoice,
            "id_customer": order.id_customer,
            "id_platform": order.id_platform,
            "id_payment": order.id_payment,
            "id_shipping": order.id_shipping,
            "id_sectional": order.id_sectional,
            "id_order_state": order.id_order_state,
            "is_invoice_requested": order.is_invoice_requested,
            "is_payed": order.is_payed,
            "payment_date": order.payment_date,
            "total_weight": order.total_weight,
            "total_price_tax_excl": order.total_price_tax_excl,
            "total_paid": order.total_paid,
            "total_discounts": order.total_discounts,
            "cash_on_delivery": order.cash_on_delivery,
            "insured_value": order.insured_value,
            "privacy_note": order.privacy_note,
            "general_note": order.general_note,
            "delivery_date": order.delivery_date,
            "date_add": order.date_add
        }
        
        # Se show_details è True, aggiungi le relazioni popolate
        if show_details:
            # Rimuovi i campi ID duplicati (usa pop con default per evitare errori)
            response.pop("id_address_delivery", None)
            response.pop("id_address_invoice", None)
            response.pop("id_customer", None)
            response.pop("id_platform", None)
            response.pop("id_payment", None)
            response.pop("id_shipping", None)
            response.pop("id_sectional", None)
            response.pop("id_order_state", None)
            response.update({
                "address_delivery": format_address(order.id_address_delivery),
                "address_invoice": format_address(order.id_address_invoice),
                "customer": format_customer(order.id_customer),
                "platform": format_platform(order.id_platform),
                "payment": format_payment(order.id_payment),
                "shipping": format_shipping(order.id_shipping),
                "sectional": format_sectional(order.id_sectional),
                "order_states": format_order_states(order.id_order),
                "order_details": format_order_details(order.id_order),
                "order_packages": format_order_packages(order.id_order)
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
            return self.session.query(Order.id_order).filter(Order.id_origin == id_origin).first()
        except Exception as e:
            return None