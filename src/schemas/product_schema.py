from typing import Optional

from pydantic import BaseModel, Field, validator

from .category_schema import CategoryResponseSchema
from .brand_schema import BrandResponseSchema


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
        reference (str): Riferimento del prodotto.
        type (str): Tipo di prodotto, utilizzato per categorizzare ulteriormente i prodotti all'interno
                    della stessa categoria.
        weight (float): Peso del prodotto.
        depth (float): Profondità del prodotto.
        height (float): Altezza del prodotto.
        width (float): Larghezza del prodotto.
        img_url (str): URL dell'immagine del prodotto.
    """
    id_origin: Optional[int] = 0
    id_category: Optional[int] = Field(0, ge=0)
    id_brand: Optional[int] = Field(0, ge=0)
    id_store: Optional[int] = Field(default=None)
    img_url: Optional[str] = Field(default=None, max_length=500)
    name: str = Field(..., max_length=128)
    sku: str = Field(..., max_length=32)
    reference: str = Field(default='ND', max_length=64)
    type: str = Field(default='', max_length=32)
    weight: float = Field(default=0.0, ge=0)
    depth: float = Field(default=0.0, ge=0)
    height: float = Field(default=0.0, ge=0)
    width: float = Field(default=0.0, ge=0)
    price: Optional[float] = Field(default=0.0, ge=0)  # Prezzo con IVA (rinominato da price_without_tax)
    quantity: Optional[int] = Field(default=0, ge=0)
    purchase_price: Optional[float] = Field(default=0.0, ge=0)
    minimal_quantity: Optional[int] = Field(default=0, ge=0)
    
    model_config = {"from_attributes": True}
    

class ProductResponseSchema(BaseModel):
    id_product: int
    id_origin: int
    id_store: Optional[int]
    img_url: str | None
    name: str
    sku: str
    reference: str
    type: str
    weight: float
    depth: float
    height: float
    width: float
    price_with_tax: float | None  # Prezzo con IVA (product.price)
    price_net: Optional[float]  # Prezzo senza IVA (calcolato)
    id_tax: Optional[int]  # ID della tassa basata su id_country
    quantity: int | None
    purchase_price: float | None
    minimal_quantity: int | None
    category: CategoryResponseSchema | None
    brand: BrandResponseSchema | None
    
    @validator('weight', 'depth', 'height', 'width', 'price_with_tax', 'price_net', 'purchase_price', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)
    
    model_config = {"from_attributes": True}


class ProductUpdateSchema(BaseModel):
    """
    Schema Pydantic per l'aggiornamento dei dati dei prodotti.
    
    Tutti i campi sono opzionali per permettere aggiornamenti parziali.
    """
    id_origin: Optional[int] = None
    id_category: Optional[int] = Field(None, ge=0)
    id_brand: Optional[int] = Field(None, ge=0)
    id_store: Optional[int] = Field(None)
    img_url: Optional[str] = Field(None, max_length=500)
    name: Optional[str] = Field(None, max_length=128)
    sku: Optional[str] = Field(None, max_length=32)
    reference: Optional[str] = Field(None, max_length=64)
    type: Optional[str] = Field(None, max_length=32)
    weight: Optional[float] = Field(None, ge=0)
    depth: Optional[float] = Field(None, ge=0)
    height: Optional[float] = Field(None, ge=0)
    width: Optional[float] = Field(None, ge=0)
    price: Optional[float] = Field(None, ge=0)  # Prezzo con IVA (rinominato da price_without_tax)
    quantity: Optional[int] = Field(None, ge=0)
    purchase_price: Optional[float] = Field(None, ge=0)
    minimal_quantity: Optional[int] = Field(None, ge=0)
    
    model_config = {"from_attributes": True}




class AllProductsResponseSchema(BaseModel):
    products: list[ProductResponseSchema]
    total: int
    page: int
    limit: int
    
    model_config = {"from_attributes": True}
