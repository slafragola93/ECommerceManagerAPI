from datetime import datetime

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text

from ..database import Base


class Shipping(Base):
    __tablename__ = "shipments"

    id_shipping = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, index=True, default=None)
    id_shipping_state = Column(Integer, index=True, default=None)
    id_tax = Column(Integer)
    tracking = Column(String(100), default=None, index=True)
    weight = Column(Numeric(10, 5), default=0)
    price_tax_incl = Column(Numeric(10, 5), default=0)
    price_tax_excl = Column(Numeric(10, 5), default=0)
    customs_value = Column(Numeric(10, 5), default=None)
    shipping_message = Column(Text)
    date_add = Column(DateTime, default=datetime.now)

    orders = relationship("Order", back_populates="shipments")
