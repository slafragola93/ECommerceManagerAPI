from sqlalchemy import Integer, Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class FedexConfiguration(Base):
    __tablename__ = "fedex_configurations"
    
    id_fedex_config = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey('carriers_api.id_carrier_api', ondelete='CASCADE'), unique=True, index=True)
    
    # Campi specifici Fedex
    description = Column(String(255))
    client_id = Column(String(255))
    client_secret = Column(String(255))
    account_number = Column(Integer)
    person_name = Column(String(255))
    company_name = Column(String(255))
    phone_number = Column(String(50))
    address = Column(String(255))
    city = Column(String(100))
    state_or_province_code = Column(String(10))
    postal_code = Column(String(20))
    country_code = Column(String(3))
    package_height = Column(Integer)
    package_width = Column(Integer)
    package_depth = Column(Integer)
    default_weight = Column(Integer)
    
    # Campi select (salvano solo il valore scelto come stringa)
    sandbox = Column(String(10))
    service_type = Column(String(100))
    packaging_type = Column(String(100))
    pickup_type = Column(String(100))
    customs_charges = Column(String(50))
    format = Column(String(20))
    notes_field = Column(String(10))
    
    # Relationship 1:1
    carrier_api = relationship("CarrierApi", back_populates="fedex_configuration")
