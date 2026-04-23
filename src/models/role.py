from sqlalchemy.orm import relationship
from .relations.relations import user_roles
from ..database import Base
from sqlalchemy import Column, Integer, String, Boolean, Enum
import enum


class PermissionType(enum.Enum):
    full_crud = "full_crud"
    custom    = "custom"


class Role(Base):
    __tablename__ = 'roles'

    id_role         = Column(Integer, primary_key=True, index=True)
    name            = Column(String(50), unique=True, index=True)
    description     = Column(String(255), nullable=True)
    permission_type = Column(
                        Enum(PermissionType),
                        default=PermissionType.custom,
                        nullable=False
                      )
    is_system       = Column(Boolean, default=False, nullable=False)
    # True = ruolo non eliminabile (ADMIN, Manager, User)
    # False = ruolo personalizzato creato dall'admin

    # Relazioni
    users = relationship(
        'User',
        secondary=user_roles,
        back_populates='roles'
    )
    module_permissions = relationship(
        'UserModulePermission',
        back_populates='role',
        foreign_keys='UserModulePermission.id_role'
    )