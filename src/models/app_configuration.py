from sqlalchemy import Integer, Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship

from src.database import Base


class AppConfiguration(Base):
    """
    Modello SQLAlchemy per la tabella 'app_configurations'.

    Definisce la struttura della tabella per le configurazioni dell'applicazione,
    organizzate per categorie per una migliore gestione e organizzazione.

    Attributes:
        __tablename__ (str): Il nome della tabella nel database, definito come 'app_configurations'.
        id_app_configuration (Column): L'ID primario della configurazione, autoincrementale.
        id_lang (Column): Identificativo della lingua per supporto multilingua.
        category (Column): Categoria della configurazione (company_info, electronic_invoicing, etc.).
        name (Column): Nome della configurazione (chiave).
        value (Column): Valore della configurazione.
        description (Column): Descrizione opzionale della configurazione.
        is_encrypted (Column): Flag per indicare se il valore è criptato.
        date_add (Column): Data di creazione del record.
        date_upd (Column): Data di ultimo aggiornamento del record.
    """
    __tablename__ = "app_configurations"

    id_app_configuration = Column(Integer, primary_key=True, index=True)
    id_lang = Column(Integer, default=0)
    category = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    value = Column(String(1000), default=None)
    description = Column(String(255), default=None)
    is_encrypted = Column(Boolean, default=False)
    date_add = Column(DateTime, default=func.now())
    date_upd = Column(DateTime, default=func.now(), onupdate=func.now())
