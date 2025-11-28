from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class CarrierPrice(Base):
    __tablename__ = "carrier_prices"

    id_carrier_price = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey("carriers_api.id_carrier_api"), nullable=False, index=True)
    postal_codes = Column(String(1000), nullable=True)  # Lista separata da virgola
    countries = Column(String(1000), nullable=True)     # Lista separata da virgola
    min_weight = Column(Numeric(10, 5), nullable=True)
    max_weight = Column(Numeric(10, 5), nullable=True)
    price_with_tax = Column(Numeric(10, 5), nullable=True)

    # Relationship with CarrierApi
    carrier_api = relationship("CarrierApi", back_populates="carrier_prices")

