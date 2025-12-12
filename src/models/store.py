from sqlalchemy import Integer, Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from src.database import Base


class Store(Base):
    __tablename__ = "stores"

    id_store = Column(Integer, primary_key=True, index=True)
    id_platform = Column(Integer, ForeignKey('platforms.id_platform'), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    vat_number = Column(String(50), nullable=True, index=True)
    country_code = Column(String(5), nullable=True, index=True)
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
    company_fiscal_infos = relationship("CompanyFiscalInfo", back_populates="store")

