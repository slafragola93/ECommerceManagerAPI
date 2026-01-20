"""
Schema per i dati di inizializzazione del frontend
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from .platform_schema import PlatformResponseSchema
from .lang_schema import LangResponseSchema
from .country_schema import CountryResponseSchema
from .tax_schema import TaxResponseSchema
from .sectional_schema import SectionalResponseSchema
from .order_state_schema import OrderStateResponseSchema
from .shipping_state_schema import ShippingStateResponseSchema


class PaymentInitSchema(BaseModel):
    """Schema per i metodi di pagamento nei dati di inizializzazione"""
    id_payment: int = Field(..., description="ID del metodo di pagamento")
    name: str = Field(..., description="Nome del metodo di pagamento")


class ApiCarrierInitSchema(BaseModel):
    """Schema per gli API carrier nei dati di inizializzazione"""
    id_carrier_api: int = Field(..., description="ID dell'API carrier")
    name: str = Field(..., description="Nome dell'API carrier")
    logo: Optional[str] = Field(None, description="URL o percorso del logo del corriere")


class StoreInitSchema(BaseModel):
    """Schema per gli store nei dati di inizializzazione"""
    id_store: int = Field(..., description="ID dello store")
    name: str = Field(..., description="Nome dello store")
    logo: Optional[str] = Field(None, description="URL o percorso del logo dello store")


class EcommerceOrderStateInitSchema(BaseModel):
    """Schema per gli stati e-commerce nei dati di inizializzazione"""
    id_platform_state: int = Field(..., description="ID dello stato sulla piattaforma remota")
    id_store: int = Field(..., description="ID dello store associato")
    name: str = Field(..., description="Nome dello stato")


class InitDataSchema(BaseModel):
    """
    Schema per i dati di inizializzazione del frontend
    """
    #TODO: idratare risposte schema per evitare di ritornare l'intera entità
    # Dati statici (cache settimanale)
    platforms: List[PlatformResponseSchema] = Field(..., description="Lista delle piattaforme disponibili")
    languages: List[LangResponseSchema] = Field(..., description="Lista delle lingue supportate")
    countries: List[CountryResponseSchema] = Field(..., description="Lista dei paesi")
    taxes: List[TaxResponseSchema] = Field(..., description="Lista delle tasse")
    payments: List[PaymentInitSchema] = Field(..., description="Lista dei metodi di pagamento")
    carriers: List[ApiCarrierInitSchema] = Field(..., description="Lista degli API carrier attivi")
    stores: List[StoreInitSchema] = Field(..., description="Lista degli store disponibili")
    
    # Dati dinamici (cache giornaliera)
    sectionals: List[SectionalResponseSchema] = Field(..., description="Lista delle sezioni/aree geografiche")
    order_states: List[OrderStateResponseSchema] = Field(..., description="Lista degli stati degli ordini")
    shipping_states: List[ShippingStateResponseSchema] = Field(..., description="Lista degli stati di spedizione")
    ecommerce_order_states: List[EcommerceOrderStateInitSchema] = Field(default_factory=list, description="Lista degli stati ordini e-commerce sincronizzati")
    
    # Metadati cache
    cache_info: 'CacheInfoSchema' = Field(..., description="Informazioni sulla cache")


class CacheInfoSchema(BaseModel):
    """
    Schema per le informazioni sulla cache
    """
    generated_at: datetime = Field(..., description="Timestamp di generazione")
    ttl_static: int = Field(..., description="TTL per dati statici (secondi)")
    ttl_dynamic: int = Field(..., description="TTL per dati dinamici (secondi)")
    version: str = Field(..., description="Versione dei dati")
    total_items: int = Field(..., description="Numero totale di elementi")


# Aggiorna i forward references
InitDataSchema.model_rebuild()
