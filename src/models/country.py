from sqlalchemy import Integer, Column, String
from src.database import Base


class Country(Base):
    __tablename__ = "countries"

    id_country = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    iso_code = Column(String(5))
