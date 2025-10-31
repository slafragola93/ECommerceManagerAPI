from sqlalchemy import Integer, Column, Float, ForeignKey
from sqlalchemy.orm import relationship
from src import Base


class OrderPackage(Base):
    __tablename__ = "order_packages"

    id_order_package = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey('orders.id_order'), index=True, nullable=True, default=None)
    id_order_document = Column(Integer, ForeignKey('orders_document.id_order_document'), index=True, nullable=True, default=None)
    height = Column(Float)
    width = Column(Float)
    depth = Column(Float)
    length = Column(Float)
    weight = Column(Float)
    value = Column(Float, default=0.0)
    
    # Relazioni
    order = relationship("Order", back_populates="order_packages")
    order_document = relationship("OrderDocument", back_populates="order_packages")

