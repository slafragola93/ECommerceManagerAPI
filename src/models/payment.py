from sqlalchemy import Integer, Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id_payment = Column(Integer, primary_key=True, index=True)
    id_store = Column(Integer, ForeignKey('stores.id_store'), nullable=True, index=True, default=None)
    name = Column(String(50))
    is_complete_payment = Column(Boolean, default=False)
    fiscal_mode_payment = Column(String(10), nullable=True, comment='Modalità di pagamento fiscale per FatturaPA (MP01-MP23)')

    # Relationships
    store = relationship("Store", back_populates="payments")
    
    # invoice = relationship("Invoice", back_populates="payments")  # Removed - no relationship needed
