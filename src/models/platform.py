from sqlalchemy import Integer, Column, String
from src.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id_platform = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    url = Column(String(200))
    api_key = Column(String(200))

