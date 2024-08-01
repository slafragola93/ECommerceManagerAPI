from typing import Optional

from pydantic import BaseModel, Field

from .category_schema import CategoryResponseSchema
from .brand_schema import BrandResponseSchema
from .tag_schema import TagResponseSchema


class ProductSchema(BaseModel):
    """
    Schema Pydantic per la validazione dei dati dei prodotti.

    Questo schema definisce le aspettative per i dati dei prodotti che vengono inviati alle API,
    basandosi sulla struttura del modello SQLAlchemy `Product`.

    Attributes:
        id_origin (int): Identificativo opzionale esterno del prodotto. Utilizzato per mantenere riferimenti
                         a sistemi o database esterni.
        id_category (int): L'ID della categoria a cui appartiene il prodotto. Corrisponde a una chiave esterna
                           nel modello di database.
        id_brand (int): L'ID del marchio del prodotto. Anche questo è una chiave esterna che fa riferimento
                        alla tabella dei marchi.
        name (str): Il nome del prodotto, un campo obbligatorio.
        sku (str): Stock Keeping Unit, un identificatore unico per il prodotto.
        type (str): Tipo di prodotto, utilizzato per categorizzare ulteriormente i prodotti all'interno
                    della stessa categoria.
    """
    id_origin: Optional[int] = 0
    id_category: int = Field(..., gt=0)
    id_brand: int = Field(..., gt=0)
    name: str = Field(..., max_length=128)
    sku: str = Field(..., max_length=32)
    type: str = Field(default='', max_length=32)


class ProductResponseSchema(BaseModel):
    id_product: int
    id_origin: int
    name: str
    sku: str
    type: str
    category: CategoryResponseSchema
    brand: BrandResponseSchema
    tags: list[TagResponseSchema] = []


class AssociateTagToProductSchema(BaseModel):
    id_product: int = Field(..., gt=0)
    id_tag: int = Field(..., gt=0)


class AllProductsResponseSchema(BaseModel):
    products: list[ProductResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
