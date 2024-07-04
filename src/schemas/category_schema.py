from typing import Optional
from pydantic import BaseModel, Field


class CategorySchema(BaseModel):
    """
        Schema per la definizione di una categoria.

        Utilizza Pydantic per la validazione dei dati in ingresso, garantendo che i dati
        inviati alle API soddisfino i criteri specificati. Questo schema viene utilizzato
        principalmente nelle operazioni CRUD legate alle categorie all'interno di un'applicazione FastAPI.

        Attributes:
            id_origin (Optional[int]): Un identificativo opzionale esterno per la categoria. Utile
                                       per mantenere riferimenti a sistemi esterni o a basi di dati differenti.
            name (str): Il nome della categoria, un campo obbligatorio che non può essere vuoto e
                        deve avere una lunghezza massima di 200 caratteri.
    """
    id_origin: Optional[int] = None
    name: str = Field(..., max_length=200)


class CategoryResponseSchema(BaseModel):
    id_category: int
    id_origin: int
    name: str


class AllCategoryResponseSchema(BaseModel):
    categories: list[CategoryResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
