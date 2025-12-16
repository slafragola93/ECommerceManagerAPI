"""
Model per EcommerceOrderState - Stati ordini recuperati dalle piattaforme e-commerce
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base


class EcommerceOrderState(Base):
    """Model per stati ordini recuperati dalle piattaforme e-commerce"""
    
    __tablename__ = "ecommerce_order_states"
    
    id_ecommerce_order_state = Column(Integer, primary_key=True, index=True)
    id_store = Column(Integer, ForeignKey('stores.id_store', ondelete='CASCADE'), nullable=False, index=True)
    id_platform_state = Column(Integer, nullable=False, comment="ID stato sulla piattaforma remota (PrestaShop, Shopify, ecc.)")
    name = Column(String(200), nullable=False, comment="Nome dello stato sulla piattaforma remota")
    platform_name = Column(String(50), nullable=False, comment="Nome della piattaforma (PrestaShop, Shopify, ecc.)")
    date_add = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="ecommerce_order_states")
    orders = relationship("Order", back_populates="ecommerce_order_state")
    platform_state_triggers = relationship("PlatformStateTrigger", back_populates="ecommerce_order_state")

