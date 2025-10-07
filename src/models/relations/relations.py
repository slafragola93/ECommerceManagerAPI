from sqlalchemy import Table, Column, Integer, ForeignKey, DateTime
from datetime import datetime

from ...database import Base


orders_history = Table('orders_history', Base.metadata,
                       Column('id_order', Integer, ForeignKey('orders.id_order')),
                       Column('id_order_state', Integer, ForeignKey('order_states.id_order_state')),
                       Column('date_add', DateTime, default=datetime.now)
                       )
user_roles = Table('user_roles', Base.metadata,
                   Column('id_user', Integer, ForeignKey('users.id_user')),
                   Column('id_role', Integer, ForeignKey('roles.id_role'))
                   )