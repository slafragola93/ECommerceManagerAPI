from sqlalchemy import Integer, Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from typing import Optional
from src.database import Base


class Store(Base):
    __tablename__ = "stores"

    id_store = Column(Integer, primary_key=True, index=True)
    id_platform = Column(Integer, ForeignKey('platforms.id_platform'), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    logo = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    date_add = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    platform = relationship("Platform", back_populates="stores")
    orders = relationship("Order", back_populates="store")
    products = relationship("Product", back_populates="store")
    customers = relationship("Customer", back_populates="store")
    addresses = relationship("Address", back_populates="store")
    fiscal_documents = relationship("FiscalDocument", back_populates="store")
    order_documents = relationship("OrderDocument", back_populates="store")
    app_configurations = relationship("AppConfiguration", back_populates="store")
    company_fiscal_infos = relationship("CompanyFiscalInfo", back_populates="store", cascade="all, delete-orphan")
    carrier_assignments = relationship("CarrierAssignment", back_populates="store")
    state_triggers = relationship("PlatformStateTrigger", back_populates="store", cascade="all, delete-orphan")
    ecommerce_order_states = relationship("EcommerceOrderState", back_populates="store", cascade="all, delete-orphan")
    
    def get_default_vat_number(self) -> Optional[str]:
        """
        Recupera la P.IVA principale dall'informazione fiscale di default.
        Returns None se non esiste una CompanyFiscalInfo di default.
        """
        default_fiscal = next((c for c in self.company_fiscal_infos if c.is_default), None)
        return default_fiscal.vat_number if default_fiscal else None
    
    def get_default_country_code(self) -> Optional[str]:
        """
        Recupera il codice paese principale dall'informazione fiscale di default.
        Returns None se non esiste una CompanyFiscalInfo di default.
        """
        default_fiscal = next((c for c in self.company_fiscal_infos if c.is_default), None)
        return default_fiscal.country if default_fiscal else None
    
    def get_default_fiscal_info(self):
        """
        Recupera l'informazione fiscale principale (is_default=True).
        Returns None se non esiste.
        """
        return next((c for c in self.company_fiscal_infos if c.is_default), None)

