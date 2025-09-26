from sqlalchemy import Integer, Column, String, Float
from src.database import Base


class OrderDetail(Base):
    __tablename__ = "order_details"

    id_order_detail = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, index=True, default=0)
    id_order = Column(Integer, index=True, default=None)
    id_invoice = Column(Integer, index=True, default=None)
    id_order_document = Column(Integer, index=True, default=None)
    id_product = Column(Integer, index=True, default=None)
    id_tax = Column(Integer, index=True, default=None)
    product_name = Column(String(100))
    product_reference = Column(String(100))
    product_qty = Column(Integer)
    product_weight = Column(Float)
    product_price = Column(Float)
    reduction_percent = Column(Float, default=0.0)
    reduction_amount = Column(Float, default=0.0)
    rda = Column(String(10))


    