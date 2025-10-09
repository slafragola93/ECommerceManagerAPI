from sqlalchemy import Integer, Column, String, Text, DateTime, func, Index

from src.database import Base


class PurchaseInvoiceSync(Base):
    """
    Modello SQLAlchemy per la tabella 'fatture_acquisto_sync'.
    
    Memorizza i documenti di acquisto sincronizzati dal POOL FatturaPA.
    Ogni riga rappresenta un documento di acquisto (fattura o nota di credito) 
    ricevuto dal Sistema di Interscambio (SdI).
    
    Attributes:
        id (Column): Chiave primaria autoincrementale.
        identificativo_sdi (Column): Identificativo univoco assegnato dal SdI.
        nome_file (Column): Nome del file XML originale.
        direzione (Column): Direzione del documento (es. 'Acquisto' o 'Vendita').
        tipo (Column): Tipo di documento (es. 'Ricezione', 'Notifica', etc.).
        blob_uri (Column): URI del blob storage Azure dove è memorizzato il file.
        xml_content (Column): Contenuto XML completo del documento (opzionale).
        file_path (Column): Path locale dove è salvato il file (alternativo a xml_content).
        partition_key (Column): Chiave di partizione Azure Table Storage.
        row_key (Column): Chiave di riga Azure Table Storage.
        etag (Column): ETag per gestire concorrenza Azure Table Storage.
        created_at (Column): Timestamp di creazione del record.
        date_add (Column): Data di aggiunta al sistema.
        date_upd (Column): Data di ultimo aggiornamento.
    """
    __tablename__ = "fatture_acquisto_sync"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identificativo_sdi = Column(String(50), nullable=False, index=True)
    nome_file = Column(String(255), nullable=False, index=True)
    direzione = Column(String(50), nullable=True, index=True)
    tipo = Column(String(50), nullable=True, index=True)
    blob_uri = Column(String(1000), nullable=True)
    xml_content = Column(Text, nullable=True)  # Contenuto XML completo
    file_path = Column(String(500), nullable=True)  # Path locale alternativo
    partition_key = Column(String(100), nullable=True)
    row_key = Column(String(100), nullable=True)
    etag = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    date_add = Column(DateTime, default=func.now())
    date_upd = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Indice composto per garantire unicità su identificativo_sdi + nome_file
    __table_args__ = (
        Index('idx_sdi_nomefile', 'identificativo_sdi', 'nome_file', unique=True),
    )
    
    def __repr__(self):
        return f"<PurchaseInvoiceSync(id={self.id}, sdi={self.identificativo_sdi}, file={self.nome_file})>"

