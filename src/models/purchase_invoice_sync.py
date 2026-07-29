from sqlalchemy import (
    Integer,
    Column,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    Numeric,
    ForeignKey,
    func,
    Index,
)
from sqlalchemy.orm import relationship

from src.database import Base


class PurchaseInvoiceSync(Base):
    """
    Modello SQLAlchemy per la tabella 'fatture_acquisto_sync'.

    Memorizza i documenti di acquisto sincronizzati dal POOL FatturaPA
    (fatture TD01 e note di credito TD04 ricevute dai fornitori via SdI).
    """

    __tablename__ = "fatture_acquisto_sync"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identificativo_sdi = Column(String(50), nullable=False, index=True)
    nome_file = Column(String(255), nullable=False, index=True)
    direzione = Column(String(50), nullable=True, index=True)
    tipo = Column(String(50), nullable=True, index=True)
    blob_uri = Column(String(1000), nullable=True)
    xml_content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    partition_key = Column(String(100), nullable=True)
    row_key = Column(String(100), nullable=True)
    etag = Column(String(100), nullable=True)

    # Consultazione da XML
    tipo_documento = Column(String(10), nullable=True, index=True)
    numero_documento = Column(String(100), nullable=True, index=True)
    data_documento = Column(Date, nullable=True, index=True)
    fornitore_denominazione = Column(String(255), nullable=True)
    fornitore_piva = Column(String(30), nullable=True, index=True)
    importo_totale = Column(Numeric(15, 2), nullable=True)
    fattura_collegata_numero = Column(String(100), nullable=True)
    fattura_collegata_data = Column(Date, nullable=True)

    # Operativi FE
    is_paid = Column(Boolean, nullable=False, default=False, index=True)
    id_payment = Column(
        Integer,
        ForeignKey("payments.id_payment"),
        nullable=True,
        index=True,
    )
    paid_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)

    # Invio email documento (stato rapido FE)
    mail_status = Column(String(20), nullable=True)  # sent|pending|error
    mail_error_message = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    date_add = Column(DateTime, default=func.now())
    date_upd = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_sdi_nomefile", "identificativo_sdi", "nome_file", unique=True),
    )

    details = relationship(
        "PurchaseInvoiceSyncDetail",
        back_populates="purchase_invoice",
        cascade="all, delete-orphan",
        order_by="PurchaseInvoiceSyncDetail.numero_linea",
    )
    payment = relationship("Payment", foreign_keys=[id_payment])

    def __repr__(self):
        return (
            f"<PurchaseInvoiceSync(id={self.id}, sdi={self.identificativo_sdi}, "
            f"file={self.nome_file})>"
        )
