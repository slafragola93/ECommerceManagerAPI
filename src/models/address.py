from sqlalchemy import Integer, Column, String, func, Date
from src.database import Base


class Address(Base):

    __tablename__ = "addresses"

    id_address = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0)
    id_country = Column(Integer, index=True)
    id_customer = Column(Integer, default=0, index=True)
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


