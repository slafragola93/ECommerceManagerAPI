from sqlalchemy import Integer, Column, Float, ForeignKey
from sqlalchemy.orm import relationship

from src import Base


class OrderPackage(Base):
    __tablename__ = "order_packages"

    id_order_package = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey("orders.id_order"), nullable=True, default=None)
    height = Column(Float)
    width = Column(Float)
    depth = Column(Float)
    weight = Column(Float)
    value = Column(Float, default=0.0)

    orders = relationship("Order", back_populates="order_packages")
