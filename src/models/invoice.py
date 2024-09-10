from sqlalchemy import Integer, Column, String, Boolean, Date, func, ForeignKey
from sqlalchemy.orm import relationship

from src import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id_invoice = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, index=True, nullable=True, default=None)
    id_address_delivery = Column(Integer, index=True, nullable=True, default=None)
    id_address_invoice = Column(Integer, index=True, nullable=True, default=None)
    id_customer = Column(Integer, index=True, nullable=True, default=None)
    id_payment = Column(Integer, ForeignKey('payments.id_payment'), index=True, nullable=True, default=None)
    invoice_status = Column(String(50), nullable=True)
    note = Column(String(150), nullable=True)
    payed = Column(Boolean, nullable=True)
    document_number = Column(Integer)
    date_add = Column(Date, default=func.current_date())

    payments = relationship("Payment", back_populates="invoice")
