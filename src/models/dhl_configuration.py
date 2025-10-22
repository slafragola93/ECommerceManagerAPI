from sqlalchemy import Integer, Column, String, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class DhlConfiguration(Base):
    __tablename__ = "dhl_configurations"
    
    id_dhl_config = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey('carriers_api.id_carrier_api', ondelete='CASCADE'), unique=True, index=True)
    
    # Campi specifici DHL
    description = Column(String(255))
    account_number = Column(Integer)
    password = Column(String(255))
    site_id = Column(String(100))
    company_name = Column(String(255))
    city = Column(String(100))
    address = Column(String(255))
    postal_code = Column(String(20))
    country_iso = Column(String(3))
    country = Column(String(100))
    reference_person = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    default_weight = Column(Numeric(10, 2))
    package_height = Column(Integer)
    package_width = Column(Integer)
    package_depth = Column(Integer)
    goods_description = Column(Text)
    
    # Campi select (salvano solo il valore scelto come stringa)
    layout = Column(String(20))
    cash_on_delivery = Column(String(10))
    print_waybill = Column(String(10))
    sku_quantity = Column(String(10))
    national_service = Column(String(100))
    international_service = Column(String(100))
    
    # Relationship 1:1
    carrier_api = relationship("CarrierApi", back_populates="dhl_configuration")
