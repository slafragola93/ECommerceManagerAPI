from sqlalchemy import Integer, Column, String, Boolean
from sqlalchemy.orm import relationship
from src.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id_platform = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    state_triggers = relationship("PlatformStateTrigger", back_populates="platform", cascade="all, delete-orphan")
    stores = relationship("Store", back_populates="platform", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="platform")

