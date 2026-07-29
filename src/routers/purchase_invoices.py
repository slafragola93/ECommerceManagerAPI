"""
API ciclo passivo — fatture e NC ricevute dai fornitori (POOL FatturaPA).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response

from src.core.dependencies import db_dependency
from src.schemas.purchase_invoice_schema import (
    AllPurchaseInvoicesResponseSchema,
    PurchaseInvoiceDetailResponseSchema,
    PurchaseInvoicePaymentUpdateSchema,
    PurchaseInvoiceSyncResultSchema,
)
from src.services.core.wrap import check_authentication
from src.services.interfaces.purchase_invoice_service_interface import (
    IPurchaseInvoiceService,
)
from src.services.routers.auth_service import get_current_user, require_permission
from src.services.routers.purchase_invoice_service import PurchaseInvoiceService
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT

router = APIRouter(
    prefix="/api/v1/purchase-invoices",
    tags=["Purchase Invoices"],
)


def get_purchase_invoice_service(db: db_dependency) -> IPurchaseInvoiceService:
    return PurchaseInvoiceService(db)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=AllPurchaseInvoicesResponseSchema,
)
@check_authentication
async def list_purchase_invoices(
    user: dict = Depends(get_current_user),
    service: IPurchaseInvoiceService = Depends(get_purchase_invoice_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    is_paid: Optional[bool] = Query(None),
    tipo_documento: Optional[str] = Query(
        None, description="Es. TD01, TD04"
    ),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    q: Optional[str] = Query(
        None, description="Cerca fornitore, P.IVA, numero, SDI, filename"
    ),
    _: None = Depends(require_permission("purchase_invoices", "read")),
):
    items, total = await service.list_invoices(
        page=page,
        limit=limit,
        is_paid=is_paid,
        tipo_documento=tipo_documento,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.post(
    "/sync",
    status_code=status.HTTP_200_OK,
    response_model=PurchaseInvoiceSyncResultSchema,
)
@check_authentication
async def sync_purchase_invoices(
    user: dict = Depends(get_current_user),
    service: IPurchaseInvoiceService = Depends(get_purchase_invoice_service),
    _: None = Depends(require_permission("purchase_invoices", "create")),
):
    """Trigger manuale sync POOL FatturaPA (oltre allo scheduler)."""
    stats = await service.sync_pool()
    return PurchaseInvoiceSyncResultSchema(
        status=stats.get("status", "success"),
        entries_found=stats.get("entries_found", 0),
        entries_processed=stats.get("entries_processed", 0),
        entries_downloaded=stats.get("entries_downloaded", 0),
        entries_saved=stats.get("entries_saved", 0),
        entries_skipped=stats.get("entries_skipped", 0),
        errors=stats.get("errors") or [],
        start_time=stats.get("start_time"),
        end_time=stats.get("end_time"),
    )


@router.get(
    "/{invoice_id}",
    status_code=status.HTTP_200_OK,
    response_model=PurchaseInvoiceDetailResponseSchema,
)
@check_authentication
async def get_purchase_invoice(
    invoice_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: IPurchaseInvoiceService = Depends(get_purchase_invoice_service),
    _: None = Depends(require_permission("purchase_invoices", "read")),
):
    return await service.get_invoice(invoice_id)


@router.get("/{invoice_id}/xml", status_code=status.HTTP_200_OK)
@check_authentication
async def download_purchase_invoice_xml(
    invoice_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: IPurchaseInvoiceService = Depends(get_purchase_invoice_service),
    _: None = Depends(require_permission("purchase_invoices", "read")),
):
    filename, content = await service.get_xml_content(invoice_id)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.patch(
    "/{invoice_id}/payment",
    status_code=status.HTTP_200_OK,
    response_model=PurchaseInvoiceDetailResponseSchema,
)
@check_authentication
async def update_purchase_invoice_payment(
    body: PurchaseInvoicePaymentUpdateSchema,
    invoice_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: IPurchaseInvoiceService = Depends(get_purchase_invoice_service),
    _: None = Depends(require_permission("purchase_invoices", "update")),
):
    return await service.update_payment(invoice_id, body)
