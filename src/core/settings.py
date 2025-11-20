"""
Cache configuration settings for ECommerceManagerAPI
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class CacheSettings(BaseSettings):
    """Cache configuration settings"""
    
    # Cache enablement
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_backend: str = Field(default="hybrid", env="CACHE_BACKEND")  # redis, memory, hybrid
    
    # Redis configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    redis_retry_on_timeout: bool = Field(default=True, env="REDIS_RETRY_ON_TIMEOUT")
    redis_socket_keepalive: bool = Field(default=True, env="REDIS_SOCKET_KEEPALIVE")
    redis_socket_keepalive_options: dict = Field(default={}, env="REDIS_SOCKET_KEEPALIVE_OPTIONS")
    
    # TTL defaults (in seconds)
    cache_default_ttl: int = Field(default=300, env="CACHE_DEFAULT_TTL")  # 5 minutes
    cache_stale_ttl: int = Field(default=900, env="CACHE_STALE_TTL")      # 15 minutes
    cache_short_ttl: int = Field(default=60, env="CACHE_SHORT_TTL")       # 1 minute
    cache_medium_ttl: int = Field(default=3600, env="CACHE_MEDIUM_TTL")   # 1 hour
    cache_long_ttl: int = Field(default=86400, env="CACHE_LONG_TTL")      # 24 hours
    
    # Memory cache configuration
    cache_max_mem_items: int = Field(default=1000, env="CACHE_MAX_MEM_ITEMS")
    cache_max_value_size: int = Field(default=1048576, env="CACHE_MAX_VALUE_SIZE")  # 1MB
    
    # Security
    cache_key_salt: str = Field(default="ecommerce-cache-salt", env="CACHE_KEY_SALT")
    
    # Metrics and logging
    cache_metrics_enabled: bool = Field(default=True, env="CACHE_METRICS_ENABLED")
    cache_log_level: str = Field(default="INFO", env="CACHE_LOG_LEVEL")
    
    # Feature flags
    cache_orders_enabled: bool = Field(default=True, env="CACHE_ORDERS_ENABLED")
    cache_products_enabled: bool = Field(default=True, env="CACHE_PRODUCTS_ENABLED")
    cache_customers_enabled: bool = Field(default=True, env="CACHE_CUSTOMERS_ENABLED")
    cache_external_apis_enabled: bool = Field(default=True, env="CACHE_EXTERNAL_APIS_ENABLED")
    
    # Shipment audit settings
    shipment_audit_enabled: bool = Field(default=False, env="SHIPMENT_AUDIT_ENABLED")
    shipment_audit_ttl_days: int = Field(default=90, env="SHIPMENT_AUDIT_TTL_DAYS")
    shipment_audit_max_json_size_kb: int = Field(default=500, env="SHIPMENT_AUDIT_MAX_JSON_SIZE_KB")
    
    # Circuit breaker
    cache_error_threshold: float = Field(default=0.5, env="CACHE_ERROR_THRESHOLD")
    cache_recovery_timeout: int = Field(default=300, env="CACHE_RECOVERY_TIMEOUT")  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_cache_settings() -> CacheSettings:
    """Get cached cache settings instance"""
    return CacheSettings()


class CarrierIntegrationSettings(BaseSettings):
    """Carrier integration configuration settings"""
    
    # DHL Integration settings
    dhl_base_url_prod: str = Field(default="https://express.api.dhl.com/mydhlapi", env="DHL_BASE_URL_PROD")
    dhl_base_url_sandbox: str = Field(default="https://express.api.dhl.com/mydhlapi/test", env="DHL_BASE_URL_SANDBOX")
    
    # BRT Integration settings
    brt_base_url_prod: str = Field(default="https://api.brt.it", env="BRT_BASE_URL_PROD")
    brt_base_url_sandbox: str = Field(default="https://api.brt.it", env="BRT_BASE_URL_SANDBOX")
    
    # FEDEX Integration settings
    fedex_base_url_prod: str = Field(default="https://apis.fedex.com", env="FEDEX_BASE_URL_PROD")
    fedex_base_url_sandbox: str = Field(default="https://apis-sandbox.fedex.com", env="FEDEX_BASE_URL_SANDBOX")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_carrier_integration_settings() -> CarrierIntegrationSettings:
    """Get cached carrier integration settings instance"""
    return CarrierIntegrationSettings()


# TTL presets for different data types
TTL_PRESETS = {
    # Static lookup tables
    "order_states": 86400,      # 24 hours
    "categories": 86400,        # 24 hours  
    "brands": 86400,            # 24 hours
    "carriers": 86400,          # 24 hours
    "countries": 86400,         # 24 hours
    "langs": 86400,             # 24 hours
    "config": 900,              # 15 minutes
    
    # Entity details
    "customer": 3600,           # 1 hour
    "product": 21600,           # 6 hours
    "order": 120,               # 2 minutes
    "quote": 300,               # 5 minutes
    "preventivo": 300,          # 5 minutes
    "address": 7200,            # 2 hours
    
    # Lists and queries
    "customers_list": 30,       # 30 seconds
    "products_list": 60,        # 1 minute
    "orders_list": 30,          # 30 seconds
    "quotes_list": 60,          # 1 minute
    "preventivi_list": 300,     # 5 minutes
    "orders_history": 300,      # 5 minutes
    
    # External APIs
    "prestashop_orders": 120,   # 2 minutes
    "prestashop_customers": 300, # 5 minutes
    "prestashop_products": 600, # 10 minutes
    "fatturapa_pool": 60,       # 1 minute
    "fatturapa_invoice": 86400, # 24 hours
    
    # Locks
    "lock": 60,                 # 1 minute
    
    # Initialization data
    "init_static": 604800,      # 7 giorni (platforms, languages, countries, taxes)
    "init_dynamic": 86400,      # 1 giorno (sectionals, order_states, shipping_states)
    "init_full": 1800,          # 30 minuti (endpoint completo)
    
    # Events
    "events_list": 2592000,     # 30 giorni (mensile) - lista eventi disponibili
}
