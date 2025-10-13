from sqlalchemy import Integer, Column, String, Boolean
from src.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id_platform = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    is_default = Column(Boolean, default=False, nullable=False)

