"""Router API ricevute."""
from datetime import date
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import StreamingResponse

from src.schemas.ricevuta_schema import (
    RicevutaCreateSchema,
    RicevutaExportFormatSchema,
    RicevutaFiltersSchema,
    RicevutaListResponseSchema,
    RicevutaResponseSchema,
    RicevutaStatoSchema,
    RicevutaUpdateSchema,
)
from src.services.core.wrap import check_authentication
from src.services.interfaces.ricevuta_service_interface import IRicevutaService
from src.services.routers.auth_service import get_current_user, require_permission
from src.routers.dependencies import LIMIT_DEFAULT, MAX_LIMIT, get_ricevuta_service

router = APIRouter(
    prefix="/api/v1/ricevute",
    tags=["Ricevute"],
    redirect_slashes=False,
)

user_dependency = Depends(get_current_user)
read_permission = Depends(require_permission("fiscal_documents", "read"))
create_permission = Depends(require_permission("fiscal_documents", "create"))
update_permission = Depends(require_permission("fiscal_documents", "update"))
delete_permission = Depends(require_permission("fiscal_documents", "delete"))


@router.post(
    "",
    response_model=RicevutaResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Crea ricevuta da ordine",
)
@router.post(
    "/",
    response_model=RicevutaResponseSchema,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@check_authentication
async def create_ricevuta(
    payload: RicevutaCreateSchema = Body(
        ...,
        examples={
            "default_emissione": {
                "summary": "Emissione con data odierna",
                "value": {"id_order": 12345},
            },
            "data_emissione_esplicita": {
                "summary": "Data emissione custom",
                "value": {"id_order": 12345, "data_emissione": "2026-07-08"},
            },
        },
    ),
    user: dict = user_dependency,
    _: None = create_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
) -> RicevutaResponseSchema:
    user_id = user.get("id_user") or user.get("user_id")
    return service.create_ricevuta(payload, user_id=user_id)


@router.get(
    "",
    response_model=RicevutaListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Lista ricevute con filtri",
)
@router.get(
    "/",
    response_model=RicevutaListResponseSchema,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@check_authentication
async def list_ricevute(
    id_order: Optional[int] = Query(None, gt=0, description="Filtra per ordine"),
    id_customer: Optional[int] = Query(None, gt=0, description="Filtra per cliente"),
    stato: Optional[RicevutaStatoSchema] = Query(None, description="Filtra per stato"),
    data_emissione_from: Optional[date] = Query(
        None, description="Data emissione da (inclusa)"
    ),
    data_emissione_to: Optional[date] = Query(
        None, description="Data emissione a (inclusa)"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(LIMIT_DEFAULT, ge=1, le=MAX_LIMIT),
    user: dict = user_dependency,
    _: None = read_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
) -> RicevutaListResponseSchema:
    filters = RicevutaFiltersSchema(
        id_order=id_order,
        id_customer=id_customer,
        stato=stato,
        data_emissione_from=data_emissione_from,
        data_emissione_to=data_emissione_to,
        page=page,
        limit=limit,
    )
    return service.list_ricevute(filters)


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export massivo ricevute (CSV/Excel)",
)
@check_authentication
async def export_ricevute(
    fmt: RicevutaExportFormatSchema = Query(
        RicevutaExportFormatSchema.CSV, description="csv o xlsx"
    ),
    id_order: Optional[int] = Query(None, gt=0),
    id_customer: Optional[int] = Query(None, gt=0),
    stato: Optional[RicevutaStatoSchema] = Query(None),
    data_emissione_from: Optional[date] = Query(None),
    data_emissione_to: Optional[date] = Query(None),
    user: dict = user_dependency,
    _: None = read_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
):
    filters = RicevutaFiltersSchema(
        id_order=id_order,
        id_customer=id_customer,
        stato=stato,
        data_emissione_from=data_emissione_from,
        data_emissione_to=data_emissione_to,
    )
    content, media_type, filename = service.export_ricevute(filters, fmt.value)
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{id_ricevuta}/export",
    status_code=status.HTTP_200_OK,
    summary="Export singola ricevuta (CSV/Excel)",
)
@check_authentication
async def export_ricevuta(
    id_ricevuta: int = Path(..., gt=0),
    fmt: RicevutaExportFormatSchema = Query(
        RicevutaExportFormatSchema.CSV, description="csv o xlsx"
    ),
    user: dict = user_dependency,
    _: None = read_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
):
    content, media_type, filename = service.export_ricevuta(id_ricevuta, fmt.value)
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{id_ricevuta}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Rigenera PDF ricevuta (sovrascrive file esistente)",
)
@check_authentication
async def regenerate_ricevuta_pdf(
    id_ricevuta: int = Path(..., gt=0),
    user: dict = user_dependency,
    _: None = update_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
):
    pdf_bytes = service.regenerate_pdf(id_ricevuta)
    filename = f"Ricevuta-{id_ricevuta}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/{id_ricevuta}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Scarica PDF ricevuta (rigenera se assente)",
)
@check_authentication
async def download_ricevuta_pdf(
    id_ricevuta: int = Path(..., gt=0),
    regenerate: bool = Query(
        False,
        description="Se true, rigenera il PDF con il template corrente (sovrascrive il file su disco)",
    ),
    user: dict = user_dependency,
    _: None = read_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
):
    pdf_bytes = service.get_ricevuta_pdf_bytes(id_ricevuta, regenerate=regenerate)
    filename = f"Ricevuta-{id_ricevuta}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.put(
    "/{id_ricevuta}",
    response_model=RicevutaResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Aggiorna data emissione ricevuta",
)
@check_authentication
async def update_ricevuta(
    id_ricevuta: int = Path(..., gt=0),
    payload: RicevutaUpdateSchema = Body(...),
    user: dict = user_dependency,
    _: None = update_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
) -> RicevutaResponseSchema:
    user_id = user.get("id_user") or user.get("user_id")
    return service.update_ricevuta(id_ricevuta, payload, user_id=user_id)


@router.delete(
    "/{id_ricevuta}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina ricevuta (cancellazione definitiva)",
)
@check_authentication
async def delete_ricevuta(
    id_ricevuta: int = Path(..., gt=0),
    user: dict = user_dependency,
    _: None = delete_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
) -> None:
    user_id = user.get("id_user") or user.get("user_id")
    service.delete_ricevuta(id_ricevuta, user_id=user_id)


@router.get(
    "/{id_ricevuta}",
    response_model=RicevutaResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Dettaglio ricevuta con dati live ordine/cliente/order_details",
)
@check_authentication
async def get_ricevuta(
    id_ricevuta: int = Path(..., gt=0),
    user: dict = user_dependency,
    _: None = read_permission,
    service: IRicevutaService = Depends(get_ricevuta_service),
) -> RicevutaResponseSchema:
    return service.get_ricevuta(id_ricevuta)
