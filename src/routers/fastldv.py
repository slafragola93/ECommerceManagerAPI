"""
Router FastLDV — integrazione app magazzino (API key, no JWT).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.container_config import get_configured_container
from src.core.fastldv_auth import verify_fastldv_api_key
from src.database import get_db
from src.events.core.event import Event, EventType
from src.events.runtime import emit_event
from src.schemas.fastldv_schema import (
    FastLdvNotifyPrintRequestSchema,
    FastLdvNotifyPrintResponseSchema,
    FastLdvOrderSuccessResponseSchema,
)
from src.services.interfaces.fastldv_order_service_interface import IFastLdvOrderService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/fastldv",
    tags=["FastLDV"],
    dependencies=[Depends(verify_fastldv_api_key)],
)


def _resolve_fastldv_service(db: Session = Depends(get_db)) -> IFastLdvOrderService:
    return get_configured_container().resolve_with_session(IFastLdvOrderService, db)


@router.get(
    "/order/{code}",
    response_model=FastLdvOrderSuccessResponseSchema,
    summary="Ordine unificato per FastLDV (dati + validazione + righe)",
)
async def get_fastldv_order(
    code: int = Path(
        ...,
        gt=0,
        description=(
            "Codice ordine scansionato. Lookup: orders.id_origin (PrestaShop) "
            "oppure orders.id_order se l'ordine è creato dal gestionale (id_origin=0)."
        ),
    ),
    carrier: Optional[str] = Query(None, description="Nome corriere selezionato in app (safety-net)"),
    printer: Optional[str] = Query(None, description="Nome stampante per audit log"),
    id_store: Optional[int] = Query(None, gt=0, description="Disambiguazione multi-negozio"),
    skip_log: Optional[int] = Query(0, description="1 = anteprima senza log blocco"),
    service: IFastLdvOrderService = Depends(_resolve_fastldv_service),
):
    data, printable = service.get_order_context(
        id_origin=code,
        carrier_query=carrier,
        printer=printer,
        id_store=id_store,
        skip_log=bool(skip_log),
    )

    payload = FastLdvOrderSuccessResponseSchema(data=data)

    if not printable:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "error_code": "FASTLDV_NOT_PRINTABLE",
                "message": data.validation.message,
                "data": data.model_dump(),
            },
        )

    return payload


@router.post(
    "/notify-print",
    response_model=FastLdvNotifyPrintResponseSchema,
    summary="Aggiorna tracking dopo stampa etichetta",
)
async def notify_fastldv_print(
    body: FastLdvNotifyPrintRequestSchema,
    service: IFastLdvOrderService = Depends(_resolve_fastldv_service),
):
    result = service.notify_print(body)
    try:
        emit_event(
            Event(
                event_type=EventType.ORDER_TRACKING_UPDATED.value,
                data={
                    "id_order": result.data["id_order"],
                    "tracking": result.data["tracking"],
                    "awb": result.data.get("awb"),
                    "id_shipping": result.data["id_shipping"],
                    "source": "fastldv",
                },
                metadata={
                    "source": "fastldv.notify_print",
                    "id_origin_db": result.data["id_origin"],
                    "scan_code": body.id_origin,
                },
            )
        )
    except Exception as exc:
        logger.warning(
            "Failed to emit ORDER_TRACKING_UPDATED for order %s: %s",
            result.data.get("id_order"),
            exc,
            exc_info=True,
        )
    return result
