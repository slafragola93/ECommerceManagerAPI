from typing import Optional

from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class CustomerSchema(BaseModel):
    """
        Schema di validazione per un cliente.

        Questo schema Pydantic è utilizzato per validare i dati di input relativi a un cliente
        all'interno di un'applicazione FastAPI. Assicura che tutti i dati necessari siano presenti
        e corretti prima di procedere con le operazioni di database o di logica di business.

        Attributes:
            id_origin (Optional[int]): Identificativo esterno opzionale del cliente. Può essere utilizzato
                                       per mantenere un collegamento con record cliente in sistemi esterni.
            id_lang (int): Identificativo della lingua preferita del cliente. Deve essere un numero positivo.
            firstname (str): Nome del cliente. Deve avere una lunghezza minima di 1 carattere e una massima di 100.
            lastname (str): Cognome del cliente. Come per il nome, deve avere una lunghezza minima di 1 carattere
                            e una massima di 100.
            email (EmailStr): Indirizzo email del cliente. Viene automaticamente validato per assicurarsi che rispetti
                              il formato standard degli indirizzi email.
    """
    id_origin: Optional[int] = None
    id_lang: int = Field(..., gt=0)
    firstname: str = Field(..., min_length=1, max_length=100)
    lastname: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class CustomerResponseSchema(BaseModel):
    id_customer: int
    id_origin: int
    id_lang: int
    firstname: str
    lastname: str
    email: str
    date_add: datetime


class AllCustomerResponseSchema(BaseModel):
    customers: list[CustomerResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
