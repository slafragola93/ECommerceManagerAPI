from typing import Optional
from pydantic import BaseModel, Field


class BrandSchema(BaseModel):
    """
        Schema per la definizione di un marchio (Brand).

        Questo schema utilizza Pydantic per la validazione dei dati in input.
        È definito per rappresentare e validare i dati relativi a un marchio all'interno
        di un'applicazione FastAPI.

        Attributes:
        - id_origin (Optional[int]): Un identificativo opzionale d'origine per il marchio.
        - name (str): Il nome del marchio, obbligatorio e con una lunghezza massima di 200 caratteri.
    """
    id_origin: Optional[int] = 0
    name: str = Field(..., max_length=200)


class BrandResponseSchema(BaseModel):
    id_brand: int
    id_origin: int
    name: str


class AllBrandsResponseSchema(BaseModel):
    brands: list[BrandResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
