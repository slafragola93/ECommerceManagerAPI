from sqlalchemy import Integer, Column, String, Boolean
from sqlalchemy.orm import relationship
from src.database import Base


class CarrierApi(Base):
    __tablename__ = "carriers_api"

    id_carrier_api = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    account_number = Column(Integer, default=0)
    password = Column(String(200), default="")
    site_id = Column(String(200), default="")
    national_service = Column(String(200), default="")
    international_service = Column(String(200), default="")
    is_active = Column(Boolean, default=True)
    api_key = Column(String(200), default="")

    # Relationship with CarrierAssignment
    carrier_assignments = relationship("CarrierAssignment", back_populates="carrier_api")