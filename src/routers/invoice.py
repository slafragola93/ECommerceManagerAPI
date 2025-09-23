from fastapi import APIRouter, HTTPException, Query, Depends, Path, status
from sqlalchemy.orm import Session
from typing import Optional

from src.database import get_db
from src.services.auth import get_current_user
from src.services.wrap import check_authentication
from src.services.auth import authorize
from src.repository.invoice_repository import InvoiceRepository
from src.services.fatturapa_service import FatturaPAService
from src.schemas.invoice_schema import (
    InvoiceResponseSchema, 
    AllInvoicesResponseSchema,
    InvoiceIssuingRequestSchema,
    InvoiceIssuingResponseSchema,
    InvoiceXMLResponseSchema
)
from src.routers.dependencies import MAX_LIMIT, LIMIT_DEFAULT

router = APIRouter(
    prefix="/api/v1/invoices",
    tags=['Invoice']
)


def get_invoice_repository(db: Session = Depends(get_db)) -> InvoiceRepository:
    return InvoiceRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllInvoicesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_all_invoices(
    user=Depends(get_current_user),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repository),
    order_ids: Optional[str] = Query(None, description="ID degli ordini separati da virgola"),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Recupera una lista di fatture filtrata per ordini.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    - `order_ids`: ID degli ordini, separati da virgola
    - `page`: Pagina corrente per la paginazione
    - `limit`: Numero di record per pagina
    """
    invoices = invoice_repo.get_all(order_ids=order_ids, page=page, limit=limit)
    
    if not invoices:
        raise HTTPException(status_code=404, detail="Nessuna fattura trovata")
    
    total_count = invoice_repo.get_count(order_ids=order_ids)
    
    results = [invoice_repo.formatted_output(invoice) for invoice in invoices]
    
    return {
        "invoices": results,
        "total": total_count,
        "page": page,
        "limit": limit
    }


@router.get("/{invoice_id}", status_code=status.HTTP_200_OK, response_model=InvoiceResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_invoice_by_id(
    user=Depends(get_current_user),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repository),
    invoice_id: int = Path(gt=0)
):
    """
    Recupera una fattura per ID.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    - `invoice_id`: ID della fattura da recuperare
    """
    invoice = invoice_repo.get_by_id(invoice_id)
    
    if invoice is None:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    
    return invoice_repo.formatted_output(invoice)


@router.get("/order/{order_id}", status_code=status.HTTP_200_OK, response_model=AllInvoicesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_invoices_by_order(
    user=Depends(get_current_user),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repository),
    order_id: int = Path(gt=0),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Recupera tutte le fatture per un ordine specifico.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    - `order_id`: ID dell'ordine
    - `page`: Pagina corrente per la paginazione
    - `limit`: Numero di record per pagina
    """
    invoices = invoice_repo.get_all(order_ids=str(order_id), page=page, limit=limit)
    
    if not invoices:
        raise HTTPException(status_code=404, detail=f"Nessuna fattura trovata per l'ordine {order_id}")
    
    total_count = invoice_repo.get_count(order_ids=str(order_id))
    
    results = [invoice_repo.formatted_output(invoice) for invoice in invoices]
    
    return {
        "invoices": results,
        "total": total_count,
        "page": page,
        "limit": limit
    }


@router.post("/{order_id}/{iso_code}/invoice_issuing", 
             status_code=status.HTTP_201_CREATED, 
             response_model=InvoiceIssuingResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['C'])
async def issue_invoice(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    order_id: int = Path(gt=0),
    iso_code: str = Path(min_length=2, max_length=2),
    request_data: InvoiceIssuingRequestSchema = None
):
    """
    Genera e carica una fattura FatturaPA per un ordine.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    - `order_id`: ID dell'ordine per cui generare la fattura
    - `iso_code`: Codice ISO del paese (es: IT, FR, DE)
    - `request_data`: Dati aggiuntivi per l'emissione (opzionale)
    """
    try:
        # Inizializza il servizio FatturaPA
        fatturapa_service = FatturaPAService(db)
        
        # Genera e carica la fattura
        result = await fatturapa_service.generate_and_upload_invoice(
            order_id=order_id,
            iso_code=iso_code
        )
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=400, 
                detail=f"Errore nella generazione fattura: {result['message']}"
            )
        
        return InvoiceIssuingResponseSchema(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore interno del server: {str(e)}"
        )


@router.get("/events/pool", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['R'])
async def get_fatturapa_events(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Recupera gli eventi dal pool FatturaPA.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    """
    try:
        fatturapa_service = FatturaPAService(db)
        events = await fatturapa_service.get_events()
        
        return events
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero eventi: {str(e)}"
        )


@router.post("/verify", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['R'])
async def verify_fatturapa_connection(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica la connessione con l'API FatturaPA.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    """
    try:
        fatturapa_service = FatturaPAService(db)
        is_connected = await fatturapa_service.verify_api()
        
        if is_connected:
            return {"status": "success", "message": "Connessione API FatturaPA verificata"}
        else:
            return {"status": "error", "message": "Connessione API FatturaPA fallita"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella verifica connessione: {str(e)}"
        )


@router.post("/{order_id}/generate-xml", 
             status_code=status.HTTP_200_OK,
             response_model=InvoiceXMLResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['R'])
async def generate_invoice_xml(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    order_id: int = Path(gt=0)
):
    """
    Genera solo l'XML FatturaPA per un ordine senza fare l'upload.
    Utile per test, preview o generazione offline.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    - `order_id`: ID dell'ordine per cui generare l'XML
    """
    try:
        # Inizializza il servizio FatturaPA
        fatturapa_service = FatturaPAService(db)
        
        # Recupera dati ordine
        order_data = fatturapa_service._get_order_data(order_id)
        order_details = fatturapa_service._get_order_details(order_id)
        
        if not order_details:
            raise HTTPException(
                status_code=404, 
                detail=f"Nessun dettaglio ordine trovato per l'ordine {order_id}"
            )
        
        # Genera numero documento sequenziale
        document_number = fatturapa_service._get_next_document_number()
        
        # Genera XML
        xml_content = fatturapa_service._generate_xml(order_data, order_details, document_number)
        
        # Genera nome file
        filename = f"{fatturapa_service.vat_number}_{document_number}.xml"
        
        return {
            "status": "success",
            "message": "XML generato con successo",
            "order_id": order_id,
            "document_number": document_number,
            "filename": filename,
            "xml_content": xml_content,
            "xml_size": len(xml_content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione XML: {str(e)}"
        )


@router.post("/{order_id}/download-xml", 
             status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'FATTURAZIONE'], permissions_required=['R'])
async def download_invoice_xml(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    order_id: int = Path(gt=0)
):
    """
    Genera e scarica l'XML FatturaPA come file per un ordine.
    
    Parametri:
    - `user`: Dipendenza dell'utente autenticato
    - `order_id`: ID dell'ordine per cui generare l'XML
    """
    try:
        # Inizializza il servizio FatturaPA
        fatturapa_service = FatturaPAService(db)
        
        # Recupera dati ordine
        order_data = fatturapa_service._get_order_data(order_id)
        order_details = fatturapa_service._get_order_details(order_id)
        
        if not order_details:
            raise HTTPException(
                status_code=404, 
                detail=f"Nessun dettaglio ordine trovato per l'ordine {order_id}"
            )
        
        # Genera numero documento sequenziale
        document_number = fatturapa_service._get_next_document_number()
        
        # Genera XML
        xml_content = fatturapa_service._generate_xml(order_data, order_details, document_number)
        
        # Genera nome file
        filename = f"{fatturapa_service.vat_number}_{document_number}.xml"
        
        # Restituisce il file XML come download
        from fastapi.responses import Response
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/xml; charset=utf-8"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione XML: {str(e)}"
        )