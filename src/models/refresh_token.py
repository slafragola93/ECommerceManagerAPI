from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from ..database import Base


class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'

    id          = Column(Integer, primary_key=True, index=True)
    id_user     = Column(Integer, ForeignKey('users.id_user'), nullable=False)
    token_hash  = Column(String(255), unique=True, nullable=False)
    device_info = Column(String(255), nullable=True)
    ip_address  = Column(String(45), nullable=True)
    expires_at  = Column(DateTime, nullable=False)
    revoked_at  = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relazione
    user = relationship('User', back_populates='refresh_tokens')

    @property
    def is_valid(self):
        """
        Ritorna True se il token non è scaduto e non è stato revocato.
        Usato per verificare se il token è ancora utilizzabile.
        """
        return (
            self.revoked_at is None and
            self.expires_at > datetime.utcnow()
        )

    def revoke(self):
        """
        Marca il token come revocato.
        Chiamato durante il logout.
        """
        self.revoked_at = datetime.utcnow()