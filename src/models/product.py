from sqlalchemy import Integer, Column, String, ForeignKey, Float
from sqlalchemy.orm import relationship

from src import Base


class Product(Base):
    """
        Modello SQLAlchemy per una tabella 'products'.

        Definisce la struttura della tabella 'products' nel database, consentendo operazioni ORM
        per la gestione dei prodotti. Ogni attributo della classe rappresenta una colonna nella tabella
        del database, con vincoli e tipi di dati specifici per ogni colonna.

        Attributes:
            __tablename__ (str): Il nome della tabella nel database, definito come 'products'.
            id_product (Column): L'ID primario del prodotto, autoincrementale e usato come chiave primaria.
            id_supplier (Column): L'ID del fornitore che ha prodotto il prodotto, usato come chiave esterna.
            id_manufacturer (Column): L'ID del produttore che ha prodotto il prodotto, usato come chiave esterna.
            id_category_default (Column): L'ID della categoria predefinita del prodotto, usato come chiave esterna.
    """
    __tablename__ = "products"

    id_product = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0, index=True)
    id_category = Column(Integer, ForeignKey('categories.id_category'), index=True, default=None)
    id_brand = Column(Integer, ForeignKey('brands.id_brand'), index=True, default=None)
    img_url = Column(String(500), default=None)
    name = Column(String(128))
    sku = Column(String(32))
    reference = Column(String(64), default='ND')
    type = Column(String(32), default='', index=True)
    weight = Column(Float, default=0.0)
    depth = Column(Float, default=0.0)
    height = Column(Float, default=0.0)
    width = Column(Float, default=0.0)

    brand = relationship("Brand", back_populates="products")
    category = relationship("Category", back_populates="products")
