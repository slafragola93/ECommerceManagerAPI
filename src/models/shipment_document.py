from sqlalchemy import Integer, Column, String, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


class ShipmentDocument(Base):
    __tablename__ = "shipment_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    awb = Column(String(50), nullable=False, index=True)
    order_id = Column(Integer, nullable=True, index=True)  # Order ID for easy retrieval
    carrier_api_id = Column(Integer, nullable=True, index=True)  # Carrier API ID for easy retrieval
    type_code = Column(String(50), nullable=False)  # label, invoice, customsDoc, waybillDoc
    file_path = Column(String(500), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)  # application/pdf
    sha256_hash = Column(String(64), nullable=False, index=True)
    size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
