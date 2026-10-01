from datetime import datetime
from sqlalchemy import Column, Enum, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base


class MFAPendingSession(Base):
    __tablename__ = 'mfa_pending_sessions'

    id         = Column(Integer, primary_key=True, index=True)
    id_user    = Column(Integer, ForeignKey('users.id_user'), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # metodo 2FA usato in questa sessione
    mfa_method    = Column(
                      Enum('totp', 'email'),
                      nullable=False
                    )

    # usato solo se mfa_method = 'email'
    # contiene il SHA-256 del codice inviato via email
    # NULL se mfa_method = 'totp'
    otp_code_hash = Column(String(255), nullable=True)

    # Tentativi falliti sulla sessione (lock dopo MAX)
    failed_attempts = Column(Integer, default=0, nullable=False)

    # Relazione
    user = relationship('User', back_populates='mfa_pending_sessions')

    @property
    def is_valid(self):
        """
        True se il token non è ancora stato usato e non è scaduto.
        """
        return (
            self.used_at is None and
            self.expires_at > datetime.now()
        )

    def consume(self):
        """
        Marca il token come usato.
        Chiamato dopo la verifica del codice TOTP/OTP.
        """
        self.used_at = datetime.now()
