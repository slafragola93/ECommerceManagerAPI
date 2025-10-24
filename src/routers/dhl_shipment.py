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
    Crea un nuova spedizione DHL per un ordine
    
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
        
    except ValueError as e:
        logger.error(f"Validation error creating DHL shipment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating DHL shipment: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tracking", response_model=List[NormalizedTrackingResponseSchema])
async def get_tracking(
    tracking: str = Query(..., description="Comma-separated list of tracking numbers"),
    carrier_api_id: int = Query(..., description="Carrier API ID for authentication"),
    dhl_tracking_service: IDhlTrackingService = Depends(get_dhl_tracking_service)
):
    """
    Get tracking information for DHL shipments
    
    Args:
        tracking: Comma-separated tracking numbers
        carrier_api_id: Carrier API ID for authentication
        dhl_tracking_service: DHL tracking service dependency
        
    Returns:
        List of normalized tracking responses
    """
    try:
        # Parse tracking numbers
        tracking_list = [tn.strip() for tn in tracking.split(",") if tn.strip()]
        
        if not tracking_list:
            raise HTTPException(status_code=400, detail="No tracking numbers provided")
        
        logger.info(f"Getting DHL tracking for {len(tracking_list)} shipments")
        
        result = await dhl_tracking_service.get_tracking(tracking_list, carrier_api_id)
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error getting DHL tracking: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting DHL tracking: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/debug-documents/{awb}")
async def debug_shipment_documents(
    awb: str,
    dhl_service: IDhlShipmentService = Depends(get_dhl_shipment_service)
):
    """
    Debug: Mostra tutti i documenti salvati per un AWB
    
    Args:
        awb: Air Waybill number della spedizione
        dhl_service: Dipendenza del servizio di spedizione DHL
        
    Returns:
        Lista dei documenti salvati
    """
    try:
        from src.repository.shipment_document_repository import ShipmentDocumentRepository
        
        # Cerca tutti i documenti per AWB
        document_repo = ShipmentDocumentRepository(dhl_service.shipment_request_repository._session)
        documents = document_repo.get_by_awb(awb)
        
        result = []
        for doc in documents:
            result.append({
                "id": doc.id,
                "awb": doc.awb,
                "type_code": doc.type_code,
                "file_path": doc.file_path,
                "size_bytes": doc.size_bytes,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            })
        
        return {
            "awb": awb,
            "documents_count": len(documents),
            "documents": result
        }
        
    except Exception as e:
        logger.error(f"Error debugging documents for AWB {awb}: {str(e)}")
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
async def cleanup_expired_documents():
    """
    Cleanup expired shipment documents and audit records
    
    Returns:
        Cleanup results with counts and memory freed
    """
    try:
        from src.core.container_config import get_configured_container
        from src.repository.interfaces.shipment_request_repository_interface import IShipmentRequestRepository
        from src.repository.interfaces.shipment_document_repository_interface import IShipmentDocumentRepository
        
        configured_container = get_configured_container()
        shipment_repo = configured_container.resolve(IShipmentRequestRepository)
        document_repo = configured_container.resolve(IShipmentDocumentRepository)
        
        # Cleanup expired audit records
        deleted_audit = shipment_repo.cleanup_expired()
        
        # POINT 1: Finding expired documents in shipment_documents table
        expired_documents = document_repo.get_expired_documents()
        
        logger.info(f"Found {len(expired_documents)} expired documents to cleanup")
        
        # TODO: Point 2 - Deleting files from filesystem
        # TODO: Point 3 - Removing database records
        # TODO: Point 4 - Calculating memory freed
        
        logger.info(f"Cleaned up {deleted_audit} expired audit records")
        
        return {
            "message": "Cleanup completed",
            "audit_records_deleted": deleted_audit,
            "expired_documents_found": len(expired_documents),
            "documents_deleted": 0,  # TODO: Implement document cleanup (points 2-4)
            "memory_freed_bytes": 0  # TODO: Calculate actual memory freed
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail="Cleanup failed")
