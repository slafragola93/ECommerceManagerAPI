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
    product_qty = Column(Numeric(10, 5), nullable=False)
    
    # Importo da stornare (può essere diverso dal prezzo originale)
    unit_price_net = Column(Numeric(10, 5))  # Prezzo unitario senza IVA (rinominato da unit_price)
    unit_price_with_tax = Column(Numeric(10, 5), nullable=False)  # Prezzo unitario con IVA (obbligatorio)
    total_price_net = Column(Numeric(10, 5), nullable=False)  # Totale senza IVA (obbligatorio)
    total_price_with_tax = Column(Numeric(10, 5), nullable=False)  # Totale con IVA (obbligatorio)
    
    # Tassa applicata (riferimento all'order detail originale)
    id_tax = Column(Integer, ForeignKey("taxes.id_tax"), nullable=True, index=True)
    
    # Backward compatibility: unit_price come alias per unit_price_net
    @property
    def unit_price(self):
        return self.unit_price_net
    
    @unit_price.setter
    def unit_price(self, value):
        self.unit_price_net = value
    
    # Relationships
    fiscal_document = relationship("FiscalDocument", back_populates="details")
    order_detail = relationship("OrderDetail")
    tax = relationship("Tax")
