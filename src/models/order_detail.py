from sqlalchemy import Integer, Column, String, Numeric, ForeignKey
from src.database import Base


class OrderDetail(Base):
    __tablename__ = "order_details"

    id_order_detail = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, index=True, default=0)
    id_order = Column(Integer, index=True, default=None)
    id_order_document = Column(Integer, index=True, default=None)
    id_product = Column(Integer, index=True, default=None)
    id_tax = Column(Integer, index=True, default=None)
    product_name = Column(String(100))
    product_reference = Column(String(100))
    product_qty = Column(Integer)
    product_weight = Column(Numeric(10, 5))
    unit_price_net = Column(Numeric(10, 5))  # Prezzo unitario senza IVA (rinominato da product_price)
    unit_price_with_tax = Column(Numeric(10, 5), nullable=False)  # Prezzo unitario con IVA (obbligatorio)
    total_price_net = Column(Numeric(10, 5), nullable=False)  # Totale senza IVA (obbligatorio)
    total_price_with_tax = Column(Numeric(10, 5), nullable=False)  # Totale con IVA (obbligatorio)
    reduction_percent = Column(Numeric(10, 5), default=0.0)
    reduction_amount = Column(Numeric(10, 5), default=0.0)
    rda = Column(String(10))
    note = Column(String(200))
    
    # Backward compatibility: product_price come alias per unit_price_net
    @property
    def product_price(self):
        return self.unit_price_net
    
    @product_price.setter
    def product_price(self, value):
        self.unit_price_net = value


    