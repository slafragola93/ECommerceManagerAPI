"""Factory utilities for e-commerce services."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.core.exceptions import BusinessRuleException
from src.services.ecommerce.base_ecommerce_service import BaseEcommerceService
from src.services.ecommerce.prestashop_service import PrestaShopService
# from src.services.ecommerce.shopify_service import ShopifyService  # Future service


def create_ecommerce_service(
    store_id: int,
    db: Session,
    **kwargs: Any,
) -> BaseEcommerceService:
    """
    Return the e-commerce service implementation for the provided store.
    
    The service is selected based on the platform associated with the store.
    The factory retrieves the store, then the platform, and selects the appropriate
    service based on platform.name (e.g., PrestaShop, Shopify, Magento).
    
    Args:
        store_id: ID of the store
        db: Database session
        **kwargs: Additional keyword arguments to pass to the service
        
    Returns:
        BaseEcommerceService: The appropriate e-commerce service instance
        
    Raises:
        BusinessRuleException: If store not found, platform not associated, or platform not supported
    """
    from src.repository.store_repository import StoreRepository
    
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise BusinessRuleException(f"Store with ID {store_id} not found.")
    
    if not store.platform:
        raise BusinessRuleException(
            f"Store {store.name} (ID: {store_id}) has no platform associated."
        )
    
    platform_name = store.platform.name.lower()
    service_kwargs = {"store_id": store_id}
    service_kwargs.update(kwargs)
    
    if platform_name == "prestashop":
        return PrestaShopService(db, **service_kwargs)
    # elif platform_name == "shopify":
    #     return ShopifyService(db, **service_kwargs)
    # elif platform_name == "magento":
    #     return MagentoService(db, **service_kwargs)
    else:
        raise BusinessRuleException(
            f"Platform '{store.platform.name}' for store ID {store_id} is not supported. "
            f"Supported platforms: PrestaShop"
        )


