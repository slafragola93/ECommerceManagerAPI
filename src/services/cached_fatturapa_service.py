"""
Cached FatturaPA Service with external API caching
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from .fatturapa_service import FatturaPAService
from ..core.cached import cached, invalidate_pattern
from ..core.settings import get_cache_settings


class CachedFatturaPAService(FatturaPAService):
    """
    FatturaPA Service with integrated caching for external API calls
    """
    
    def __init__(self, db: Session, vat_number: Optional[str] = None):
        super().__init__(db, vat_number)
        self.settings = get_cache_settings()
    
    @cached(preset="fatturapa_pool", key="fatturapa:pool:{tenant}:{page_token}:{hash}", single_flight=True)
    async def get_pool_cached(self, tenant: str, page_token: Optional[str] = None, **filters) -> Dict[str, Any]:
        """Cached version of FatturaPA pool fetch"""
        # This would call the actual FatturaPA API
        return {
            "invoices": [],
            "next_page_token": None,
            "total": 0,
            "cached": True
        }
    
    @cached(preset="fatturapa_invoice", key="fatturapa:inv:{tenant}:{sdi}:meta", single_flight=True)
    async def get_invoice_metadata_cached(self, tenant: str, sdi: str) -> Dict[str, Any]:
        """Cached version of invoice metadata fetch"""
        return {
            "sdi": sdi,
            "metadata": {},
            "cached": True
        }
    
    async def download_pool_with_cache(self, tenant: str, **filters) -> List[Dict[str, Any]]:
        """Download pool with cache invalidation"""
        if not self.settings.cache_external_apis_enabled:
            return await self.download_pool(**filters)
        
        # Use cached data
        page_token = filters.get("page_token")
        cached_data = await self.get_pool_cached(tenant, page_token, **filters)
        
        # Process download logic here
        # ...
        
        return cached_data.get("invoices", [])
    
    async def download_invoice_with_cache(self, tenant: str, sdi: str) -> Optional[Dict[str, Any]]:
        """Download single invoice with cache"""
        if not self.settings.cache_external_apis_enabled:
            return await self.download_invoice(sdi)
        
        cached_metadata = await self.get_invoice_metadata_cached(tenant, sdi)
        
        # Process download logic here
        # ...
        
        return cached_metadata
    
    async def invalidate_fatturapa_cache(self, tenant: str):
        """Manually invalidate FatturaPA cache"""
        patterns = [
            f"fatturapa:pool:{tenant}:*",
            f"fatturapa:inv:{tenant}:*"
        ]
        
        for pattern in patterns:
            await invalidate_pattern(pattern)
    
    def _create_filters_hash(self, filters: Dict[str, Any]) -> str:
        """Create hash for filter parameters"""
        import hashlib
        import json
        
        # Sort filters for consistent hashing
        sorted_filters = sorted(filters.items())
        filter_str = json.dumps(sorted_filters, default=str, sort_keys=True)
        return hashlib.md5(filter_str.encode()).hexdigest()[:8]


# Factory function
def get_cached_fatturapa_service(db: Session, vat_number: Optional[str] = None) -> CachedFatturaPAService:
    """Get cached FatturaPA service instance"""
    return CachedFatturaPAService(db, vat_number)
