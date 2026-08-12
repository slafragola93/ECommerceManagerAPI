"""
Audit Log Router — sola lettura.

Gate: require_permission("audit", "read") → accesso completo a tutti i log.
can_create / can_update / can_delete sul modulo audit non sono usati
(entità append-only; unico flag effettivo = can_read).
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status

from src.core.dependencies import db_dependency
from src.repository.interfaces.audit_log_repository_interface import IAuditLogRepository
from src.schemas.audit_log_schema import (
    AllAuditLogResponseSchema,
    AuditLogResponseSchema,
)
from src.services.core.wrap import check_authentication
from src.services.interfaces.audit_log_service_interface import IAuditLogService
from src.services.routers.auth_service import get_current_user, require_permission

from .dependencies import LIMIT_DEFAULT, MAX_LIMIT

router = APIRouter(
    prefix="/api/v1/audit-logs",
    tags=["AuditLog"],
)


def get_audit_log_service(db: db_dependency) -> IAuditLogService:
    from src.core.container_config import get_configured_container

    configured_container = get_configured_container()
    repo = configured_container.resolve_with_session(IAuditLogRepository, db)
    service = configured_container.resolve(IAuditLogService)
    if hasattr(service, "_audit_log_repository"):
        service._audit_log_repository = repo
    return service


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=AllAuditLogResponseSchema,
)
@check_authentication
async def get_all_audit_logs(
    user: dict = Depends(get_current_user),
    audit_service: IAuditLogService = Depends(get_audit_log_service),
    _: None = Depends(require_permission("audit", "read")),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    actor_id: Optional[int] = Query(None, description="Filtro opzionale per attore"),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
):
    """
    Lista paginata audit log.

    Richiede can_read sul modulo audit (o role_type=full_crud).
    Visibilità completa: tutte le azioni di tutti gli utenti, tutte le colonne.
    """
    filters = {
        "actor_id": actor_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action": action,
        "level": level,
        "date_from": date_from,
        "date_to": date_to,
    }
    logs = await audit_service.get_audit_logs(page=page, limit=limit, **filters)
    total = await audit_service.get_audit_logs_count(**filters)
    return {
        "status": "success",
        "count": total,
        "data": logs,
        "page": page,
        "limit": limit,
    }


@router.get(
    "/{id_audit_log}",
    status_code=status.HTTP_200_OK,
    response_model=AuditLogResponseSchema,
)
@check_authentication
async def get_audit_log_by_id(
    id_audit_log: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    audit_service: IAuditLogService = Depends(get_audit_log_service),
    _: None = Depends(require_permission("audit", "read")),
):
    """Dettaglio singolo audit log (payload completo inclusi campi sensibili)."""
    return await audit_service.get_audit_log(id_audit_log)
