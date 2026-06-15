"""Router FastAPI per la feature Bordero (riepilogo spedizioni).

Espone l'endpoint `POST /api/v1/bordero/generate` che produce un PDF tabellare
delle spedizioni in stato "Spediti" per un corriere selezionato, con opzione
di cambio stato automatico a "Spedizione Confermata".
"""
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.bordero_schema import BorderoGenerateRequest
from src.services.core.wrap import check_authentication
from src.services.routers.auth_service import get_current_user, require_permission
from src.services.routers.bordero_service import BorderoService


router = APIRouter(
    prefix="/api/v1/bordero",
    tags=["Bordero"],
)


def get_bordero_service(db: Session = Depends(get_db)) -> BorderoService:
    return BorderoService(db)


user_dependency = Depends(get_current_user)


def _carrier_filename_token(name: str) -> str:
    """Trasforma il nome corriere in token MAIUSCOLO filename-safe.

    Mantiene solo alfanumerici (es. "BRT", "DHL", "FEDEX"). Match con il
    formato richiesto dal contratto FE: `bordero_BRT_20260525.pdf`.
    """
    if not name:
        return "BORDERO"
    token = re.sub(r"[^a-zA-Z0-9]+", "", name.strip().upper())
    return token or "BORDERO"


@router.post(
    "/generate",
    status_code=status.HTTP_200_OK,
    summary="Genera PDF borderò spedizioni",
    description=(
        "Genera un PDF tabellare delle spedizioni in stato 'Spediti' per il "
        "corriere indicato, filtrate per `id_order_state=3`, "
        "`id_carrier_api=carrier_id`, `tracking IS NOT NULL`, corriere attivo "
        "e opzionalmente finestra date su `orders.date_add` (estremi inclusivi, "
        "stessa semantica di `GET /api/v1/orders/`).\n\n"
        "Se `update_status=true`, dopo la generazione gli ordini inclusi vengono "
        "spostati a stato 'Spedizione Confermata' (best-effort) ed emettono "
        "l'evento `ORDER_STATUS_CHANGED`.\n\n"
        "**Header di risposta:**\n"
        "- `X-Bordero-Order-Count`: numero di spedizioni incluse nel PDF.\n"
        "- `X-Bordero-Order-Ids`: CSV degli `id_order` inclusi (per sync ottimistico FE).\n"
        "- Se count=0: `X-Bordero-Hint-Code`, `X-Bordero-Hint-Message` "
        "(URL-encoded UTF-8, decodificare con `decodeURIComponent`), "
        "`X-Bordero-Missing-Tracking-Count` (diagnostica per messaggio FE mirato).\n\n"
        "**Caso 0 ordini:** ritorna comunque 200 con PDF 'vuoto' e count=0 "
        "(il FE mostra alert info senza aprire il PDF, usando gli hint se presenti)."
    ),
    response_description="File PDF binario del borderò spedizioni",
)
@check_authentication
async def generate_bordero(
    request: BorderoGenerateRequest = Body(
        ...,
        examples={
            "esempio_base": {
                "summary": "Genera borderò senza cambiare stato",
                "value": {"carrier_id": 1, "update_status": False},
            },
            "esempio_con_cambio_stato": {
                "summary": "Genera borderò e sposta ordini a Spedizione Confermata",
                "value": {"carrier_id": 1, "update_status": True},
            },
            "esempio_con_filtri_data": {
                "summary": "Genera borderò con filtri data (allineato al filtro lista FE)",
                "value": {
                    "carrier_id": 6,
                    "update_status": True,
                    "date_from": "2026-05-10",
                    "date_to": "2026-05-26",
                },
            },
        },
    ),
    user: dict = user_dependency,
    service: BorderoService = Depends(get_bordero_service),
    _: None = Depends(require_permission("shipments", "create")),
):
    pdf_bytes, order_count, carrier_name, order_ids, zero_hint = await service.generate_bordero(
        carrier_id=request.carrier_id,
        update_status=request.update_status,
        date_from=request.date_from,
        date_to=request.date_to,
    )

    filename = (
        f"bordero_{_carrier_filename_token(carrier_name)}_"
        f"{datetime.now().strftime('%Y%m%d')}.pdf"
    )

    response_headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "no-cache",
        "Content-Type": "application/pdf",
        "X-Bordero-Order-Count": str(order_count),
        "X-Bordero-Order-Ids": ",".join(str(oid) for oid in order_ids),
        "Access-Control-Expose-Headers": (
            "X-Bordero-Order-Count, X-Bordero-Order-Ids, "
            "X-Bordero-Hint-Code, X-Bordero-Hint-Message, "
            "X-Bordero-Missing-Tracking-Count, Content-Disposition"
        ),
    }
    if zero_hint:
        response_headers["X-Bordero-Hint-Code"] = zero_hint.code
        response_headers["X-Bordero-Hint-Message"] = quote(
            zero_hint.message, safe=""
        )
        response_headers["X-Bordero-Missing-Tracking-Count"] = str(
            zero_hint.missing_tracking_count
        )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=response_headers,
    )
