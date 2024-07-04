from sqlalchemy import Integer, Column, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from src import Base
from src.models.order import orders_history


# association_table = Table(
#     'orders_history', Base.metadata,
#     Column('id_order', Integer, ForeignKey('orders.id_order')),
#     Column('id_order_state', Integer, ForeignKey('order_states.id_order_state'))
# )


class OrderState(Base):
    __tablename__ = "order_states"

    id_order_state = Column(Integer, primary_key=True, index=True)
    name = Column(String(128))
    orders = relationship("Order",  secondary=orders_history, back_populates="order_states")
