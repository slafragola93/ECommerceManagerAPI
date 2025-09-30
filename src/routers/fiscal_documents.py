from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.auth import get_current_user
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.services.fatturapa_service import FatturaPAService
from src.schemas.fiscal_document_schema import (
    InvoiceCreateSchema,
    InvoiceResponseSchema,
    CreditNoteCreateSchema,
    CreditNoteResponseSchema,
    FiscalDocumentResponseSchema,
    FiscalDocumentListResponseSchema,
    FiscalDocumentUpdateStatusSchema,
    FiscalDocumentUpdateXMLSchema,
    FiscalDocumentDetailResponseSchema,
    FiscalDocumentDetailWithProductSchema
)

router = APIRouter(prefix="/api/v1/fiscal-documents", tags=["Fiscal Documents"])

# Dependencies
def get_fiscal_repository(db: Session = Depends(get_db)) -> FiscalDocumentRepository:
    return FiscalDocumentRepository(db)

def get_fatturapa_service(db: Session = Depends(get_db)) -> FatturaPAService:
    return FatturaPAService(db)

user_dependency = Depends(get_current_user)
db_dependency = Depends(get_db)


# ==================== FATTURE ====================

@router.post("/invoices", response_model=InvoiceResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreateSchema = Body(
        ...,
        examples={
            "fattura_elettronica": {
                "summary": "Fattura elettronica (indirizzo IT)",
                "description": "Crea una fattura elettronica. L'indirizzo deve essere italiano (id_country=1).",
                "value": {
                    "id_order": 12345,
                    "is_electronic": True
                }
            },
            "fattura_non_elettronica": {
                "summary": "Fattura non elettronica",
                "description": "Crea una fattura senza XML (per ordini esteri o non elettronici).",
                "value": {
                    "id_order": 12345,
                    "is_electronic": False
                }
            }
        }
    ),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Crea una nuova fattura per un ordine
    
    ## Regole:
    - L'ordine non deve avere già una fattura
    - Se `is_electronic=True`, l'indirizzo deve essere italiano (id_country=1)
    - Viene generato automaticamente un numero sequenziale per fatture elettroniche
    - Il tipo documento FatturaPA sarà TD01
    """
    try:
        repo = get_fiscal_repository(db)
        invoice = repo.create_invoice(
            id_order=invoice_data.id_order,
            is_electronic=invoice_data.is_electronic
        )
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/invoices/order/{id_order}", response_model=List[InvoiceResponseSchema])
async def get_invoices_by_order(
    id_order: int = Path(..., gt=0, description="ID dell'ordine"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera tutte le fatture di un ordine
    
    Un ordine può avere multiple fatture (es. fattura iniziale + integrazioni)
    """
    try:
        repo = get_fiscal_repository(db)
        invoices = repo.get_invoices_by_order(id_order)
        
        if not invoices:
            raise HTTPException(status_code=404, detail=f"Nessuna fattura trovata per ordine {id_order}")
        
        return invoices
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/{id_fiscal_document}/details", response_model=List[FiscalDocumentDetailResponseSchema])
async def get_fiscal_document_details(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera gli articoli (dettagli) di un documento fiscale
    
    ## Utilità:
    - Per **fatture**: Vedere quali articoli sono stati fatturati
    - Per **note di credito**: Vedere quali articoli sono stati stornati
    - Prima di creare una NC parziale: Vedere quali articoli sono disponibili per lo storno
    
    ## Response:
    Lista di FiscalDocumentDetail con:
    - id_order_detail: Riferimento all'articolo originale
    - quantity: Quantità fatturata/stornata
    - unit_price: Prezzo unitario
    - total_amount: Importo totale (con sconti, IVA esclusa)
    """
    try:
        from src.models.fiscal_document_detail import FiscalDocumentDetail
        from src.models.order_detail import OrderDetail
        
        repo = get_fiscal_repository(db)
        
        # Verifica che il documento esista
        doc = repo.get_fiscal_document_by_id(id_fiscal_document)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        # Recupera i dettagli
        details = db.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == id_fiscal_document
        ).all()
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Nessun articolo trovato nel documento {id_fiscal_document}")
        
        return details
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/{id_fiscal_document}/details-with-products", response_model=List[FiscalDocumentDetailWithProductSchema])
async def get_fiscal_document_details_with_products(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera gli articoli di un documento fiscale CON informazioni prodotto
    
    ## Rispetto a /details:
    - Questo endpoint include `product_name` e `product_reference`
    - Utile per mostrare una lista user-friendly degli articoli fatturati
    - Ideale prima di creare una nota di credito parziale
    
    ## Use Case:
    ```
    1. GET /fiscal-documents/1/details-with-products
    2. L'utente vede: "Prodotto XYZ - Qty: 3 - €300"
    3. Decide di stornare: id_order_detail=15, quantity=2
    4. POST /credit-notes con questi dati
    ```
    """
    try:
        from src.models.fiscal_document_detail import FiscalDocumentDetail
        from src.models.order_detail import OrderDetail
        
        repo = get_fiscal_repository(db)
        
        # Verifica che il documento esista
        doc = repo.get_fiscal_document_by_id(id_fiscal_document)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        # Recupera i dettagli con JOIN per ottenere info prodotto
        details_with_products = []
        
        details = db.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == id_fiscal_document
        ).all()
        
        for detail in details:
            # Recupera OrderDetail per info prodotto
            order_detail = db.query(OrderDetail).filter(
                OrderDetail.id_order_detail == detail.id_order_detail
            ).first()
            
            details_with_products.append({
                'id_fiscal_document_detail': detail.id_fiscal_document_detail,
                'id_fiscal_document': detail.id_fiscal_document,
                'id_order_detail': detail.id_order_detail,
                'quantity': detail.quantity,
                'unit_price': detail.unit_price,
                'total_amount': detail.total_amount,
                'product_name': order_detail.product_name if order_detail else None,
                'product_reference': order_detail.product_reference if order_detail else None
            })
        
        if not details_with_products:
            raise HTTPException(status_code=404, detail=f"Nessun articolo trovato nel documento {id_fiscal_document}")
        
        return details_with_products
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# ==================== NOTE DI CREDITO ====================

@router.post("/credit-notes", response_model=CreditNoteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_credit_note(
    credit_note_data: CreditNoteCreateSchema,
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Crea una nota di credito per una fattura
    
    ## Regole:
    - La fattura di riferimento deve esistere
    - Se `is_electronic=True`, la fattura deve essere elettronica e l'indirizzo italiano
    - Se `is_partial=True`, devi specificare gli articoli da stornare in `items`
    - Il tipo documento FatturaPA sarà TD04
    - Per note parziali, le quantità possono essere minori dell'originale
    """
    try:
        repo = get_fiscal_repository(db)
        
        # Prepara items se parziale
        items = None
        if credit_note_data.is_partial and credit_note_data.items:
            items = [
                {
                    'id_order_detail': item.id_order_detail,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price
                }
                for item in credit_note_data.items
            ]
        
        credit_note = repo.create_credit_note(
            id_invoice=credit_note_data.id_invoice,
            reason=credit_note_data.reason,
            is_partial=credit_note_data.is_partial,
            items=items,
            is_electronic=credit_note_data.is_electronic
        )
        
        return credit_note
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/credit-notes/invoice/{id_invoice}", response_model=List[CreditNoteResponseSchema])
async def get_credit_notes_by_invoice(
    id_invoice: int = Path(..., gt=0, description="ID della fattura"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """Recupera tutte le note di credito di una fattura"""
    try:
        repo = get_fiscal_repository(db)
        credit_notes = repo.get_credit_notes_by_invoice(id_invoice)
        return credit_notes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# ==================== OPERAZIONI GENERICHE ====================

@router.get("/{id_fiscal_document}", response_model=FiscalDocumentResponseSchema)
async def get_fiscal_document(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """Recupera documento fiscale per ID (fattura o nota di credito)"""
    try:
        repo = get_fiscal_repository(db)
        doc = repo.get_fiscal_document_by_id(id_fiscal_document)
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/", response_model=FiscalDocumentListResponseSchema)
async def get_fiscal_documents(
    page: int = Query(1, ge=1, description="Numero pagina"),
    limit: int = Query(100, ge=1, le=1000, description="Elementi per pagina"),
    document_type: Optional[str] = Query(None, description="Filtra per tipo (invoice, credit_note)"),
    is_electronic: Optional[bool] = Query(None, description="Filtra per elettronici/non elettronici"),
    status: Optional[str] = Query(None, description="Filtra per status"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera lista documenti fiscali con filtri
    
    ## Filtri disponibili:
    - `document_type`: 'invoice' o 'credit_note'
    - `is_electronic`: true/false
    - `status`: pending, generated, uploaded, sent, error
    """
    try:
        repo = get_fiscal_repository(db)
        skip = (page - 1) * limit
        
        documents = repo.get_fiscal_documents(
            skip=skip,
            limit=limit,
            document_type=document_type,
            is_electronic=is_electronic,
            status=status
        )
        
        return FiscalDocumentListResponseSchema(
            documents=documents,
            total=len(documents),
            page=page,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.delete("/{id_fiscal_document}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fiscal_document(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Elimina documento fiscale (solo se status=pending)
    
    ## Regole:
    - Solo documenti con status='pending' possono essere eliminati
    - Non è possibile eliminare fatture con note di credito collegate
    """
    try:
        repo = get_fiscal_repository(db)
        success = repo.delete_fiscal_document(id_fiscal_document)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


# ==================== GENERA XML ====================

@router.post("/{id_fiscal_document}/generate-xml", response_model=FiscalDocumentResponseSchema)
async def generate_xml(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Genera XML FatturaPA per documento fiscale
    
    ## Processo:
    1. Verifica che il documento sia elettronico (is_electronic=True)
    2. Verifica che l'indirizzo sia italiano
    3. Genera XML secondo specifiche FatturaPA
    4. Salva XML nel database
    5. Aggiorna status a 'generated'
    """
    try:
        fatturapa_service = get_fatturapa_service(db)
        repo = get_fiscal_repository(db)
        
        # Genera XML
        result = fatturapa_service.generate_xml_from_fiscal_document(id_fiscal_document)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result.get('message', 'Errore generazione XML'))
        
        # Aggiorna documento con XML
        doc = repo.update_fiscal_document_xml(
            id_fiscal_document=id_fiscal_document,
            filename=result['filename'],
            xml_content=result['xml_content']
        )
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.patch("/{id_fiscal_document}/status", response_model=FiscalDocumentResponseSchema)
async def update_status(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    status_data: FiscalDocumentUpdateStatusSchema = Body(...),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """Aggiorna status di un documento fiscale"""
    try:
        repo = get_fiscal_repository(db)
        doc = repo.update_fiscal_document_status(
            id_fiscal_document=id_fiscal_document,
            status=status_data.status,
            upload_result=status_data.upload_result
        )
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/{id_fiscal_document}/send-to-sdi", response_model=FiscalDocumentResponseSchema)
async def send_to_sdi(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    send_to_sdi: bool = Body(False, description="Se True, invia a Sistema di Interscambio (default: False = solo upload)"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Carica documento fiscale su FatturaPA (con opzione invio a SDI)
    
    ## Processo:
    1. Verifica che XML sia stato generato (status='generated')
    2. Upload Start - Ottiene URL Azure Blob
    3. Upload XML - Carica XML su Azure
    4. Upload Stop - Completa processo (opzionale invio SDI)
    5. Aggiorna status='uploaded' o 'sent'
    
    ## Parametri:
    - **send_to_sdi**: 
      - False (default) = Solo carica su FatturaPA (NON invia a SDI)
      - True = Carica E invia automaticamente a SDI
    
    ## Note:
    - Richiede XML già generato (chiamare prima /generate-xml)
    - Solo per documenti elettronici (is_electronic=True)
    """
    try:
        import json
        
        repo = get_fiscal_repository(db)
        fatturapa_service = get_fatturapa_service(db)
        
        # Recupera documento
        doc = repo.get_fiscal_document_by_id(id_fiscal_document)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
        
        # Verifica che sia elettronico
        if not doc.is_electronic:
            raise HTTPException(status_code=400, detail="Il documento non è elettronico, non può essere inviato a FatturaPA")
        
        # Verifica che XML sia stato generato
        if not doc.xml_content or not doc.filename:
            raise HTTPException(status_code=400, detail="XML non ancora generato. Chiamare prima /generate-xml")
        
        # 1. Upload Start
        name, complete_url = await fatturapa_service.upload_start(doc.filename)
        if not name or not complete_url:
            raise HTTPException(status_code=500, detail="UploadStart fallito")
        
        # 2. Upload XML
        upload_success = await fatturapa_service.upload_xml(complete_url, doc.xml_content)
        if not upload_success:
            raise HTTPException(status_code=500, detail="Upload XML fallito")
        
        # 3. Upload Stop
        stop_result = await fatturapa_service.upload_stop(name, send_to_sdi=send_to_sdi)
        
        # 4. Verifica risultato e aggiorna status
        if stop_result.get("status") == "error":
            # Aggiorna con status error
            repo.update_fiscal_document_status(
                id_fiscal_document=id_fiscal_document,
                status="error",
                upload_result=json.dumps(stop_result) if stop_result else None
            )
            # Lancia eccezione con dettagli errore
            error_message = stop_result.get("message", "Upload Stop fallito")
            raise HTTPException(status_code=500, detail=f"Errore upload a FatturaPA: {error_message}")
        
        # Success - aggiorna status
        final_status = "sent" if send_to_sdi else "uploaded"
        
        doc = repo.update_fiscal_document_status(
            id_fiscal_document=id_fiscal_document,
            status=final_status,
            upload_result=json.dumps(stop_result) if stop_result else None
        )
        
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")
