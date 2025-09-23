from datetime import datetime

from sqlalchemy import Integer, Column, Text, Boolean, Date, Float, Table, ForeignKey
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
    id_origin = Column(Integer, index=True, nullable=True)
    id_address_delivery = Column(Integer, index=True, nullable=True, default=None)
    id_address_invoice = Column(Integer, index=True, nullable=True, default=None)
    id_customer = Column(Integer, index=True, nullable=True, default=None)
    id_platform = Column(Integer, index=True, nullable=True, default=1)
    id_payment = Column(Integer, index=True, nullable=True, default=None)
    id_shipping = Column(Integer, ForeignKey('shipments.id_shipping'), default=None)
    id_sectional = Column(Integer, index=True, nullable=True, default=None)
    id_order_state = Column(Integer, default=1)
    is_invoice_requested = Column(Boolean, default=False)
    is_payed = Column(Boolean, default=False)
    payment_date = Column(Date, nullable=True)
    total_weight = Column(Float, default=0)
    total_price = Column(Float, default=0)
    cash_on_delivery = Column(Float, default=0)
    insured_value = Column(Float, default=0)
    privacy_note = Column(Text, nullable=True)
    general_note = Column(Text, nullable=True)
    delivery_date = Column(Date, nullable=True)
    date_add = Column(Date, default=datetime.today)

    # Relazioni
    order_states = relationship("OrderState", secondary=orders_history, back_populates="orders")
    shipments = relationship("Shipping", back_populates="orders")
    orders_document = relationship("OrderDocument", back_populates="order")
    invoices = relationship("Invoice", back_populates="order")
