from sqlalchemy import Integer, Column, String, func, Date, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id_address = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0)
    id_country = Column(Integer, ForeignKey("countries.id_country"), default=None)
    id_customer = Column(Integer, ForeignKey("customers.id_customer"), default=None)
    company = Column(String(255), default=None)
    firstname = Column(String(255), default=None)
    lastname = Column(String(255), default=None)
    address1 = Column(String(128), default=None)
    address2 = Column(String(128), default=None)
    state = Column(String(128), default=None)
    postcode = Column(String(12), default=None)
    city = Column(String(64), default=None)
    phone = Column(String(32), default=None)
    mobile_phone = Column(String(32), default=None)
    vat = Column(String(32), default=None)
    dni = Column(String(16), default=None)
    pec = Column(String(128), default=None)
    sdi = Column(String(128), default=None)
    date_add = Column(Date, default=func.now())

    customers = relationship("Customer", back_populates="addresses")
    country = relationship("Country", back_populates="addresses")
    address_delivery = relationship(
        "OrderDocument",
        foreign_keys="[OrderDocument.id_address_delivery]",  # Explicitly state the FK to use
        back_populates="address_delivery"
    )
    address_invoice = relationship(
        "OrderDocument",
        foreign_keys="[OrderDocument.id_address_invoice]",  # Explicitly state the FK to use
        back_populates="address_invoice"
    )