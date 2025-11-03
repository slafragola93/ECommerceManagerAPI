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
        - id_platform (int): Identificativo della piattaforma, default 0.
        - name (str): Il nome del marchio, obbligatorio e con una lunghezza massima di 200 caratteri.
    """
    id_origin: Optional[int] = 0
    id_platform: int = Field(default=0, ge=0)
    name: str = Field(..., max_length=200)
    
    model_config = {"from_attributes": True}


class BrandResponseSchema(BaseModel):
    id_brand: int | None
    id_origin: int | None
    id_platform: int | None
    name: str | None
    
    model_config = {"from_attributes": True}


class AllBrandsResponseSchema(BaseModel):
    brands: list[BrandResponseSchema]
    total: int
    page: int
    limit: int
    
    model_config = {"from_attributes": True}
