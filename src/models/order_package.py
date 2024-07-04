from sqlalchemy import Integer, Column, Float
from src import Base


class OrderPackage(Base):
    __tablename__ = "order_packages"

    id_order_package = Column(Integer, primary_key=True, index=True)
    id_order = Column(Integer, index=True, nullable=True)
    height = Column(Float)
    width = Column(Float)
    depth = Column(Float)
    weight = Column(Float)
    value = Column(Float, default=0.0)

