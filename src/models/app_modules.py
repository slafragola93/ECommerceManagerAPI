from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from ..database import Base


class AppModule(Base):
    __tablename__ = 'app_modules'

    id_module  = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), unique=True, nullable=False)
    label      = Column(String(100), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)

    # Relazione
    user_permissions = relationship(
        'UserModulePermission',
        back_populates='module'
    )