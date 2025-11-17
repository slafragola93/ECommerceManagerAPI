"""Router exposing management endpoints for the event system."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from src.events.plugin_manager import PluginManager
from src.events.marketplace.plugin_installer import PluginInstaller
from src.events.runtime import (
    get_config_loader,
    get_marketplace_client,
    get_plugin_manager,
)
from src.services.core.wrap import check_authentication
from src.services.routers.auth_service import authorize, get_current_user
from src.core.cached import cached
from src.events.core.event import EventType

logger = logging.getLogger(__name__)


def get_manager() -> PluginManager:
    try:
        return get_plugin_manager()
    except RuntimeError as exc:  # pragma: no cover - defensive
        logger.exception("Plugin manager not initialised")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_installer() -> PluginInstaller:
    """Get plugin installer instance."""
    config_loader = get_config_loader()
    plugin_manager = get_plugin_manager()
    try:
        marketplace_client = get_marketplace_client()
    except RuntimeError:
        marketplace_client = None
    return PluginInstaller(
        config_loader=config_loader,
        plugin_manager=plugin_manager,
        marketplace_client=marketplace_client,
    )


router = APIRouter(prefix="/api/v1/events", tags=["Event System"])


@router.post(
    "/reload-config",
    summary="Ricarica configurazione eventi",
    response_description="Configurazione ricaricata",
)
@check_authentication
@authorize(roles_permitted=["ADMIN"], permissions_required=["U"])
async def reload_event_configuration(
    user: dict = Depends(get_current_user), plugin_manager: PluginManager = Depends(get_manager)
):
    config = await plugin_manager.reload()
    return {"message": "Configurazione eventi ricaricata", "config": config.model_dump(mode="json")}


@router.get(
    "/plugins",
    summary="Elenco plugin eventi",
    response_description="Stato attuale dei plugin caricati",
)
@check_authentication
@authorize(roles_permitted=["ADMIN"], permissions_required=["R"])
async def list_event_plugins(
    user: dict = Depends(get_current_user), plugin_manager: PluginManager = Depends(get_manager)
):
    status = await plugin_manager.get_status()
    return {"plugins": status}


@router.post(
    "/plugins/{plugin_name}/enable",
    summary="Abilita un plugin",
    response_description="Plugin abilitato",
)
@check_authentication
@authorize(roles_permitted=["ADMIN"], permissions_required=["U"])
async def enable_event_plugin(
    plugin_name: str = Path(..., min_length=1),
    user: dict = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(get_manager),
):
    if plugin_name not in plugin_manager.get_loaded_plugins():
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' non trovato")

    config = await plugin_manager.enable_plugin(plugin_name)
    return {
        "message": f"Plugin '{plugin_name}' abilitato",
        "config": config.model_dump(mode="json"),
    }


@router.post(
    "/plugins/{plugin_name}/disable",
    summary="Disabilita un plugin",
    response_description="Plugin disabilitato",
)
@check_authentication
@authorize(roles_permitted=["ADMIN"], permissions_required=["U"])
async def disable_event_plugin(
    plugin_name: str = Path(..., min_length=1),
    user: dict = Depends(get_current_user),
    plugin_manager: PluginManager = Depends(get_manager),
):
    if plugin_name not in plugin_manager.get_loaded_plugins():
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' non trovato")

    config = await plugin_manager.disable_plugin(plugin_name)
    return {
        "message": f"Plugin '{plugin_name}' disabilitato",
        "config": config.model_dump(mode="json"),
    }


@router.delete(
    "/plugins/{plugin_name}/uninstall",
    summary="Disinstalla e elimina definitivamente un plugin",
    response_description="Plugin disinstallato",
)
@check_authentication
@authorize(roles_permitted=["ADMIN"], permissions_required=["D"])
async def uninstall_event_plugin(
    plugin_name: str = Path(..., min_length=1),
    user: dict = Depends(get_current_user),
    installer: PluginInstaller = Depends(get_installer),
):
    """Disinstalla un plugin eliminando completamente i suoi file dal filesystem."""
    try:
        config = await installer.uninstall(plugin_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Errore disinstallazione plugin '%s'", plugin_name)
        raise HTTPException(status_code=500, detail="Disinstallazione plugin fallita") from exc

    return {
        "message": f"Plugin '{plugin_name}' disinstallato e rimosso definitivamente",
        "config": config.model_dump(mode="json"),
    }


@router.get(
    "/list",
    summary="Lista eventi disponibili",
    response_description="Lista di tutti gli eventi disponibili nell'applicazione",
)
@check_authentication
@authorize(roles_permitted=["ADMIN"], permissions_required=["R"])
@cached(preset="events_list", key="events:list")
async def get_events_list(
    user: dict = Depends(get_current_user)
):
    """
    Restituisce lista di tutti gli eventi disponibili nell'applicazione.
    
    Utile per configurare i trigger di sincronizzazione stati.
    Cache mensile (30 giorni).
    """
    events = EventType.get_all_events()
    return {
        "events": events,
        "total": len(events)
    }

