from sqlalchemy import Integer, Column, String
from sqlalchemy.orm import relationship

from src.database import Base


class Country(Base):
    __tablename__ = "countries"

    id_country = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, index=True)
    name = Column(String(200))
    iso_code = Column(String(5))

    addresses = relationship("Address", back_populates="country")
    taxes = relationship("Tax", back_populates="country")
