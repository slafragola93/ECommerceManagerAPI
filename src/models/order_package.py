from sqlalchemy import Integer, Column, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from src import Base


class OrderPackage(Base):
    __tablename__ = "order_packages"

    id_order_package = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey('orders.id_order'), index=True, nullable=True, default=None)
    id_order_document = Column(Integer, ForeignKey('orders_document.id_order_document'), index=True, nullable=True, default=None)
    height = Column(Numeric(10, 5))
    width = Column(Numeric(10, 5))
    depth = Column(Numeric(10, 5))
    length = Column(Numeric(10, 5))
    weight = Column(Numeric(10, 5))
    value = Column(Numeric(10, 5), default=0.0)
    
    # Relazioni
    order = relationship("Order", back_populates="order_packages")
    order_document = relationship("OrderDocument", back_populates="order_packages")

