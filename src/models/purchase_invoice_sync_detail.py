from sqlalchemy import Integer, Column, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class PurchaseInvoiceSyncDetail(Base):
    """
    Righe (DettaglioLinee) di un documento di acquisto sincronizzato dal POOL.
    Snapshot da XML FatturaPA — prodotto o servizio del fornitore.
    """

    __tablename__ = "fatture_acquisto_sync_details"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_purchase_invoice_sync = Column(
        Integer,
        ForeignKey("fatture_acquisto_sync.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    numero_linea = Column(Integer, nullable=False, default=1)
    descrizione = Column(String(1000), nullable=True)
    codice_articolo = Column(String(100), nullable=True)
    quantita = Column(Numeric(12, 5), nullable=False, default=1)
    unita_misura = Column(String(20), nullable=True)
    prezzo_unitario = Column(Numeric(15, 5), nullable=True)
    prezzo_totale = Column(Numeric(15, 5), nullable=True)
    aliquota_iva = Column(Numeric(5, 2), nullable=True)
    natura = Column(String(10), nullable=True)

    purchase_invoice = relationship(
        "PurchaseInvoiceSync",
        back_populates="details",
    )

    def __repr__(self):
        return (
            f"<PurchaseInvoiceSyncDetail(id={self.id}, "
            f"invoice={self.id_purchase_invoice_sync}, linea={self.numero_linea})>"
        )
