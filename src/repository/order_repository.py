from sqlalchemy.orm import Session
from .address_repository import AddressRepository
from .customer_repository import CustomerRepository
from .sectional_repository import SectionalRepository
from .shipping_repository import ShippingRepository
from .tax_repository import TaxRepository
from .. import AddressSchema, SectionalSchema, ShippingSchema
from ..models import Order
from src.schemas.customer_schema import *
from ..schemas.order_schema import OrderSchema
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
        self.order_state_repository = OrderRepository(session)
        self.tax_repository = TaxRepository(session)
        self.customer_repository = CustomerRepository(session)

    # def get_all(self,
    #             page: int = 1, limit: int = 10
    #             ):
    #
    #     orders_result = self.session.query(Order).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()
    #
    #     return orders_result

    # def get_count(self,
    #               lang_ids: Optional[str] = None,
    #               ) -> AllOrderResponseSchema:
    #     """
    #     Recupera tutti i clienti
    #
    #     Returns:
    #         AllOrderResponseSchema: Tutti i clienti
    #     """
    #     query = self.session.query(func.count(Order.id_customer))
    #
    #     try:
    #         query = QueryUtils.filter_by_id(query, Order, 'id_lang', lang_ids)
    #
    #     except ValueError:
    #         raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")
    #
    #     customers_result = query.scalar()
    #
    #     return customers_result

    # def get_by_id(self, _id: int) -> OrderResponseSchema:
    #     return self.session.query(Order).filter(Order.id_customer == _id).first()

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

        # Se oggetto Address (quindi da creare)
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
        else:
            # Creare sistema che crei shipping calcolando carrier api e shipping state

            order.id_shipping = self.shipping_repository.create_and_get_id(ShippingSchema(
                id_carrier_api=1,
                id_shipping_state=1,
                id_tax=self.tax_repository.define_tax(data.address_delivery.id_country),
                tracking="",
                weight=0.0,
                price_tax_incl=0.0,
                price_tax_excl=0.0
            ))

        if isinstance(data.sectional, SectionalSchema):
            order.id_sectional = QueryUtils.create_and_set_id(repository=self.sectional_repository,
                                                              schema_datas=data,
                                                              field_name="sectional")

        # Set stato di default per l'ordine
        order.order_states = [self.order_state_repository.get_by_id(1)]

        self.session.add(order)
        self.session.commit()

    # def update_order_status(self, id_order: int, id_order_state: int):
    #     order_history = OrderHistory(id_order=id_order, id_order_state=id_order_state)
    #
    #     self.session.add(order_history)
    #     self.session.commit()
    #     self.session.refresh(order_history)

    # def update(self, edited_customer: Order, data: OrderSchema):
    #
    #     entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati
    #
    #     for key, value in entity_updated.items():
    #         if hasattr(edited_customer, key) and value is not None:
    #             setattr(edited_customer, key, value)
    #
    #     self.session.add(edited_customer)
    #     self.session.commit()
    #
    # def delete(self, customer: Order) -> bool:
    #     self.session.delete(customer)
    #     self.session.commit()
    #
    #     return True
