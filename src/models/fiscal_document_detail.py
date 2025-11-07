from sqlalchemy import Integer, Column, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class FiscalDocumentDetail(Base):
    """
    Dettagli articoli per documenti fiscali (usato principalmente per note di credito parziali)
    """
    __tablename__ = "fiscal_document_details"

    id_fiscal_document_detail = Column(Integer, primary_key=True, index=True)
    
    # Relazione con documento fiscale
    id_fiscal_document = Column(Integer, ForeignKey("fiscal_documents.id_fiscal_document"), nullable=False, index=True)
    
    # Relazione con order detail originale
    id_order_detail = Column(Integer, ForeignKey("order_details.id_order_detail"), nullable=False, index=True)
    
    # Quantità da stornare (può essere minore della quantità originale)
    quantity = Column(Numeric(10, 5), nullable=False)
    
    # Importo da stornare (può essere diverso dal prezzo originale)
    unit_price = Column(Numeric(10, 5), nullable=False)
    total_amount = Column(Numeric(10, 5), nullable=False)
    
    # Tassa applicata (riferimento all'order detail originale)
    id_tax = Column(Integer, ForeignKey("taxes.id_tax"), nullable=True, index=True)
    
    # Relationships
    fiscal_document = relationship("FiscalDocument", back_populates="details")
    order_detail = relationship("OrderDetail")
    tax = relationship("Tax")
