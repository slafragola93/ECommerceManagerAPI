from sqlalchemy import Integer, Column, String, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Tax(Base):
    __tablename__ = "taxes"

    id_tax = Column(Integer, primary_key=True, index=True)
    id_country = Column(Integer, ForeignKey('countries.id_country'), index=True, nullable=True, default=None)
    is_default = Column(Integer, default=0)
    name = Column(String(200))
    note = Column(String(200), default=None)
    code = Column(String(10))
    percentage = Column(Integer, default=0)
    electronic_code = Column(String(10), default="")

    country = relationship("Country", back_populates="taxes")
    orders_document = relationship("OrderDocument", back_populates="tax")