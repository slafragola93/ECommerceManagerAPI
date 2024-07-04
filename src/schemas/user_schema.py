from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, EmailStr

from .role_schema import RoleResponseSchema


class UserSchema(BaseModel):
    """
        Schema di validazione per un utente.

        Questo schema utilizza Pydantic per assicurare che i dati forniti per un utente
        siano validi e conformi alle specifiche richieste dall'applicazione. Include controlli
        sulla lunghezza e sul formato di username, nome, cognome, password ed email.

        Attributes:
            username (str): Il nome utente, che deve essere univoco. Deve contenere tra 4 e 15 caratteri
                            alfanumerici (lettere e numeri).
            firstname (str): Il nome dell'utente, con una lunghezza minima di 1 e massima di 100 caratteri.
            lastname (str): Il cognome dell'utente, anch'esso con limiti di lunghezza simili al nome.
            password (str): La password dell'utente, che deve avere una lunghezza minima di 8 caratteri e
                            una massima di 15 caratteri.
            email (EmailStr): L'indirizzo email dell'utente, che deve seguire il formato standard degli indirizzi email.
    """
    username: str = Field(..., min_length=4, max_length=15, pattern="^[a-zA-Z0-9]+$")
    firstname: str = Field(..., min_length=1, max_length=100)
    lastname: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=15)
    email: EmailStr
    roles: Optional[List[RoleResponseSchema]] = []


class UserResponseSchema(BaseModel):
    id_user: int
    username: str
    firstname: str
    lastname: str
    email: EmailStr
    roles: Optional[List[RoleResponseSchema]] = []


class AllUsersResponseSchema(BaseModel):
    users: list[UserResponseSchema]
    total: int
    page: int
    limit: int


class Token(BaseModel):
    """
        Schema per i token di autenticazione.

        Questo modello definisce la struttura dei token di accesso restituiti agli utenti
        quando si autenticano. Include il token vero e proprio e il suo tipo (di solito "bearer").

        Attributes:
            access_token (str): Il token di accesso JWT generato.
            token_type (str): Il tipo di token, generalmente "bearer".
    """
    access_token: str
    token_type: str
    current_user: str
    expires_at: datetime


class ChangePasswordSchema(BaseModel):
    """
        Schema per la richiesta di cambio password.

        Utilizzato quando un utente desidera cambiare la propria password, assicurando
        che la nuova password sia valida e rispetti le specifiche di lunghezza.

        Attributes:
            old_password (str): La vecchia password dell'utente, utilizzata per verificare la sua identità.
            new_password (str): La nuova password che l'utente desidera impostare, che deve avere una lunghezza
                                minima di 6 caratteri e massima di 20 caratteri.
    """
    old_password: str
    new_password: str = Field(min_length=6, max_length=20)
