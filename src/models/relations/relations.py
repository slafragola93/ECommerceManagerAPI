from sqlalchemy import Table, Column, ForeignKey, Integer

from ...database import Base

product_tags = Table('product_tags', Base.metadata,
                     Column('id_product', Integer, ForeignKey('products.id_product'), primary_key=True),
                     Column('id_tag', Integer, ForeignKey('tags.id_tag'), primary_key=True)
                     )

orders_history = Table('orders_history', Base.metadata,
                       Column('id_order', Integer, ForeignKey('orders.id_order')),
                       Column('id_order_state', Integer, ForeignKey('order_states.id_order_state'))
                       )
user_roles = Table('user_roles', Base.metadata,
                   Column('id_user', Integer, ForeignKey('users.id_user')),
                   Column('id_role', Integer, ForeignKey('roles.id_role'))
                   )
