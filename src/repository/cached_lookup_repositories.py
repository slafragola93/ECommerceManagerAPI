"""
Cached lookup repositories for static data
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from .order_state_repository import OrderStateRepository
from .category_repository import CategoryRepository
from .brand_repository import BrandRepository
from .carrier_repository import CarrierRepository
from .country_repository import CountryRepository
from .lang_repository import LangRepository
from ..core.cached import cached
from ..core.settings import get_cache_settings


class CachedOrderStateRepository(OrderStateRepository):
    """Order State Repository with caching"""
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="order_states", key="order_states:{tenant}")
    async def get_all_cached(self, tenant: str) -> List:
        """Cached version of get_all"""
        return self.get_all()
    
    @cached(preset="order_states", key="order_state:{tenant}:{state_id}")
    async def get_by_id_cached(self, tenant: str, state_id: int) -> Optional:
        """Cached version of get_by_id"""
        return self.get_by_id(state_id)
    
    @cached(preset="order_states", key="order_states:count:{tenant}")
    async def get_count_cached(self, tenant: str) -> int:
        """Cached version of get_count"""
        return self.get_count()
    
    def get_all_with_cache(self, tenant: str) -> List:
        """Get all order states with caching"""
        if not self.settings.cache_enabled:
            return self.get_all()
        
        return self.get_all_cached(tenant)
    
    def get_by_id_with_cache(self, state_id: int, tenant: str) -> Optional:
        """Get order state by ID with caching"""
        if not self.settings.cache_enabled:
            return self.get_by_id(state_id)
        
        return self.get_by_id_cached(tenant, state_id)
    
    def get_count_with_cache(self, tenant: str) -> int:
        """Get order states count with caching"""
        if not self.settings.cache_enabled:
            return self.get_count()
        
        return self.get_count_cached(tenant)


class CachedCategoryRepository(CategoryRepository):
    """Category Repository with caching"""
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="categories", key="categories:{tenant}")
    async def get_all_cached(self, tenant: str) -> List:
        """Cached version of get_all"""
        return self.get_all()
    
    @cached(preset="categories", key="category:{tenant}:{category_id}")
    async def get_by_id_cached(self, tenant: str, category_id: int) -> Optional:
        """Cached version of get_by_id"""
        return self.get_by_id(category_id)
    
    def get_all_with_cache(self, tenant: str) -> List:
        """Get all categories with caching"""
        if not self.settings.cache_enabled:
            return self.get_all()
        
        return self.get_all_cached(tenant)
    
    def get_by_id_with_cache(self, category_id: int, tenant: str) -> Optional:
        """Get category by ID with caching"""
        if not self.settings.cache_enabled:
            return self.get_by_id(category_id)
        
        return self.get_by_id_cached(tenant, category_id)


class CachedBrandRepository(BrandRepository):
    """Brand Repository with caching"""
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="brands", key="brands:{tenant}")
    async def get_all_cached(self, tenant: str) -> List:
        """Cached version of get_all"""
        return self.get_all()
    
    @cached(preset="brands", key="brand:{tenant}:{brand_id}")
    async def get_by_id_cached(self, tenant: str, brand_id: int) -> Optional:
        """Cached version of get_by_id"""
        return self.get_by_id(brand_id)
    
    def get_all_with_cache(self, tenant: str) -> List:
        """Get all brands with caching"""
        if not self.settings.cache_enabled:
            return self.get_all()
        
        return self.get_all_cached(tenant)
    
    def get_by_id_with_cache(self, brand_id: int, tenant: str) -> Optional:
        """Get brand by ID with caching"""
        if not self.settings.cache_enabled:
            return self.get_by_id(brand_id)
        
        return self.get_by_id_cached(tenant, brand_id)


class CachedCarrierRepository(CarrierRepository):
    """Carrier Repository with caching"""
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="carriers", key="carriers:{tenant}")
    async def get_all_cached(self, tenant: str) -> List:
        """Cached version of get_all"""
        return self.get_all()
    
    @cached(preset="carriers", key="carrier:{tenant}:{carrier_id}")
    async def get_by_id_cached(self, tenant: str, carrier_id: int) -> Optional:
        """Cached version of get_by_id"""
        return self.get_by_id(carrier_id)
    
    def get_all_with_cache(self, tenant: str) -> List:
        """Get all carriers with caching"""
        if not self.settings.cache_enabled:
            return self.get_all()
        
        return self.get_all_cached(tenant)
    
    def get_by_id_with_cache(self, carrier_id: int, tenant: str) -> Optional:
        """Get carrier by ID with caching"""
        if not self.settings.cache_enabled:
            return self.get_by_id(carrier_id)
        
        return self.get_by_id_cached(tenant, carrier_id)


class CachedCountryRepository(CountryRepository):
    """Country Repository with caching"""
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="countries", key="countries:{tenant}")
    async def get_all_cached(self, tenant: str) -> List:
        """Cached version of get_all"""
        return self.get_all()
    
    @cached(preset="countries", key="country:{tenant}:{country_id}")
    async def get_by_id_cached(self, tenant: str, country_id: int) -> Optional:
        """Cached version of get_by_id"""
        return self.get_by_id(country_id)
    
    def get_all_with_cache(self, tenant: str) -> List:
        """Get all countries with caching"""
        if not self.settings.cache_enabled:
            return self.get_all()
        
        return self.get_all_cached(tenant)
    
    def get_by_id_with_cache(self, country_id: int, tenant: str) -> Optional:
        """Get country by ID with caching"""
        if not self.settings.cache_enabled:
            return self.get_by_id(country_id)
        
        return self.get_by_id_cached(tenant, country_id)


class CachedLangRepository(LangRepository):
    """Language Repository with caching"""
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="langs", key="langs:{tenant}")
    async def get_all_cached(self, tenant: str) -> List:
        """Cached version of get_all"""
        return self.get_all()
    
    @cached(preset="langs", key="lang:{tenant}:{lang_id}")
    async def get_by_id_cached(self, tenant: str, lang_id: int) -> Optional:
        """Cached version of get_by_id"""
        return self.get_by_id(lang_id)
    
    def get_all_with_cache(self, tenant: str) -> List:
        """Get all languages with caching"""
        if not self.settings.cache_enabled:
            return self.get_all()
        
        return self.get_all_cached(tenant)
    
    def get_by_id_with_cache(self, lang_id: int, tenant: str) -> Optional:
        """Get language by ID with caching"""
        if not self.settings.cache_enabled:
            return self.get_by_id(lang_id)
        
        return self.get_by_id_cached(tenant, lang_id)


# Factory functions
def get_cached_order_state_repository(session: Session) -> CachedOrderStateRepository:
    """Get cached order state repository"""
    return CachedOrderStateRepository(session)

def get_cached_category_repository(session: Session) -> CachedCategoryRepository:
    """Get cached category repository"""
    return CachedCategoryRepository(session)

def get_cached_brand_repository(session: Session) -> CachedBrandRepository:
    """Get cached brand repository"""
    return CachedBrandRepository(session)

def get_cached_carrier_repository(session: Session) -> CachedCarrierRepository:
    """Get cached carrier repository"""
    return CachedCarrierRepository(session)

def get_cached_country_repository(session: Session) -> CachedCountryRepository:
    """Get cached country repository"""
    return CachedCountryRepository(session)

def get_cached_lang_repository(session: Session) -> CachedLangRepository:
    """Get cached language repository"""
    return CachedLangRepository(session)
