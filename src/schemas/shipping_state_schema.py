from pydantic import BaseModel, Field


class ShippingStateSchema(BaseModel):
    """
    Schema per la validazione dello stato di spedizione.

    Definisce e valida i dati relativi agli stati di spedizione utilizzati nell'applicazione,
    garantendo che il nome dello stato di spedizione sia presente e rispetti i limiti di lunghezza definiti.

    Attributes:
        name (str): Nome dello stato di spedizione. È un campo obbligatorio che deve avere una lunghezza
                    minima di 1 carattere e massima di 100 caratteri. Questo assicura che lo stato di
                    spedizione sia descritto in modo adeguato e comprensibile.
    """
    name: str = Field(..., min_length=1, max_length=100)
