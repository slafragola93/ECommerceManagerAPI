from datetime import datetime

from sqlalchemy.orm import relationship

from ..database import Base
from sqlalchemy import Column, Integer, String, Boolean, Date, Table, ForeignKey

user_roles = Table('user_roles', Base.metadata,
                   Column('id_user', Integer, ForeignKey('users.id_user')),
                   Column('id_role', Integer, ForeignKey('roles.id_role'))
                   )


class User(Base):
    """
        Modello SQLAlchemy per una tabella 'users'.

        Questa classe rappresenta la struttura della tabella 'users' nel database, facilitando
        operazioni ORM per la gestione degli utenti. Include campi per l'identificazione dell'utente,
        credenziali di accesso, stato attivo e data di registrazione.

        Attributes:
            __tablename__ (str): Il nome della tabella nel database, impostato su 'users'.
            id_user (Column): L'ID primario dell'utente, utilizzato come chiave primaria. È autoincrementale
                              per garantire l'unicità.
            username (Column): Il nome utente, unico per ogni utente e indicizzato per migliorare le prestazioni
                               delle query.
            firstname (Column): Il nome dell'utente, senza restrizioni di unicità.
            lastname (Column): Il cognome dell'utente.
            password (Column): La password dell'utente, memorizzata come stringa. Si raccomanda di memorizzare
                               password hashate anziché in chiaro per motivi di sicurezza.
            email (Column): L'indirizzo email dell'utente, che deve essere unico e indicizzato.
            is_active (Column): Un flag booleano che indica se l'account utente è attivo. Utile per abilitare o
                                disabilitare l'accesso senza eliminare il record dell'utente.
            date_add (Column): La data di creazione dell'account utente, con un valore di default che corrisponde
                               alla data e ora corrente al momento della creazione del record.
    """
    __tablename__ = 'users'

    id_user = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True)
    firstname = Column(String(100))
    lastname = Column(String(100))
    password = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    is_active = Column(Boolean, default=True)
    date_add = Column(Date, default=datetime.now)
    roles = relationship('Role', secondary=user_roles, back_populates='users')
