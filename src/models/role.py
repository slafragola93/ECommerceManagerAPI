from sqlalchemy.orm import relationship

from .user import user_roles
from ..database import Base
from sqlalchemy import Column, Integer, String


class Role(Base):
    __tablename__ = 'roles'

    id_role = Column(Integer, primary_key=True, index=True)
    name = Column(String(15), unique=True, index=True)
    permissions = Column(String(10), default='r')
    users = relationship('User', secondary=user_roles, back_populates='roles')
