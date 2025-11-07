from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class CarrierAssignment(Base):
    __tablename__ = "carrier_assignments"

    id_carrier_assignment = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey("carriers_api.id_carrier_api"), nullable=False, index=True)
    postal_codes = Column(String(1000), nullable=True)  # JSON string with postal codes list
    countries = Column(String(1000), nullable=True)     # JSON string with country IDs list
    origin_carriers = Column(String(1000), nullable=True)  # JSON string with origin carrier IDs list
    min_weight = Column(Numeric(10, 5), nullable=True)
    max_weight = Column(Numeric(10, 5), nullable=True)

    # Relationship with CarrierApi
    carrier_api = relationship("CarrierApi", back_populates="carrier_assignments")
