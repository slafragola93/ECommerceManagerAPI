from sqlalchemy import Integer, Column, ForeignKey, String

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
    id_category = Column(Integer, index=True)
    id_brand = Column(Integer, index=True)
    name = Column(String(128))
    sku = Column(String(32))
    type = Column(String(32), default='', index=True)
