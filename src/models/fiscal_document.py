from sqlalchemy import Integer, Column, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from src.database import Base


class FiscalDocument(Base):
    """
    Modello unificato per documenti fiscali (fatture e note di credito)
    
    - document_type: 'invoice' o 'credit_note'
    - tipo_documento_fe: TD01 (fattura), TD04 (nota credito), ecc.
    - is_electronic: True se emessa elettronicamente (solo per IT)
    """
    __tablename__ = "fiscal_documents"

    id_fiscal_document = Column(Integer, primary_key=True, index=True)
    
    # Tipo documento
    document_type = Column(String(20), nullable=False, index=True)  # 'invoice' o 'credit_note'
    tipo_documento_fe = Column(String(4), nullable=True)  # TD01, TD04, ecc. (null se non elettronico)
    
    # Relazioni
    id_order = Column(Integer, ForeignKey("orders.id_order"), nullable=False, index=True)
    id_fiscal_document_ref = Column(Integer, ForeignKey("fiscal_documents.id_fiscal_document"), nullable=True, index=True)  # Per note di credito -> fattura
    
    # Numerazione
    document_number = Column(String(10), nullable=True, index=True)  # Numero sequenziale elettronico (solo se is_electronic=True)
    internal_number = Column(String(50), nullable=True, index=True)  # Numero interno alternativo
    
    # Dati documento
    filename = Column(String(255), nullable=True)
    xml_content = Column(Text, nullable=True)
    
    # Status
    status = Column(String(50), nullable=False, default="pending")  # pending, generated, uploaded, sent, error
    is_electronic = Column(Boolean, default=False, nullable=False)  # True se FatturaPA elettronica
    upload_result = Column(Text, nullable=True)  # JSON result from upload
    
    # Dati specifici note di credito
    credit_note_reason = Column(Text, nullable=True)  # Motivo nota di credito
    is_partial = Column(Boolean, default=False, nullable=False)  # True se parziale
    
    # Importi (per note parziali)
    total_amount = Column(Float, nullable=True)  # Importo totale documento
    
    # Timestamp
    date_add = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_upd = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="fiscal_documents")
    referenced_document = relationship("FiscalDocument", remote_side=[id_fiscal_document], foreign_keys=[id_fiscal_document_ref])
    credit_notes = relationship("FiscalDocument", back_populates="referenced_document", foreign_keys=[id_fiscal_document_ref])
    details = relationship("FiscalDocumentDetail", back_populates="fiscal_document", cascade="all, delete-orphan")
