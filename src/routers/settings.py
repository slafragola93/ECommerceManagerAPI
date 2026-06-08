"""
Router /api/v1/settings/ — facade compatibile FE.

Persistenza su app_configurations (category=vies, name=reverse_charge_id_tax).
Per CRUD generico usare /api/v1/app_configurations/.
"""
from fastapi import APIRouter, Depends, status

from src.core.dependencies import db_dependency
from src.core.container_config import get_configured_container
from src.repository.interfaces.app_configuration_repository_interface import (
    IAppConfigurationRepository,
)
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.schemas.settings_schema import SettingsUpdateSchema
from src.services.core.wrap import check_authentication
from src.services.interfaces.settings_service_interface import ISettingsService
from src.services.routers.auth_service import get_current_user, require_permission
from src.services.routers.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


def get_settings_service(db: db_dependency) -> ISettingsService:
    configured = get_configured_container()
    app_repo = configured.resolve_with_session(IAppConfigurationRepository, db)
    tax_repo = configured.resolve_with_session(ITaxRepository, db)
    service = SettingsService(app_repo, tax_repo)
    return service


@router.get("/", status_code=status.HTTP_200_OK)
@check_authentication
async def get_settings(
    user: dict = Depends(get_current_user),
    settings_service: ISettingsService = Depends(get_settings_service),
    _: None = Depends(require_permission("settings", "read")),
):
    """Impostazioni VIES (reverse_charge_id_tax da app_configurations)."""
    data = await settings_service.get_settings()
    return {"status": "success", "data": data.model_dump()}


@router.put("/", status_code=status.HTTP_200_OK)
@check_authentication
async def update_settings(
    body: SettingsUpdateSchema,
    user: dict = Depends(get_current_user),
    settings_service: ISettingsService = Depends(get_settings_service),
    _: None = Depends(require_permission("settings", "update")),
):
    """Aggiorna reverse_charge_id_tax in app_configurations (categoria vies)."""
    data = await settings_service.update_settings(body)
    return {"status": "success", "data": data.model_dump()}
