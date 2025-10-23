from sqlalchemy import Integer, Column, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from src.database import Base
import enum


class EnvironmentEnum(str, enum.Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class ShipmentRequest(Base):
    __tablename__ = "shipment_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey('orders.id_order'), nullable=False)
    id_carrier_api = Column(Integer, ForeignKey('carriers_api.id_carrier_api'), nullable=False)
    awb = Column(String(50), nullable=True, index=True)
    message_reference = Column(String(100), nullable=True, unique=True, index=True)
    request_json_redacted = Column(Text, nullable=True)
    response_json_redacted = Column(Text, nullable=True)
    environment = Column(Enum(EnvironmentEnum), nullable=False)
    status_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    # Relationships
    order = relationship("Order", back_populates="shipment_requests")
    carrier_api = relationship("CarrierApi")
    shipment_documents = relationship("ShipmentDocument", back_populates="shipment_request", cascade="all, delete-orphan")
