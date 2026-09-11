from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from src.database import Base


class FiscalDocumentSdiNotification(Base):
    """Storico notifiche SDI sul ciclo attivo (distinto da status workflow)."""

    __tablename__ = "fiscal_document_sdi_notifications"

    id_fiscal_document_sdi_notification = Column(
        Integer, primary_key=True, autoincrement=True
    )
    id_fiscal_document = Column(
        Integer,
        ForeignKey("fiscal_documents.id_fiscal_document"),
        nullable=False,
        index=True,
    )
    notification_type = Column(String(4), nullable=False, index=True)
    identificativo_sdi = Column(String(50), nullable=True, index=True)
    nome_file = Column(String(255), nullable=True)
    message = Column(String(500), nullable=True)
    payload = Column(Text, nullable=True)
    notified_at = Column(DateTime, nullable=True)
    date_add = Column(DateTime, default=func.now(), nullable=False)

    fiscal_document = relationship("FiscalDocument", back_populates="sdi_notifications")

    __table_args__ = (
        UniqueConstraint(
            "id_fiscal_document",
            "notification_type",
            "nome_file",
            name="uq_sdi_notification_doc_type_file",
        ),
    )
