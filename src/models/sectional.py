from sqlalchemy import Integer, Column, String

from src import Base


class Sectional(Base):
    __tablename__ = "sectionals"

    id_sectional = Column(Integer, primary_key=True, index=True)
    name = Column(String(128))
