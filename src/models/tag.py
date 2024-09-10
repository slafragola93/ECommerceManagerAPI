from sqlalchemy import Integer, Column, String
from sqlalchemy.orm import relationship

from src.database import Base
from .relations.relations import product_tags


class Tag(Base):
    __tablename__ = "tags"

    id_tag = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, index=True)
    name = Column(String(200))

    products = relationship("Product", secondary="product_tags", back_populates='tags')
