from sqlalchemy import Integer, Column, String, Float
from src.database import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id_carrier = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0, index=True)
    name = Column(String(200))