"""
Servizio per i dati di inizializzazione del frontend
"""

from typing import Dict, Any, List
from datetime import datetime

from src.core.cached import cached
from src.core.settings import TTL_PRESETS
from src.schemas.init_schema import InitDataSchema, CacheInfoSchema

from src.repository.platform_repository import PlatformRepository
from src.repository.lang_repository import LangRepository
from src.repository.country_repository import CountryRepository
from src.repository.tax_repository import TaxRepository
from src.repository.sectional_repository import SectionalRepository
from src.repository.order_state_repository import OrderStateRepository
from src.repository.shipping_state_repository import ShippingStateRepository


class InitService:
    """
    Servizio per aggregare i dati di inizializzazione del frontend
    """
    
    def __init__(self, db):
        self.db = db
        self.platform_repo = PlatformRepository(db)
        self.lang_repo = LangRepository(db)
        self.country_repo = CountryRepository(db)
        self.tax_repo = TaxRepository(db)
        self.sectional_repo = SectionalRepository(db)
        self.order_state_repo = OrderStateRepository(db)
        self.shipping_state_repo = ShippingStateRepository(db)
    
    @cached(
        ttl=TTL_PRESETS.get("init_static", 604800),  # 7 giorni per dati statici
        key="init_data:static",
        layer="hybrid"
    )
    async def get_static_data(self) -> Dict[str, Any]:
        """
        Ottiene i dati statici (platforms, languages, countries, taxes)
        Cache: 7 giorni
        """
        print("[INIT] Caricamento dati statici...")
        
        # Carica tutti i dati statici sequenzialmente
        platforms = self._get_platforms()
        languages = self._get_languages()
        countries = self._get_countries()
        taxes = self._get_taxes()
        
        return {
            "platforms": platforms,
            "languages": languages,
            "countries": countries,
            "taxes": taxes
        }
    
    @cached(
        ttl=TTL_PRESETS.get("init_dynamic", 86400),  # 1 giorno per dati dinamici
        key="init_data:dynamic",
        layer="hybrid"
    )
    async def get_dynamic_data(self) -> Dict[str, Any]:
        """
        Ottiene i dati dinamici (sectionals, order_states, shipping_states)
        Cache: 1 giorno
        """
        print("[INIT] Caricamento dati dinamici...")
        
        # Carica tutti i dati dinamici sequenzialmente
        sectionals = self._get_sectionals()
        order_states = self._get_order_states()
        shipping_states = self._get_shipping_states()
        
        return {
            "sectionals": sectionals,
            "order_states": order_states,
            "shipping_states": shipping_states
        }
    
    @cached(
        ttl=TTL_PRESETS.get("init_full", 1800),  # 30 minuti per endpoint completo
        key="init_data:full",
        layer="hybrid"
    )
    async def get_full_init_data(self) -> InitDataSchema:
        """
        Ottiene tutti i dati di inizializzazione
        Cache: 30 minuti
        """
        print("[INIT] Caricamento dati completi di inizializzazione...")
        
        # Carica dati statici e dinamici sequenzialmente
        static_data = await self.get_static_data()
        dynamic_data = await self.get_dynamic_data()
        
        print(f"DEBUG: Static data: {static_data}")
        print(f"DEBUG: Dynamic data: {dynamic_data}")
        
        # Calcola statistiche
        total_items = (
            len(static_data.get("platforms", [])) +
            len(static_data.get("languages", [])) +
            len(static_data.get("countries", [])) +
            len(static_data.get("taxes", [])) +
            len(dynamic_data.get("sectionals", [])) +
            len(dynamic_data.get("order_states", [])) +
            len(dynamic_data.get("shipping_states", []))
        )
        
        # Crea metadati cache
        cache_info = CacheInfoSchema(
            generated_at=datetime.now(),
            ttl_static=TTL_PRESETS.get("init_static", 604800),
            ttl_dynamic=TTL_PRESETS.get("init_dynamic", 86400),
            version="1.0",
            total_items=total_items
        )
        
        # Combina tutti i dati
        return InitDataSchema(
            platforms=static_data.get("platforms", []),
            languages=static_data.get("languages", []),
            countries=static_data.get("countries", []),
            taxes=static_data.get("taxes", []),
            sectionals=dynamic_data.get("sectionals", []),
            order_states=dynamic_data.get("order_states", []),
            shipping_states=dynamic_data.get("shipping_states", []),
            cache_info=cache_info
        )
    
    def _get_platforms(self) -> List[Dict[str, Any]]:
        """Ottiene le piattaforme (senza API key)"""
        try:
            # Usa un limite alto per ottenere tutti i dati
            platforms = self.platform_repo.get_all(limit=10000)
            # Rimuovi API key per sicurezza
            return [
                {
                    "id_platform": p.id_platform,
                    "name": p.name,
                    "is_default": p.is_default
                }
                for p in platforms
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento platforms: {e}")
            return []
    
    def _get_languages(self) -> List[Dict[str, Any]]:
        """Ottiene le lingue"""
        try:
            languages = self.lang_repo.get_all(limit=10000)
            return [
                {
                    "id_lang": l.id_lang,
                    "name": l.name,
                    "iso_code": l.iso_code
                }
                for l in languages
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento languages: {e}")
            return []
    
    def _get_countries(self) -> List[Dict[str, Any]]:
        """Ottiene i paesi"""
        try:
            countries = self.country_repo.get_all(limit=10000)
            return [
                {
                    "id_country": c.id_country,
                    "name": c.name,
                    "iso_code": c.iso_code,
                    "id_origin": c.id_origin
                }
                for c in countries
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento countries: {e}")
            return []
    
    def _get_taxes(self) -> List[Dict[str, Any]]:
        """Ottiene le tasse"""
        try:
            taxes = self.tax_repo.get_all(limit=10000)
            return [
                {
                    "id_tax": t.id_tax,
                    "id_country": t.id_country,
                    "is_default": t.is_default,
                    "name": t.name,
                    "note": t.note,
                    "code": t.code,
                    "percentage": t.percentage,
                    "electronic_code": t.electronic_code
                }
                for t in taxes
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento taxes: {e}")
            return []
    
    def _get_sectionals(self) -> List[Dict[str, Any]]:
        """Ottiene le sezioni"""
        try:
            sectionals = self.sectional_repo.get_all(limit=10000)
            return [
                {
                    "id_sectional": s.id_sectional,
                    "name": s.name
                }
                for s in sectionals
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento sectionals: {e}")
            return []
    
    def _get_order_states(self) -> List[Dict[str, Any]]:
        """Ottiene gli stati degli ordini"""
        try:
            order_states = self.order_state_repo.get_all(limit=10000)
            return [
                {
                    "id_order_state": os.id_order_state,
                    "name": os.name
                }
                for os in order_states
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento order_states: {e}")
            return []
    
    def _get_shipping_states(self) -> List[Dict[str, Any]]:
        """Ottiene gli stati di spedizione"""
        try:
            shipping_states = self.shipping_state_repo.get_all(limit=10000)
            return [
                {
                    "id_shipping_state": ss.id_shipping_state,
                    "name": ss.name
                }
                for ss in shipping_states
            ]
        except Exception as e:
            print(f"[ERROR] Errore caricamento shipping_states: {e}")
            return []
