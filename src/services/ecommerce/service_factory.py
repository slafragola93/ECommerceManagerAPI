"""Factory utilities for e-commerce services."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.core.exceptions import BusinessRuleException
from src.models.platform import Platform
from src.services.ecommerce.prestashop_service import PrestaShopService


def create_ecommerce_service(
    platform: Platform,
    db: Session,
    **kwargs: Any,
) -> PrestaShopService:
    """Return the e-commerce service implementation for the provided platform."""

    platform_name = (platform.name or "").lower()

    if platform_name == "prestashop":
        service_kwargs = {"platform_id": platform.id_platform}
        service_kwargs.update(kwargs)
        return PrestaShopService(db, **service_kwargs)

    raise BusinessRuleException(
        f"Piattaforma '{platform.name}' non supportata.",
        details={
            "platform_id": platform.id_platform,
            "platform_name": platform.name,
        },
    )


