from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, DateTime, func

from ..database import Base


class Customer(Base):
    """
        Modello SQLAlchemy per una tabella 'customers'.

        Definisce la struttura della tabella 'customers' nel database, consentendo operazioni ORM
        per la gestione dei clienti. Ogni attributo della classe rappresenta una colonna nella tabella
        del database, con vincoli e tipi di dati specifici per ogni colonna.

        Attributes:
            __tablename__ (str): Il nome della tabella nel database, definito come 'customers'.
            id_customer (Column): L'ID primario del cliente, autoincrementale e usato come chiave primaria.
            id_origin (Column): Un ID opzionale che può essere usato per mantenere riferimenti a record di cliente
                                in altri sistemi o database. Di default è impostato a 0.
            id_lang (Column): Un identificativo che rappresenta la lingua preferita del cliente. Può essere utilizzato
                              per personalizzare l'interfaccia utente o i messaggi inviati al cliente.
            firstname (Column): Il nome del cliente, con una lunghezza massima di 100 caratteri.
            lastname (Column): Il cognome del cliente, anch'esso con una lunghezza massima di 100 caratteri.
            email (Column): L'indirizzo email del cliente, unico per ogni record per evitare duplicati.
                            La lunghezza massima è di 150 caratteri.
            date_add (Column): La data e ora di registrazione del cliente nel sistema, utile per tenere traccia
                               del momento esatto della loro aggiunta.
    """
    __tablename__ = "customers"

    id_customer = Column(Integer, primary_key=True, index=True)
    id_origin = Column(Integer, default=0)
    id_lang = Column(Integer)
    firstname = Column(String(100))
    lastname = Column(String(100))
    email = Column(String(150), index=True)
    date_add = Column(DateTime, default=func.now())

    addresses = relationship("Address", back_populates="customer")
    orders_document = relationship("OrderDocument", back_populates="customer")
