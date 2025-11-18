from sqlalchemy import Integer, Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class BrtConfiguration(Base):
    __tablename__ = "brt_configurations"
    
    id_brt_config = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey('carriers_api.id_carrier_api', ondelete='CASCADE'), unique=True, index=True)
    
    # Campi specifici BRT
    description = Column(String(255))
    sender = Column(String(255))
    api_user = Column(String(100))
    api_password = Column(String(255))
    departure_line = Column(Integer)
    client_code = Column(Integer)
    departure_branch = Column(Integer)
    departure_depot = Column(Integer)
    rate_code = Column(Integer)
    service_type = Column(String(100))
    default_weight = Column(Integer)
    notes = Column(Text)
    
    # Campi select (salvano solo il valore scelto come stringa)
    collection_mode = Column(String(50))
    network = Column(String(50))
    label_format = Column(String(50))
    customer_notification = Column(String(50))
    tracking_type = Column(String(50))
    
    # Relationship 1:1
    carrier_api = relationship("CarrierApi", back_populates="brt_configuration")
