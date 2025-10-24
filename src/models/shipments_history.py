from sqlalchemy import Integer, Column, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from src.database import Base
import enum


class SourceEnum(str, enum.Enum):
    MANUAL = "manual"
    DHL_TRACKING = "dhl_tracking"
    API_UPDATE = "api_update"


class ShipmentsHistory(Base):
    __tablename__ = "shipments_history"
    
    id = Column(Integer, primary_key=True, index=True)
    id_shipping = Column(Integer, ForeignKey('shipments.id_shipping'), nullable=False)
    id_shipping_state = Column(Integer, ForeignKey('shipping_state.id_shipping_state'), nullable=False)
    id_shipping_state_previous = Column(Integer, ForeignKey('shipping_state.id_shipping_state'), nullable=True)
    tracking_event_code = Column(String(10), nullable=True)  # typeCode DHL (PU, OK, ecc.)
    tracking_event_description = Column(Text, nullable=True)
    changed_at = Column(DateTime, nullable=False, index=True)
    source = Column(Enum(SourceEnum), nullable=False, default=SourceEnum.DHL_TRACKING)
    
    # Relationships
    shipping = relationship("Shipping")
    shipping_state = relationship("ShippingState", foreign_keys=[id_shipping_state])
    shipping_state_previous = relationship("ShippingState", foreign_keys=[id_shipping_state_previous])
