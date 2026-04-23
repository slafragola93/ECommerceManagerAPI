from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..database import Base


class AuthLog(Base):
    __tablename__ = 'auth_logs'

    id         = Column(Integer, primary_key=True, index=True)
    id_user    = Column(Integer, ForeignKey('users.id_user'), nullable=True)
    event      = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    extradata   = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relazione
    user = relationship('User', back_populates='auth_logs')