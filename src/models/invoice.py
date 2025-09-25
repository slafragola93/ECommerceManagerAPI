from sqlalchemy import Integer, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from src.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id_invoice = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey("orders.id_order"), nullable=False)
    document_number = Column(String(10), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    xml_content = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, uploaded, sent, error
    upload_result = Column(Text, nullable=True)  # JSON result from upload
    date_add = Column(DateTime, default=datetime.utcnow)
    date_upd = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order = relationship("Order", back_populates="invoices")