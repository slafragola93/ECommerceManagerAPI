from sqlalchemy import Integer, Column, String
from src.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id_tag = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
