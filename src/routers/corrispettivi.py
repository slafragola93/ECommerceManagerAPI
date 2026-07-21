from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.corrispettivo_schema import (
    CorrispettivoDayExportRequestSchema,
    CorrispettivoExportRequestSchema,
    CorrispettivoFiltersSchema,
    CorrispettivoListResponseSchema,
    CorrispettivoRiepilogoResponseSchema,
    validate_corrispettivo_day,
)
from src.services.core.wrap import check_authentication
from src.services.routers.auth_service import get_current_user, require_permission
from src.services.routers.corrispettivo_service import CorrispettivoService

router = APIRouter(
    prefix="/api/v1/corrispettivi",
    tags=["Corrispettivi"],
    redirect_slashes=False,
)

user_dependency = Depends(get_current_user)
db_dependency = Depends(get_db)
read_permission = Depends(require_permission("fiscal_documents", "read"))


def get_corrispettivo_service(db: Session = db_dependency) -> CorrispettivoService:
    return CorrispettivoService(db)


def _build_filters(
    id_platform: Optional[int] = None,
    id_store: Optional[int] = None,
    delivery_country_iso: Optional[str] = None,
    day: Optional[int] = None,
) -> Optional[CorrispettivoFiltersSchema]:
    if not any([id_platform, id_store, delivery_country_iso, day]):
        return None
    return CorrispettivoFiltersSchema(
        id_platform=id_platform,
        id_store=id_store,
        delivery_country_iso=delivery_country_iso,
        day=day,
    )


def _validate_period_day(year: int, month: int, day: Optional[int]) -> None:
    if day is not None:
        try:
            validate_corrispettivo_day(year, month, day)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _get_corrispettivi_riepilogo(
    year: int,
    month: int,
    id_platform: Optional[int],
    id_store: Optional[int],
    delivery_country_iso: Optional[str],
    day: Optional[int],
    service: CorrispettivoService,
) -> CorrispettivoRiepilogoResponseSchema:
    _validate_period_day(year, month, day)
    filters = _build_filters(id_platform, id_store, delivery_country_iso, day)
    return service.get_riepilogo(year, month, filters)


async def _get_corrispettivi_daily_summary(
    year: int,
    month: int,
    id_platform: Optional[int],
    id_store: Optional[int],
    delivery_country_iso: Optional[str],
    day: Optional[int],
    service: CorrispettivoService,
) -> CorrispettivoListResponseSchema:
    _validate_period_day(year, month, day)
    filters = _build_filters(id_platform, id_store, delivery_country_iso, day)
    return service.get_daily_summary(year, month, filters)


@router.get(
    "/riepilogo",
    response_model=CorrispettivoRiepilogoResponseSchema,
    status_code=status.HTTP_200_OK,
)
@check_authentication
async def get_corrispettivi_riepilogo(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    id_platform: Optional[int] = Query(None, gt=0),
    id_store: Optional[int] = Query(None, gt=0),
    delivery_country_iso: Optional[str] = Query(None, min_length=2, max_length=5),
    day: Optional[int] = Query(None, ge=1, le=31),
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """
    Riepilogo corrispettivi mensile: matrice giorni × aliquote IVA con vendite nette e resi netti.
    """
    return await _get_corrispettivi_riepilogo(
        year, month, id_platform, id_store, delivery_country_iso, day, service
    )


router.add_api_route(
    "/riepilogo/",
    get_corrispettivi_riepilogo,
    methods=["GET"],
    response_model=CorrispettivoRiepilogoResponseSchema,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)


@router.get(
    "/",
    response_model=CorrispettivoListResponseSchema,
    status_code=status.HTTP_200_OK,
)
@check_authentication
async def get_corrispettivi_daily_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    id_platform: Optional[int] = Query(None, gt=0),
    id_store: Optional[int] = Query(None, gt=0),
    delivery_country_iso: Optional[str] = Query(None, min_length=2, max_length=5),
    day: Optional[int] = Query(None, ge=1, le=31),
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """Totali giornalieri compatti (vendite, resi, netto) con split prodotti/spedizione."""
    return await _get_corrispettivi_daily_summary(
        year, month, id_platform, id_store, delivery_country_iso, day, service
    )


@router.get(
    "/summary",
    response_model=CorrispettivoListResponseSchema,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    deprecated=True,
)
@check_authentication
async def get_corrispettivi_daily_summary_alias(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    id_platform: Optional[int] = Query(None, gt=0),
    id_store: Optional[int] = Query(None, gt=0),
    delivery_country_iso: Optional[str] = Query(None, min_length=2, max_length=5),
    day: Optional[int] = Query(None, ge=1, le=31),
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """Alias legacy di GET `/` per compatibilità FE."""
    return await _get_corrispettivi_daily_summary(
        year, month, id_platform, id_store, delivery_country_iso, day, service
    )


@router.post(
    "/export",
    status_code=status.HTTP_200_OK,
)
@check_authentication
async def export_corrispettivi_registri(
    request: CorrispettivoExportRequestSchema,
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """
    Genera ZIP con `registro.xlsx` consolidato (matrice aliquote) e `registro_{ISO}.xlsx` per paese consegna.
    Con `filters.day` valorizzato: un solo giorno del mese e filename `Registro_YYYY-MM-DD.zip`.
    """
    zip_bytes = service.build_export_zip(request)
    filename = service.export_zip_filename(request)
    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/giorno/riepilogo",
    response_model=CorrispettivoRiepilogoResponseSchema,
    status_code=status.HTTP_200_OK,
)
@check_authentication
async def get_corrispettivi_giorno_riepilogo(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    day: int = Query(..., ge=1, le=31),
    id_platform: Optional[int] = Query(None, gt=0),
    id_store: Optional[int] = Query(None, gt=0),
    delivery_country_iso: Optional[str] = Query(None, min_length=2, max_length=5),
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """Riepilogo corrispettivi per un singolo giorno (matrice aliquote IVA)."""
    return await _get_corrispettivi_riepilogo(
        year, month, id_platform, id_store, delivery_country_iso, day, service
    )


@router.get(
    "/giorno",
    response_model=CorrispettivoListResponseSchema,
    status_code=status.HTTP_200_OK,
)
@check_authentication
async def get_corrispettivi_giorno_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    day: int = Query(..., ge=1, le=31),
    id_platform: Optional[int] = Query(None, gt=0),
    id_store: Optional[int] = Query(None, gt=0),
    delivery_country_iso: Optional[str] = Query(None, min_length=2, max_length=5),
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """Totali corrispettivi per un singolo giorno (vendite, resi, netto)."""
    return await _get_corrispettivi_daily_summary(
        year, month, id_platform, id_store, delivery_country_iso, day, service
    )


@router.post(
    "/giorno/export",
    status_code=status.HTTP_200_OK,
)
@check_authentication
async def export_corrispettivi_giorno(
    request: CorrispettivoDayExportRequestSchema,
    user: dict = user_dependency,
    _: None = read_permission,
    service: CorrispettivoService = Depends(get_corrispettivo_service),
):
    """Genera ZIP `Registro_YYYY-MM-DD.zip` con Excel corrispettivo del singolo giorno."""
    export_request = request.to_export_request()
    zip_bytes = service.build_export_zip(export_request)
    filename = service.export_zip_filename(export_request)
    return StreamingResponse(
        BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
