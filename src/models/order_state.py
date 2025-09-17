from sqlalchemy import Integer, Column, String, Table
from sqlalchemy.orm import relationship, foreign

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
    orders = relationship("Order", secondary=orders_history, back_populates="order_states",
                         primaryjoin="OrderState.id_order_state == foreign(orders_history.c.id_order_state)",
                         secondaryjoin="foreign(orders_history.c.id_order) == Order.id_order")
