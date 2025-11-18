from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
import logging
from sqlalchemy.orm import Session

from src.core.container import container
from src.core.container_config import get_configured_container
from src.services.interfaces.dhl_shipment_service_interface import IDhlShipmentService
from src.services.interfaces.dhl_tracking_service_interface import IDhlTrackingService
from src.schemas.dhl_shipment_schema import DhlCreateShipmentResponse
from src.schemas.dhl_tracking_schema import DhlTrackingRequest, DhlTrackingResponse, NormalizedTrackingResponseSchema
from src.database import get_db
from src.repository.shipping_repository import ShippingRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/shippings/dhl", tags=["DHL Shipments"])


def get_dhl_shipment_service(db: Session = Depends(get_db)) -> IDhlShipmentService:
    """Dependency to get DHL shipment service"""
    configured_container = get_configured_container()
    return configured_container.resolve_with_session(IDhlShipmentService, db)


def get_dhl_tracking_service(db: Session = Depends(get_db)) -> IDhlTrackingService:
    """Dependency to get DHL tracking service"""
    configured_container = get_configured_container()
    return configured_container.resolve_with_session(IDhlTrackingService, db)


@router.post("/{order_id}/create", response_model=DhlCreateShipmentResponse)
async def create_shipment(
    order_id: int,
    dhl_service: IDhlShipmentService = Depends(get_dhl_shipment_service)
):
    """
    [DEPRECATED] Crea un nuova spedizione DHL per un ordine
    
    DEPRECATED: Use /api/v1/shippings/{order_id}/create instead.
    This endpoint is kept for backward compatibility only.
    
    Args:
        order_id: ID dell'ordine per cui creare la spedizione
        dhl_service: Dipendenza del servizio di spedizione DHL
        
    Returns:
        Risposta di creazione spedizione con AWB
        
    """
    try:
        logger.info(f"Creating DHL shipment for order {order_id}")
        result = await dhl_service.create_shipment(order_id)
        
        return DhlCreateShipmentResponse(
            awb=result["awb"]
        )
        
    except HTTPException:
        raise
    except ValueError:
        raise 
    except Exception:
        raise

@router.get("/tracking", response_model=List[NormalizedTrackingResponseSchema])
async def get_tracking(
    tracking: str = Query(..., description="Comma-separated list of tracking numbers"),
    carrier_api_id: int = Query(..., description="Carrier API ID for authentication"),
    dhl_tracking_service: IDhlTrackingService = Depends(get_dhl_tracking_service),
    db: Session = Depends(get_db)
):
    """
    [DEPRECATED] Recupera informazioni di tracciamento per le spedizioni DHL
    
    DEPRECATED: Use /api/v1/shippings/tracking instead.
    This endpoint is kept for backward compatibility only.
    
    Args:
        tracking: Numero di tracciamento separato da virgole
        carrier_api_id: ID dell'API del carrier per l'autenticazione
        dhl_tracking_service: Dipendenza del servizio di tracciamento DHL
        
    Returns:
        Lista di risposte di tracciamento normalizzate
    """
    try:
        # Parse tracking numbers
        tracking_list = [tn.strip() for tn in tracking.split(",") if tn.strip()]
        
        if not tracking_list:
            raise HTTPException(status_code=400, detail="No tracking numbers provided")
        
        logger.info(f"Getting DHL tracking for {len(tracking_list)} shipments")
        
        result = await dhl_tracking_service.get_tracking(tracking_list, carrier_api_id)

        # Aggiorna lo stato shipment in base al tracking (se presente)
        try:
            repo = ShippingRepository(db)
            for item in result:
                tn = item.get("tracking_number")
                state_id = item.get("current_internal_state_id")
                if tn and isinstance(state_id, int):
                    repo.update_state_by_tracking(tn, state_id)
        except Exception as _:
            # Non bloccare la risposta in caso di problemi di aggiornamento
            logger.warning("Errore in aggiornamento stato spedizione", exc_info=True)

        return result
        
    except HTTPException:
        # Rilancia HTTPException così mantiene il formato corretto
        raise
    except ValueError as e:
        logger.error(f"Validation error getting DHL tracking: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting DHL tracking: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")




@router.get("/download-label/{awb}")
async def download_shipment_label(
    awb: str,
    dhl_service: IDhlShipmentService = Depends(get_dhl_shipment_service)
):
    """
    Scarica il PDF della label per una spedizione DHL
    
    Args:
        awb: Air Waybill number della spedizione
        dhl_service: Dipendenza del servizio di spedizione DHL
        
    Returns:
        File PDF della label
    """
    try:
        from fastapi.responses import FileResponse
        import os
        
        logger.info(f"Downloading label for AWB: {awb}")
        
        # Recupera il percorso del file PDF
        file_path = await dhl_service.get_label_file_path(awb)
        print(file_path)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Label not found for AWB: {awb}")
        
        return FileResponse(
            path=file_path,
            filename=f"dhl_label_{awb}.pdf",
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading label for AWB {awb}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/cleanup-documents")
async def cleanup_expired_documents(db: Session = Depends(get_db)):
    """
    Cleanup expired shipment documents
    
    Returns:
        Cleanup results with counts and memory freed
    """
    try:
        from src.core.container_config import get_configured_container
        from src.repository.interfaces.shipment_document_repository_interface import IShipmentDocumentRepository
        
        configured_container = get_configured_container()
        document_repo = configured_container.resolve_with_session(IShipmentDocumentRepository, db)
        
        # POINT 1: Finding expired documents in shipment_documents table
        expired_documents = document_repo.get_expired_documents()
        
        logger.info(f"Found {len(expired_documents)} expired documents to cleanup")
        
        # TODO: Point 2 - Deleting files from filesystem
        # TODO: Point 3 - Removing database records
        # TODO: Point 4 - Calculating memory freed
        
        return {
            "message": "Cleanup completed",
            "expired_documents_found": len(expired_documents),
            "documents_deleted": 0,  # TODO: Implement document cleanup (points 2-4)
            "memory_freed_bytes": 0  # TODO: Calculate actual memory freed
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail="Cleanup failed")
