from sqlalchemy import Integer, Column, String

from src.database import Base


class Configuration(Base):

    __tablename__ = "configurations"

    id_configuration = Column(Integer, primary_key=True, index=True)
    id_lang = Column(Integer, default=0)
    name = Column(String(50))
    value = Column(String(50))