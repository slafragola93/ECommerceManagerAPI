from sqlalchemy import Integer, Column, String, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from src.database import Base


class FedexConfiguration(Base):
    __tablename__ = "fedex_configurations"
    
    id_fedex_config = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey('carriers_api.id_carrier_api', ondelete='CASCADE'), unique=True, index=True)
    
    # Campi specifici Fedex
    description = Column(String(255))
    
    # OAuth 2.0 Authentication fields
    client_id = Column(String(255))
    client_secret = Column(String(255))
    
    # Account information
    account_number = Column(String(50))  # Changed from Integer to String for flexibility
    
    # Shipper contact information
    person_name = Column(String(255))
    company_name = Column(String(255))
    phone_number = Column(String(50))
    contact_email = Column(String(255), nullable=True)  # Email address for shipper contact
    
    # Shipper address
    address = Column(String(255))
    city = Column(String(100))
    state_or_province_code = Column(String(10))
    postal_code = Column(String(20))
    country_code = Column(String(3))
    
    # Package defaults
    package_height = Column(Integer)
    package_width = Column(Integer)
    package_depth = Column(Integer)
    default_weight = Column(Numeric(10, 2))  # Changed from Integer to Numeric for decimal support
    
    # Shipment configuration fields
    service_type = Column(String(100))  # FEDEX_GROUND, FEDEX_EXPRESS_SAVER, PRIORITY_OVERNIGHT, etc.
    packaging_type = Column(String(100))  # YOUR_PACKAGING, FEDEX_PAK, FEDEX_BOX, etc.
    pickup_type = Column(String(100))  # DROPOFF_AT_FEDEX_LOCATION, USE_SCHEDULED_PICKUP, CONTACT_FEDEX_TO_SCHEDULE
    customs_charges = Column(String(50), nullable=True)  # SENDER, RECIPIENT, THIRD_PARTY, ACCOUNT - used for paymentType
    
    # Legacy/Deprecated fields (kept for backward compatibility)
    sandbox = Column(String(10), nullable=True)
    format = Column(String(20), nullable=True)  # Legacy label format
    notes_field = Column(String(10), nullable=True)
    
    # Relationship 1:1
    carrier_api = relationship("CarrierApi", back_populates="fedex_configuration")
