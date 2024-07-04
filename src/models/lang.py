from sqlalchemy import Integer, Column, String
from src.database import Base


class Lang(Base):

    __tablename__ = "languages"

    id_lang = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    iso_code = Column(String(10))
