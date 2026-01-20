from datetime import datetime

from sqlalchemy import Integer, Column, Text, Boolean, Date, DateTime, Numeric, Table, ForeignKey, String
from sqlalchemy.orm import relationship
from .relations.relations import orders_history

from src import Base

# orders_history = Table('orders_history', Base.metadata,
#                        Column('id_order', Integer, ForeignKey('orders.id_order')),
#                        Column('id_order_state', Integer, ForeignKey('order_states.id_order_state'))
#                        )



class Order(Base):
    __tablename__ = "orders"

    id_order = Column(Integer, primary_key=True, index=True)
    reference = Column(String(255), nullable=True)
    internal_reference = Column(String(12), nullable=True, index=True)  # Max 12 caratteri (potrebbe cambiare in futuro)
    id_origin = Column(Integer, index=True, nullable=True)
    id_address_delivery = Column(Integer, index=True, nullable=True, default=None)
    id_address_invoice = Column(Integer, index=True, nullable=True, default=None)
    id_customer = Column(Integer, index=True, nullable=True, default=None)
    id_platform = Column(Integer, ForeignKey('platforms.id_platform'), index=True, nullable=True, default=1)
    id_store = Column(Integer, ForeignKey('stores.id_store'), index=True, nullable=True, default=1)
    id_payment = Column(Integer, index=True, nullable=True, default=None)
    id_carrier = Column(Integer, ForeignKey('carriers.id_carrier'), default=0, nullable=True)
    id_shipping = Column(Integer, ForeignKey('shipments.id_shipping'), default=None)
    id_sectional = Column(Integer, index=True, nullable=True, default=None)
    id_order_state = Column(Integer, default=1)
    id_ecommerce_state = Column(Integer, ForeignKey('ecommerce_order_states.id_ecommerce_order_state', ondelete='SET NULL'), nullable=True, index=True, comment="ID stato corrente sull'e-commerce remoto (PrestaShop, Shopify, ecc.)")
    is_invoice_requested = Column(Boolean, default=False)
    is_payed = Column(Boolean, default=False)
    payment_date = Column(Date, nullable=True)
    total_weight = Column(Numeric(10, 5), default=0)
    total_price_with_tax = Column(Numeric(10, 5), nullable=False, default=0)  # ex total_with_tax, ex total_paid
    total_price_net = Column(Numeric(10, 5), default=0.0, nullable=True)  # ex total_without_tax
    products_total_price_net = Column(Numeric(10, 5), default=0.0, nullable=False)  # Totale imponibile prodotti (senza shipping)
    products_total_price_with_tax = Column(Numeric(10, 5), default=0.0, nullable=False)  # Totale con IVA prodotti (senza shipping)
    total_discounts = Column(Numeric(10, 5), default=0.0)
    cash_on_delivery = Column(Numeric(10, 5), default=0)
    insured_value = Column(Numeric(10, 5), default=0)
    privacy_note = Column(Text, nullable=True)
    general_note = Column(Text, nullable=True)
    delivery_date = Column(Date, nullable=True)
    date_add = Column(DateTime, default=datetime.now)
    updated_at = Column(String(19), nullable=True)  # Formato: DD-MM-YYYY hh:mm:ss
    is_multishipping = Column(Integer, default=0, nullable=False, comment="1 se ordine in multispedizione")

    # Relazioni
    platform = relationship("Platform", back_populates="orders")
    store = relationship("Store", back_populates="orders")
    order_states = relationship("OrderState", secondary=orders_history, back_populates="orders")
    carrier = relationship("Carrier", back_populates="orders")
    shipments = relationship("Shipping", back_populates="orders")
    orders_document = relationship("OrderDocument", back_populates="order")
    fiscal_documents = relationship("FiscalDocument", back_populates="order")
    order_packages = relationship("OrderPackage", back_populates="order")
    ecommerce_order_state = relationship("EcommerceOrderState", back_populates="orders")
