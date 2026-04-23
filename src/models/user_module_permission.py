from datetime import datetime
from sqlalchemy import (Column, Integer, Boolean,
                        DateTime, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship
from ..database import Base


class UserModulePermission(Base):
    __tablename__ = 'user_module_permissions'

    id        = Column(Integer, primary_key=True, index=True)
    id_user   = Column(Integer, ForeignKey('users.id_user'), nullable=True)
    id_role   = Column(Integer, ForeignKey('roles.id_role'), nullable=True)
    id_module = Column(Integer, ForeignKey('app_modules.id_module'), nullable=False)

    can_read   = Column(Boolean, default=False, nullable=False)
    can_create = Column(Boolean, default=False, nullable=False)
    can_update = Column(Boolean, default=False, nullable=False)
    can_delete = Column(Boolean, default=False, nullable=False)

    created_by = Column(Integer, ForeignKey('users.id_user'), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)

    # Vincoli unicità
    __table_args__ = (
        UniqueConstraint(
            'id_role', 'id_module',
            name='uq_role_module'
        ),
        UniqueConstraint(
            'id_user', 'id_module',
            name='uq_user_module'
        ),
    )

    # Relazioni
    user = relationship(
        'User',
        foreign_keys=[id_user],
        back_populates='module_permissions'
    )
    role = relationship(
        'Role',
        foreign_keys=[id_role],
        back_populates='module_permissions'
    )
    module = relationship(
        'AppModule',
        back_populates='user_permissions'
    )
    creator = relationship(
        'User',
        foreign_keys=[created_by]
    )