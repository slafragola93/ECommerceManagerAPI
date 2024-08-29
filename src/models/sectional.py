from sqlalchemy import Integer, Column, String
from sqlalchemy.orm import relationship

from src import Base


class Sectional(Base):
    __tablename__ = "sectionals"

    id_sectional = Column(Integer, primary_key=True, index=True)
    name = Column(String(128))

    orders_document = relationship("OrderDocument", back_populates="sectional")