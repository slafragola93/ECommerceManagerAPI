from sqlalchemy import Integer, Column, String

from src.database import Base


class Category(Base):
    """
        Modello SQLAlchemy per una tabella 'categories'.

        Definisce la struttura della tabella 'categories' nel database, utilizzando SQLAlchemy.
        Ogni istanza di questa classe rappresenta una riga nella tabella 'categories', consentendo
        operazioni ORM per la gestione delle categorie.

        Attributes:
            __tablename__ (str): Nome della tabella nel database, impostato su 'categories'.
            id_category (Column): Colonna per l'ID della categoria, usata come chiave primaria.
                                  Autoincrementale e indicizzata per migliorare le prestazioni delle query.
            id_origin (Column): Colonna opzionale per un ID esterno o d'origine. Può essere usata per
                                mantenere i riferimenti a sistemi o database esterni. Il valore di default è 0.
            name (Column): Colonna per il nome della categoria, con una lunghezza massima di 200 caratteri.
                           Questo campo è obbligatorio e viene utilizzato per descrivere la categoria.
    """
    __tablename__ = "categories"

    id_category = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0)
    name = Column(String(200))