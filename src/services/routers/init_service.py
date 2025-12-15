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
        print("[INIT] Caricamento dati statici...")
        
        # Carica tutti i dati statici sequenzialmente
        platforms = self._get_platforms()
        languages = self._get_languages()
        countries = self._get_countries()
        taxes = self._get_taxes()
        payments = self._get_payments()
        carriers = self._get_api_carriers()
        stores = self._get_stores()
        
        print(f"[INIT] get_static_data - Stores recuperati: {stores}")
        print(f"[INIT] get_static_data - Stores type: {type(stores)}")
        print(f"[INIT] get_static_data - Stores len: {len(stores) if stores else 0}")
        print(f"[INIT] get_static_data - Stores è None: {stores is None}")
        print(f"[INIT] get_static_data - Stores è lista vuota: {stores == []}")

        result_dict = {
            "platforms": platforms,
            "languages": languages,
            "countries": countries,
            "taxes": taxes,
            "payments": payments,
            "carriers": carriers,
            "stores": stores
        }
        
        print(f"[INIT] get_static_data - Chiavi nel dict risultante: {list(result_dict.keys())}")
        print(f"[INIT] get_static_data - Stores nel dict: {result_dict.get('stores')}")
        print(f"[INIT] get_static_data - Stores type nel dict: {type(result_dict.get('stores'))}")
        print(f"[INIT] get_static_data - 'stores' in dict: {'stores' in result_dict}")
        
        return result_dict
    
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
        
        # Combina tutti i dati - assicurati che stores sia sempre una lista
        stores_list = static_data.get("stores")
        if stores_list is None:
            print("[WARNING] Stores non trovato in static_data, uso lista vuota")
            stores_list = []
        elif not isinstance(stores_list, list):
            print(f"[WARNING] Stores non è una lista (tipo: {type(stores_list)}), converto in lista vuota")
            stores_list = []
        
        print(f"[INIT] Stores recuperati: {len(stores_list)}")
        print(f"[INIT] Stores data: {stores_list}")
        print(f"[INIT] Stores type: {type(stores_list)}")
        
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
                cache_info=cache_info
            )
        except Exception as e:
            print(f"[ERROR] Errore creazione InitDataSchema: {e}")
            print(f"[ERROR] static_data keys: {list(static_data.keys())}")
            print(f"[ERROR] stores presente in static_data: {'stores' in static_data}")
            print(f"[ERROR] stores value: {static_data.get('stores')}")
            print("[ERROR] Possibile causa: cache obsoleta. Prova a cancellare la cache.")
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
        """Ottiene le lingue """
        try:
            return self.lang_repo.get_all_for_init()
        except Exception as e:
            print(f"[ERROR] Errore caricamento languages: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"[ERROR] Errore caricamento metodi di pagamento: {e}")
            return []
    
    def _get_api_carriers(self) -> List[Dict[str, Any]]:
        """Ottiene gli API carrier attivi (solo id_carrier_api e name)"""
        try:
            result = self.api_carrier_repo.get_active_carriers_for_init()
            return result
        except Exception as e:
            print(f"[ERROR] Errore caricamento API carriers: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_stores(self) -> List[Dict[str, Any]]:
        """Ottiene gli store attivi (solo id_store, name, logo)"""
        try:
            print("[INIT] _get_stores - Inizio recupero store attivi...")
            stores = self.store_repo.get_active_stores()
            print(f"[INIT] _get_stores - Store objects recuperati dal repository: {len(stores)}")
            
            if not stores:
                print("[WARNING] _get_stores - Nessuno store attivo trovato nel database")
                return []
            
            result = []
            for s in stores:
                store_dict = {
                    "id_store": s.id_store,
                    "name": s.name,
                    "logo": s.logo
                }
                print(f"[INIT] _get_stores - Store processato: {store_dict}")
                result.append(store_dict)
            
            print(f"[INIT] _get_stores - Risultato finale: {result}")
            print(f"[INIT] _get_stores - Tipo risultato: {type(result)}")
            print(f"[INIT] _get_stores - Lunghezza risultato: {len(result)}")
            return result
        except Exception as e:
            print(f"[ERROR] Errore caricamento stores: {e}")
            import traceback
            traceback.print_exc()
            return []
