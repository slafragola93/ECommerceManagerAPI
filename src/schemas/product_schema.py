from typing import Optional
import re

from pydantic import BaseModel, Field, computed_field

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
    id_category: int = Field(..., ge=0)
    id_brand: int = Field(..., ge=0)
    img_url: Optional[str] = Field(default=None, max_length=500)
    name: str = Field(..., max_length=128)
    sku: str = Field(..., max_length=32)
    reference: str = Field(default='ND', max_length=64)
    type: str = Field(default='', max_length=32)
    weight: float = Field(default=0.0, ge=0)
    depth: float = Field(default=0.0, ge=0)
    height: float = Field(default=0.0, ge=0)
    width: float = Field(default=0.0, ge=0)
    
    @computed_field
    @property
    def img_api_url(self) -> Optional[str]:
        """Genera automaticamente l'API URL per l'immagine se img_url è presente"""
        if not self.img_url:
            return None
        
        # Estrai platform_id e filename da img_url
        match = re.match(r'/media/product_images/(\d+)/(.+)', self.img_url)
        if match:
            platform_id, filename = match.groups()
            return f"/api/v1/images/product/{platform_id}/{filename}"
        
        return None

class ProductResponseSchema(BaseModel):
    id_product: int
    id_origin: int
    img_url: str | None
    name: str
    sku: str
    reference: str
    type: str
    weight: float
    
    @computed_field
    @property
    def img_api_url(self) -> Optional[str]:
        """Genera automaticamente l'API URL per l'immagine se img_url è presente"""
        if not self.img_url:
            return None
        
        # Estrai platform_id e filename da img_url
        match = re.match(r'/media/product_images/(\d+)/(.+)', self.img_url)
        if match:
            platform_id, filename = match.groups()
            return f"/api/v1/images/product/{platform_id}/{filename}"
        
        return None
    depth: float
    height: float
    width: float
    category: CategoryResponseSchema | None
    brand: BrandResponseSchema | None


class ProductUpdateSchema(BaseModel):
    """
    Schema Pydantic per l'aggiornamento dei dati dei prodotti.
    
    Tutti i campi sono opzionali per permettere aggiornamenti parziali.
    """
    id_origin: Optional[int] = None
    id_category: Optional[int] = Field(None, ge=0)
    id_brand: Optional[int] = Field(None, ge=0)
    img_url: Optional[str] = Field(None, max_length=500)
    name: Optional[str] = Field(None, max_length=128)
    sku: Optional[str] = Field(None, max_length=32)
    reference: Optional[str] = Field(None, max_length=64)
    type: Optional[str] = Field(None, max_length=32)
    weight: Optional[float] = Field(None, ge=0)
    depth: Optional[float] = Field(None, ge=0)
    height: Optional[float] = Field(None, ge=0)
    width: Optional[float] = Field(None, ge=0)




class AllProductsResponseSchema(BaseModel):
    products: list[ProductResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
