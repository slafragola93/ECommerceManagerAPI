from sqlalchemy import Integer, Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id_payment = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    is_complete_payment = Column(Boolean, default=False)

    invoice = relationship("Invoice", back_populates="payments")
