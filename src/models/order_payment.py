from datetime import datetime

from sqlalchemy import Integer, Column, String, Boolean, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class OrderPayment(Base):
    """Singolo pagamento/incasso collegato a un ordine (non una rata)."""

    __tablename__ = "order_payments"

    id_order_payment = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, ForeignKey("orders.id_order"), nullable=False, index=True)
    id_payment = Column(Integer, ForeignKey("payments.id_payment"), nullable=False, index=True)
    amount = Column(Numeric(10, 5), nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    payment_date = Column(Date, nullable=True)
    note = Column(String(200), nullable=True)
    date_add = Column(DateTime, default=datetime.now, nullable=False)

    order = relationship("Order", back_populates="order_payments")
    payment = relationship("Payment")
