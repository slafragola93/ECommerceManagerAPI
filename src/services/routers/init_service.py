"""
Servizio per i dati di inizializzazione del frontend
"""

from typing import Dict, Any, List
from datetime import datetime

from src.core.cached import cached
from src.core.settings import TTL_PRESETS
from src.core.exceptions import InfrastructureException, ErrorCode
from src.schemas.init_schema import InitDataSchema, CacheInfoSchema

from src.repository.platform_repository import PlatformRepository
from src.repository.lang_repository import LangRepository
from src.repository.country_repository import CountryRepository
from src.repository.tax_repository import TaxRepository
from src.repository.sectional_repository import SectionalRepository
from src.repository.order_state_repository import OrderStateRepository
from src.repository.shipping_state_repository import ShippingStateRepository
from src.repository.payment_repository import PaymentRepository
from src.repository.api_carrier_repository import ApiCarrierRepository
from src.repository.store_repository import StoreRepository
from src.models.ecommerce_order_state import EcommerceOrderState


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
        self.payment_repo = PaymentRepository(db)
        self.api_carrier_repo = ApiCarrierRepository(db)
        self.store_repo = StoreRepository(db)
    
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
        # Carica tutti i dati statici sequenzialmente
        platforms = self._get_platforms()
        languages = self._get_languages()
        countries = self._get_countries()
        taxes = self._get_taxes()
        payments = self._get_payments()
        carriers = self._get_api_carriers()
        stores = self._get_stores()

        result_dict = {
            "platforms": platforms,
            "languages": languages,
            "countries": countries,
            "taxes": taxes,
            "payments": payments,
            "carriers": carriers,
            "stores": stores
        }
        
        return result_dict
    
    @cached(
        ttl=TTL_PRESETS.get("init_dynamic", 86400),  # 1 giorno per dati dinamici
        key="init_data:dynamic",
        layer="hybrid"
    )
    async def get_dynamic_data(self) -> Dict[str, Any]:
        """
        Ottiene i dati dinamici (sectionals, order_states, shipping_states, ecommerce_order_states)
        Cache: 1 giorno
        """
        # Carica tutti i dati dinamici sequenzialmente
        sectionals = self._get_sectionals()
        order_states = self._get_order_states()
        shipping_states = self._get_shipping_states()
        ecommerce_order_states = self._get_ecommerce_order_states()
        
        return {
            "sectionals": sectionals,
            "order_states": order_states,
            "shipping_states": shipping_states,
            "ecommerce_order_states": ecommerce_order_states
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
    
        # Carica dati statici e dinamici sequenzialmente
        static_data = await self.get_static_data()
        dynamic_data = await self.get_dynamic_data()
        
        # Calcola statistiche
        total_items = (
            len(static_data.get("platforms", [])) +
            len(static_data.get("languages", [])) +
            len(static_data.get("countries", [])) +
            len(static_data.get("taxes", [])) +
            len(static_data.get("payments", [])) +
            len(static_data.get("carriers", [])) +
            len(static_data.get("stores", [])) +
            len(dynamic_data.get("sectionals", [])) +
            len(dynamic_data.get("order_states", [])) +
            len(dynamic_data.get("shipping_states", [])) +
            len(dynamic_data.get("ecommerce_order_states", []))
        )
        
        # Crea metadati cache
        cache_info = CacheInfoSchema(
            generated_at=datetime.now(),
            ttl_static=TTL_PRESETS.get("init_static", 604800),
            ttl_dynamic=TTL_PRESETS.get("init_dynamic", 86400),
            version="1.0",
            total_items=total_items
        )
        
        # Combina tutti i dati - assicurati che stores sia sempre una lista
        stores_list = static_data.get("stores")
        if stores_list is None:
            stores_list = []
        elif not isinstance(stores_list, list):
            stores_list = []
        
        # Verifica che tutti i campi richiesti siano presenti
        try:
            return InitDataSchema(
                platforms=static_data.get("platforms", []),
                languages=static_data.get("languages", []),
                countries=static_data.get("countries", []),
                taxes=static_data.get("taxes", []),
                payments=static_data.get("payments", []),
                carriers=static_data.get("carriers", []),
                stores=stores_list,
                sectionals=dynamic_data.get("sectionals", []),
                order_states=dynamic_data.get("order_states", []),
                shipping_states=dynamic_data.get("shipping_states", []),
                ecommerce_order_states=dynamic_data.get("ecommerce_order_states", []),
                cache_info=cache_info
            )
        except Exception as e:
            raise InfrastructureException(
                message=f"Errore validazione InitDataSchema. Possibile causa: cache obsoleta senza campo 'stores'. "
                       f"Prova a cancellare la cache e riprova.",
                error_code=ErrorCode.DATABASE_ERROR,
                details={
                    "original_error": str(e),
                    "static_data_keys": list(static_data.keys()),
                    "stores_present": 'stores' in static_data,
                    "stores_value": str(static_data.get('stores')),
                    "suggestion": "Cancella la cache e riprova",
                    "cache_keys": ["init_data:static", "init_data:full"]
                }
            ) from e
    
    def _get_platforms(self) -> List[Dict[str, Any]]:
        """Ottiene le piattaforme"""
        try:
            # Usa un limite alto per ottenere tutti i dati
            platforms = self.platform_repo.get_all(limit=10000)
            # Rimuovi API key per sicurezza
            result = []
            for p in platforms:
                platform_dict = {
                    "id_platform": p.id_platform,
                    "name": p.name,
                    "is_default": p.is_default
                }
                # Aggiungi logo basato su platform name
                if p.name:
                    # Costruisci il path del logo: /media/logos/platforms/{platform_name.lower()}.png
                    platform_dict["logo"] = f"/media/logos/platforms/{p.name.lower()}.png"
                else:
                    platform_dict["logo"] = None
                result.append(platform_dict)
            return result
        except Exception as e:
            return []
    
    def _get_languages(self) -> List[Dict[str, Any]]:
        """Ottiene le lingue """
        try:
            return self.lang_repo.get_all_for_init()
        except Exception as e:
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
            return []
    
    def _get_payments(self) -> List[Dict[str, Any]]:
        """Ottiene i metodi di pagamento"""
        try:
            payments = self.payment_repo.get_all(limit=10000)
            return [
                {
                    "id_payment": p.id_payment,
                    "name": p.name
                }
                for p in payments
            ]
        except Exception as e:
            return []
    
    def _get_api_carriers(self) -> List[Dict[str, Any]]:
        """Ottiene gli API carrier attivi con logo"""
        try:
            result = self.api_carrier_repo.get_active_carriers_for_init()
            
            # Aggiungi logo basato su carrier_type
            for carrier in result:
                carrier_type = carrier.get("carrier_type", "")
                if carrier_type:
                    # Costruisci il path del logo: /media/logos/carriers/{carrier_type.lower()}.png
                    carrier["logo"] = f"/media/logos/carriers/{carrier_type.lower()}.png"
                else:
                    carrier["logo"] = None
            return result
        except Exception as e:
            return []
    
    def _get_stores(self) -> List[Dict[str, Any]]:
        """Ottiene gli store attivi (solo id_store, name, logo)"""
        try:
            stores = self.store_repo.get_active_stores()
            
            if not stores:
                return []
            
            result = []
            for s in stores:
                logo_path = s.get_logo_path() if s.logo else None
                store_dict = {
                    "id_store": s.id_store,
                    "name": s.name,
                    "logo": logo_path
                }
                result.append(store_dict)
            return result
        except Exception as e:
            return []
    
    def _get_ecommerce_order_states(self) -> List[Dict[str, Any]]:
        """Ottiene gli stati e-commerce sincronizzati (id_platform_state, id_store, name)"""
        try:
            ecommerce_states = self.db.query(EcommerceOrderState).all()
            return [
                {
                    "id_platform_state": es.id_platform_state,
                    "id_store": es.id_store,
                    "name": es.name
                }
                for es in ecommerce_states
            ]
        except Exception as e:
            return []
