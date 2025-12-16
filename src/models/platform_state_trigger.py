"""
Model per PlatformStateTrigger - Configurazione trigger sincronizzazione stati con piattaforme ecommerce
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base


class PlatformStateTrigger(Base):
    """Model per configurazione trigger sincronizzazione stati piattaforma"""
    
    __tablename__ = "platform_state_triggers"
    
    id_trigger = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True, comment="Tipo evento (es. order_status_changed, shipping_status_changed)")
    id_store = Column(Integer, ForeignKey('stores.id_store', ondelete='CASCADE'), nullable=False, index=True, comment="ID dello store associato")
    state_type = Column(String(20), nullable=False, comment="Tipo di stato: 'order_state' o 'shipping_state'")
    id_state_local = Column(Integer, nullable=False, comment="ID stato locale (OrderState.id_order_state o ShippingState.id_shipping_state)")
    id_state_platform = Column(Integer, ForeignKey('ecommerce_order_states.id_ecommerce_order_state', ondelete='SET NULL'), nullable=True, comment="ID stato sulla piattaforma remota (riferimento a ecommerce_order_states)")
    is_active = Column(Boolean, nullable=False, default=True, server_default='1', index=True)
    created_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="state_triggers")
    ecommerce_order_state = relationship("EcommerceOrderState", back_populates="platform_state_triggers")

