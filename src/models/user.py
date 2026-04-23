from datetime import datetime
from sqlalchemy.orm import relationship
from ..database import Base
from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Enum
from .relations.relations import user_roles


class User(Base):
    __tablename__ = 'users'

    id_user     = Column(Integer, primary_key=True, index=True)
    username    = Column(String(100), unique=True, index=True)
    firstname   = Column(String(100))
    lastname    = Column(String(100))
    password    = Column(String(100))
    email       = Column(String(100), unique=True, index=True)
    is_active   = Column(Boolean, default=True)
    date_add    = Column(Date, default=datetime.now)

    # 2FA — nuovo
    totp_secret  = Column(String(255), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False)
    mfa_method   = Column(
                     Enum('totp', 'email', 'none'),
                     default='none',
                     nullable=False
                   )

    # Soft delete — nuovo
    deleted_at   = Column(DateTime, nullable=True)

    # Relazioni
    roles = relationship(
        'Role',
        secondary="user_roles",
        back_populates='users'
    )
    refresh_tokens = relationship(
        'RefreshToken',
        back_populates='user'
    )
    module_permissions = relationship(
        'UserModulePermission',
        back_populates='user'
    )

    mfa_pending_sessions = relationship(
    'MFAPendingSession',
    back_populates='user'
)