from sqlalchemy import Integer, Column, String, Float
from src.database import Base


class OrderDetail(Base):
    __tablename__ = "order_details"

    id_order_detail = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, index=True)
    id_invoice = Column(Integer, index=True)
    id_order_document = Column(Integer, index=True)
    id_origin = Column(Integer, index=True)
    id_product = Column(Integer, index=True)
    id_tax = Column(Integer, index=True)
    product_name = Column(String(100))
    product_reference = Column(String(100))
    product_qty = Column(Integer)
    product_weight = Column(Float)
    product_price = Column(Float)
    reduction_percent = Column(Float)
    reduction_amount = Column(Float)
    rda = Column(String(10))


