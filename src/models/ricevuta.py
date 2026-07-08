import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from src.database import Base


class RicevutaStato(str, enum.Enum):
    EMESSA = "emessa"
    ANNULLATA = "annullata"


# Stato ordine oltre al quale la ricevuta non è più modificabile/eliminabile
ORDER_STATE_SPEDIZIONE_CONFERMATA = 4


class Ricevuta(Base):
    """Documento fiscale interno per clienti esteri privati (no SDI)."""

    __tablename__ = "ricevute"
    __table_args__ = (
        UniqueConstraint("numero", "anno", name="uq_ricevute_numero_anno"),
        Index("idx_ricevute_incasso", "data_incasso", "stato"),
        Index("idx_ricevute_emissione", "data_emissione", "stato"),
        Index("idx_ricevute_order", "id_order"),
    )

    id_ricevuta = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False)
    anno = Column(SmallInteger, nullable=False)

    id_order = Column(Integer, ForeignKey("orders.id_order"), nullable=False)
    id_customer = Column(Integer, ForeignKey("customers.id_customer"), nullable=False)

    data_incasso = Column(Date, nullable=False)
    data_emissione = Column(Date, nullable=False)

    stato = Column(
        Enum(
            RicevutaStato,
            values_callable=lambda choices: [item.value for item in choices],
        ),
        nullable=False,
        default=RicevutaStato.EMESSA,
    )

    pdf_path = Column(String(500), nullable=True)
    pdf_hash = Column(String(128), nullable=True)
    pdf_generated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    annullata_at = Column(DateTime, nullable=True)
    annullata_da_user_id = Column(Integer, ForeignKey("users.id_user"), nullable=True)

    order = relationship("Order", back_populates="ricevute")
    customer = relationship("Customer", back_populates="ricevute")
