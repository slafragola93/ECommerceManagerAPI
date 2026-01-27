from sqlalchemy import Integer, Column, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id_carrier = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0, index=True)
    id_store = Column(Integer, ForeignKey('stores.id_store'), nullable=True, index=True, default=None)
    name = Column(String(200))
    
    # Relazioni
    orders = relationship("Order", back_populates="carrier")
    store = relationship("Store", back_populates="carriers")