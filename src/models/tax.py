from sqlalchemy import Integer, Column, String
from src.database import Base


class Tax(Base):
    __tablename__ = "taxes"

    id_tax = Column(Integer, primary_key=True, index=True)
    id_country = Column(Integer, index=True)
    is_default = Column(Integer, default=0)
    name = Column(String(200))
    note = Column(String(200), default="")
    code = Column(String(10))
    percentage = Column(Integer, default=0)
    electronic_code = Column(String(10), default="")
