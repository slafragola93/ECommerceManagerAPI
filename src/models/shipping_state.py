from ..database import Base
from sqlalchemy import Column, Integer, String


class ShippingState(Base):
    """
        Modello SQLAlchemy per una tabella 'shipping_state'.

        Questa classe definisce la struttura della tabella 'shipping_state' nel database, permettendo
        la gestione degli stati di spedizione tramite operazioni ORM. Ogni stato di spedizione è identificato
        da un ID univoco e ha un nome associato.

        Attributes:
            __tablename__ (str): Il nome della tabella nel database, definito come 'shipping_state'.
            id_shipping_state (Column): L'ID primario dello stato di spedizione, autoincrementale e usato
                                        come chiave primaria. Garantisce l'unicità per ogni stato di spedizione.
            name (Column): Il nome dello stato di spedizione, che descrive il particolare stato in cui si trova
                           una spedizione (ad esempio, "In preparazione", "Spedito", "Consegnato", ecc.).
                           La lunghezza massima del nome è di 100 caratteri.
    """
    __tablename__ = "shipping_state"

    id_shipping_state = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))