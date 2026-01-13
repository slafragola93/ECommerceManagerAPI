from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class StoreSchema(BaseModel):
    id_platform: int = Field(..., description="ID della piattaforma")
    name: str = Field(..., max_length=200, description="Nome dello store")
    base_url: str = Field(..., max_length=500, description="URL base dell'ecommerce")
    api_key: str = Field(..., max_length=500, description="Chiave API dell'ecommerce")
    logo: Optional[str] = Field(None, max_length=500, description="URL o percorso del logo dello store")
    is_active: bool = Field(True, description="Store attivo")
    is_default: bool = Field(False, description="Store di default")


class StoreCreateSchema(BaseModel):
    id_platform: int = Field(..., description="ID della piattaforma")
    name: str = Field(..., max_length=200, description="Nome dello store")
    base_url: str = Field(..., max_length=500, description="URL base dell'ecommerce")
    api_key: str = Field(..., max_length=500, description="Chiave API dell'ecommerce")
    logo: Optional[str] = Field(None, max_length=500, description="URL o percorso del logo dello store")
    is_active: bool = Field(True, description="Store attivo")
    is_default: bool = Field(False, description="Store di default")


class StoreUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=200, description="Nome dello store")
    base_url: Optional[str] = Field(None, max_length=500, description="URL base dell'ecommerce")
    api_key: Optional[str] = Field(None, max_length=500, description="Chiave API dell'ecommerce")
    logo: Optional[str] = Field(None, max_length=500, description="URL o percorso del logo dello store")
    is_active: Optional[bool] = Field(None, description="Store attivo")
    is_default: Optional[bool] = Field(None, description="Store di default")


class StoreResponseSchema(BaseModel):
    id_store: int
    id_platform: int
    name: str
    base_url: str
    api_key: str
    logo: Optional[str]
    is_active: bool
    is_default: bool
    date_add: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AllStoresResponseSchema(BaseModel):
    stores: list[StoreResponseSchema]
    total: int
    page: int
    limit: int

