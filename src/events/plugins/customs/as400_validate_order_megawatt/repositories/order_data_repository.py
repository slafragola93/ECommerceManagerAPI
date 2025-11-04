"""Repository per caricamento ottimizzato dati ordine con selezione campi."""

from typing import Optional
from sqlalchemy.orm import Session, joinedload, load_only
from src.models.order import Order
from src.models.address import Address
from src.models.customer import Customer
from src.models.order_detail import OrderDetail
from src.models.product import Product
from src.models.tax import Tax
from src.models.payment import Payment
from src.models.country import Country
from src.models.shipping import Shipping
from src.models.carrier_api import CarrierApi


class OrderDataRepository:
    """Repository per caricare dati ordine con solo i campi necessari."""

    def __init__(self, session: Session):
        """Inizializza repository con sessione database."""
        self.session = session

    def get_order_with_relations(self, order_id: int) -> Optional[Order]:
        """
        Carica ordine con tutte le relazioni necessarie, selezionando solo i campi necessari.
        
        Usa query ottimizzate con load_only per selezionare solo le colonne richieste:
        - order: reference, internal_reference, date_add, id_address_delivery, id_customer, 
                 id_payment, total_price_tax_excl, total_paid, id_order_state
        - address_delivery: company, address1, address2, postcode, city, state, 
                           firstname, lastname, phone, id_country
        - country: iso_code
        - customer: email
        - order_details: id_product, id_tax, product_price, product_qty
        - product: id_origin
        - tax: percentage
        - payment: is_complete_payment
        
        Args:
            order_id: ID dell'ordine da caricare
            
        Returns:
            Oggetto Order con relazioni allegate, o None se non trovato
        """
        # Carica ordine con solo i campi necessari
        order = (
            self.session.query(Order)
            .options(
                load_only(
                    Order.id_order,
                    Order.reference,
                    Order.internal_reference,
                    Order.date_add,
                    Order.id_address_delivery,
                    Order.id_customer,
                    Order.id_payment,
                    Order.id_shipping,
                    Order.total_price_tax_excl,
                    Order.total_paid,
                    Order.id_order_state
                )
            )
            .filter(Order.id_order == order_id)
            .first()
        )
        
        if not order:
            return None
        
        # Carica address_delivery con country, selezionando solo i campi necessari
        if order.id_address_delivery:
            address = (
                self.session.query(Address)
                .options(
                    load_only(
                        Address.id_address,
                        Address.company,
                        Address.address1,
                        Address.address2,
                        Address.postcode,
                        Address.city,
                        Address.state,
                        Address.firstname,
                        Address.lastname,
                        Address.phone,
                        Address.id_country
                    ),
                    joinedload(Address.country).options(
                        load_only(Country.id_country, Country.iso_code)
                    )
                )
                .filter(Address.id_address == order.id_address_delivery)
                .first()
            )
            if address:
                order.address_delivery = address
        
        # Carica customer con solo campo email
        if order.id_customer:
            customer = (
                self.session.query(Customer)
                .options(load_only(Customer.id_customer, Customer.email))
                .filter(Customer.id_customer == order.id_customer)
                .first()
            )
            if customer:
                order.customer = customer
        
        # Carica order_details con join a Tax per recuperare percentage direttamente
        order_details_result = (
            self.session.query(
                OrderDetail,
                Tax.percentage.label('tax_percentage')
            )
            .outerjoin(Tax, OrderDetail.id_tax == Tax.id_tax)
            .options(
                load_only(
                    OrderDetail.id_order_detail,
                    OrderDetail.id_order,
                    OrderDetail.id_product,
                    OrderDetail.id_tax,
                    OrderDetail.product_price,
                    OrderDetail.product_qty
                )
            )
            .filter(OrderDetail.id_order == order_id)
            .all()
        )
        
        # Estrai OrderDetail e percentage dai risultati
        order_details = []
        if order_details_result:
            # Carica products in batch
            product_ids = [od.id_product for od, _ in order_details_result if od.id_product]
            products = {}
            if product_ids:
                products_query = (
                    self.session.query(Product)
                    .options(load_only(Product.id_product, Product.id_origin))
                    .filter(Product.id_product.in_(product_ids))
                    .all()
                )
                products = {p.id_product: p for p in products_query}
            
            # Associa percentage e products agli order details
            for detail, tax_percentage in order_details_result:
                # Assegna percentage come attributo
                detail.tax_percentage = tax_percentage if tax_percentage is not None else 0.0
                
                # Associa product sempre (anche se None) per evitare AttributeError
                if detail.id_product and detail.id_product in products:
                    detail.product = products[detail.id_product]
                else:
                    detail.product = None
                
                order_details.append(detail)
        
        # Assicura che order_details sia sempre una lista (anche se vuota)
        order.order_details = order_details
        
        # Carica payment con solo is_complete_payment
        # Assicurati che payment sia sempre assegnato (anche None) per accesso diretto
        if order.id_payment:
            payment = (
                self.session.query(Payment)
                .options(load_only(Payment.id_payment, Payment.is_complete_payment))
                .filter(Payment.id_payment == order.id_payment)
                .first()
            )
            order.payment = payment if payment else None
        else:
            order.payment = None
        
        # Carica shipping con carrier_api per recuperare il nome del carrier
        # Assicurati che shipments sia sempre assegnato (anche None) per accesso diretto
        if order.id_shipping:
            shipping = (
                self.session.query(Shipping)
                .options(load_only(Shipping.id_shipping, Shipping.id_carrier_api))
                .filter(Shipping.id_shipping == order.id_shipping)
                .first()
            )
            if shipping and shipping.id_carrier_api:
                # Carica carrier_api per recuperare il nome
                carrier_api = (
                    self.session.query(CarrierApi)
                    .options(load_only(CarrierApi.id_carrier_api, CarrierApi.name))
                    .filter(CarrierApi.id_carrier_api == shipping.id_carrier_api)
                    .first()
                )
                if carrier_api:
                    # Assegna carrier_api come attributo per accesso diretto
                    shipping.carrier_api = carrier_api
                else:
                    shipping.carrier_api = None
            order.shipments = shipping
        else:
            order.shipments = None
        
        return order

