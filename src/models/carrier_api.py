from sqlalchemy import Integer, Column, String, Boolean, Enum
from sqlalchemy.orm import relationship
from src.database import Base
import enum


class CarrierTypeEnum(str, enum.Enum):
    BRT = "BRT"
    FEDEX = "FEDEX"
    DHL = "DHL"


class CarrierApi(Base):
    __tablename__ = "carriers_api"

    id_carrier_api = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    carrier_type = Column(Enum(CarrierTypeEnum), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    api_key = Column(String(200), default="")
    
    # Generic authentication fields
    use_sandbox = Column(Boolean, default=False, nullable=False)
    # Relationships
    carrier_assignments = relationship("CarrierAssignment", back_populates="carrier_api")
    carrier_prices = relationship("CarrierPrice", back_populates="carrier_api")
    
    # Relationships with configurations
    # BRT and DHL: 1:1 relationship
    brt_configuration = relationship("BrtConfiguration", back_populates="carrier_api", uselist=False, cascade="all, delete-orphan")
    dhl_configuration = relationship("DhlConfiguration", back_populates="carrier_api", uselist=False, cascade="all, delete-orphan")
    # FedEx: 1:N relationship 
    fedex_configurations = relationship("FedexConfiguration", back_populates="carrier_api", uselist=True, cascade="all, delete-orphan")