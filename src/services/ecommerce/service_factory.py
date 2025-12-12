"""Factory utilities for e-commerce services."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.core.exceptions import BusinessRuleException
from src.models.platform import Platform
from src.services.ecommerce.prestashop_service import PrestaShopService


def create_ecommerce_service(
    store_id: int,
    db: Session,
    **kwargs: Any,
) -> PrestaShopService:
    """Return the e-commerce service implementation for the provided store."""

    # For now, we assume PrestaShop. In the future, we can check store.platform.name
    service_kwargs = {"store_id": store_id}
    service_kwargs.update(kwargs)
    return PrestaShopService(db, **service_kwargs)


