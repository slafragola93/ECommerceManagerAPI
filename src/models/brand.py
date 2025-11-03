from sqlalchemy import Integer, Column, String, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class Brand(Base):
    """
        Modello SQLAlchemy per una tabella 'brands'.

        Questa classe definisce la struttura della tabella 'brands' utilizzando SQLAlchemy.
        Ogni istanza della classe rappresenta una riga nella tabella del database.

        Attributes:
            __tablename__ (str): Nome della tabella nel database.
            id_brand (Column): Colonna dell'ID del marchio, chiave primaria della tabella.
            id_origin (Column): Colonna dell'ID d'origine del marchio, con un valore di default impostato a 0.
                                Questo può essere utilizzato per mantenere un riferimento a record in altri sistemi o database.
            name (Column): Colonna del nome del marchio, che può contenere fino a 200 caratteri.
    """
    __tablename__ = "brands"

    id_brand = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=None)
    id_platform = Column(Integer, ForeignKey('platforms.id_platform'), default=0, nullable=False, index=True)
    name = Column(String(200))

    products = relationship("Product", back_populates="brand")
