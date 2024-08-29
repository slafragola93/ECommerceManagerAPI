from sqlalchemy import Integer, Column, String, Float, ForeignKey, Date, func
from sqlalchemy.orm import relationship

from src.database import Base


# preventivo e reso?
class OrderDocument(Base):
    __tablename__ = "orders_document"

    id_order_document = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey("orders.id_order"), index=True, default=None)
    id_tax = Column(Integer, ForeignKey("taxes.id_tax"), index=True, default=None)
    id_address_delivery = Column(Integer, ForeignKey("addresses.id_address"), index=True, default=None)
    id_address_invoice = Column(Integer, ForeignKey("addresses.id_address"), index=True, default=None)
    id_customer = Column(Integer, ForeignKey("customers.id_customer"), index=True, default=None)
    id_sectional = Column(Integer, ForeignKey("sectionals.id_sectional"), index=True, default=None)
    document_number = Column(String(32))
    type_document = Column(String(32))
    total_weight = Column(Float)
    total_price = Column(Float)
    delivery_price = Column(Float)
    note = Column(String(200))
    date_add = Column(Date, default=func.now())

    order = relationship("Order", back_populates="orders_document")
    tax = relationship("Tax", back_populates="orders_document")
    address_delivery = relationship("Address", foreign_keys=[id_address_delivery])
    address_invoice = relationship("Address", foreign_keys=[id_address_invoice])
    customer = relationship("Customer", back_populates="orders_document")
    sectional = relationship("Sectional", back_populates="orders_document")