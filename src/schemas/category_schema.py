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
            id_platform (int): Identificativo della piattaforma, default 0.
            name (str): Il nome della categoria, un campo obbligatorio che non può essere vuoto e
                        deve avere una lunghezza massima di 200 caratteri.
    """
    id_origin: Optional[int] = None
    id_platform: int = Field(default=0, ge=0)
    name: str = Field(..., max_length=200)
    
    model_config = {"from_attributes": True}


class CategoryResponseSchema(BaseModel):
    id_category: int | None
    id_origin: int | None
    id_store: int | None
    name: str | None
    
    model_config = {"from_attributes": True, "extra": "ignore"}


class AllCategoryResponseSchema(BaseModel):
    categories: list[CategoryResponseSchema]
    total: int
    page: int
    limit: int
    
    model_config = {"from_attributes": True}
