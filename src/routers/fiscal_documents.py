from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from src.database import get_db
from src.services.routers.auth_service import get_current_user
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.services.external.fatturapa_service import FatturaPAService
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

router = APIRouter(prefix="/api/v1/fiscal_documents", tags=["Fiscal Documents"])

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
    repo = get_fiscal_repository(db)
    invoices = repo.get_invoices_by_order(id_order)
    
    if not invoices:
        raise HTTPException(status_code=404, detail=f"Nessuna fattura trovata per ordine {id_order}")
    
    return invoices



# ==================== NOTE DI CREDITO ====================

@router.post("/credit-notes", response_model=CreditNoteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_credit_note(
    credit_note_data: CreditNoteCreateSchema,
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Crea una nota di credito per una fattura esistente
    
    ## 📋 Parametri principali
    
    - **`id_invoice`** (int, obbligatorio): ID della fattura da stornare
    - **`reason`** (string, obbligatorio): Motivo della nota di credito (max 500 caratteri)
    - **`is_partial`** (bool, default: false): Tipo di storno
    - **`is_electronic`** (bool, default: true): Se generare XML FatturaPA (TD04)
    - **`include_shipping`** (bool, default: true): Se includere spese di spedizione
    - **`items`** (array, opzionale): Articoli da stornare (obbligatorio se `is_partial=true`)
    
    ---
    
    ## 🔴 Nota di Credito TOTALE (`is_partial: false`)
    
    Storna l'intera fattura con tutti gli articoli. Include spese di spedizione solo se `include_shipping=true`.
    
    ### Body esempio (CON spese di spedizione):
    ```json
    {
      "id_invoice": 123,
      "reason": "Reso completo merce",
      "is_partial": false,
      "is_electronic": true,
      "include_shipping": true
    }
    ```
    
    ### Body esempio (SENZA spese di spedizione):
    ```json
    {
      "id_invoice": 123,
      "reason": "Reso merce - spedizione già stornata",
      "is_partial": false,
      "is_electronic": true,
      "include_shipping": false
    }
    ```
    
    ### Comportamento:
    - ✅ Storna TUTTI gli articoli della fattura
    - ✅ Include spese di spedizione (se `include_shipping=true`)
    - ✅ Include sconti generali
    - ❌ NON serve specificare `items`
    
    ---
    
    ## 🟡 Nota di Credito PARZIALE (`is_partial: true`)
    
    Storna solo alcuni articoli o quantità parziali. Può includere spese di spedizione se non già stornate.
    
    ### Body esempio (articoli SENZA spese):
    ```json
    {
      "id_invoice": 123,
      "reason": "Reso parziale - 2 articoli difettosi",
      "is_partial": true,
      "is_electronic": true,
      "include_shipping": false,
      "items": [
        {
          "id_order_detail": 456,
          "quantity": 2.0
        },
        {
          "id_order_detail": 457,
          "quantity": 1.0
        }
      ]
    }
    ```
    
    **Nota**: Il `unit_price` viene recuperato automaticamente dalla fattura originale.
    
    ### Body esempio (articoli CON spese):
    ```json
    {
      "id_invoice": 123,
      "reason": "Reso parziale + spedizione",
      "is_partial": true,
      "is_electronic": true,
      "include_shipping": true,
      "items": [
        {
          "id_order_detail": 456,
          "quantity": 2.0
        }
      ]
    }
    ```
    
    ### Comportamento:
    - ✅ Storna SOLO gli articoli specificati in `items`
    - ✅ Può stornare quantità parziali (es: 2 su 5)
    - ✅ Applica automaticamente sconti proporzionali
    - ✅ Include spese di spedizione (se `include_shipping=true` e non già stornate)
    - ❌ NON include sconti generali ordine
    
    ### Come trovare gli `id_order_detail`:
    ```
    GET /api/v1/fiscal-documents/{id_fiscal_document}/details-with-products
    ```
    
    ---
    
    ## ✅ Validazioni automatiche
    
    ### 1. Validazione fattura:
    - La fattura deve esistere e essere di tipo `invoice`
    - Se `is_electronic=true`: la fattura deve essere elettronica
    - Se `is_electronic=true`: l'indirizzo deve essere italiano (IT)
    
    ### 2. Validazione note di credito esistenti:
    - **Blocco nota totale duplicata**: Se esiste già una NC totale → Errore
    - **Articoli già stornati**: Verifica che gli articoli non siano già completamente stornati
    - **Spese già stornate**: Se `include_shipping=true` e spese già stornate → Errore
    
    ### 3. Validazione articoli (solo se `is_partial=true`):
    - Ogni `id_order_detail` DEVE essere nella fattura originale
    - La `quantity` DEVE essere ≤ quantità residua (fatturata - già stornata)
    - Se superi → Errore 400: "Quantità da stornare (X) superiore a quella residua (Y)"
    
    ### 4. Calcoli automatici:
    - **Sconti articolo**: Applicati proporzionalmente
    - **IVA**: Calcolata automaticamente per aliquota
    - **Totale**: Somma imponibile + IVA
    
    ---
    
    ## 📊 Differenze tra totale e parziale
    
    | Aspetto | is_partial=false | is_partial=true |
    |---------|------------------|-----------------|
    | Campo `items` | ❌ Non necessario | ✅ Obbligatorio |
    | Articoli stornati | Tutti | Solo quelli in items |
    | Spese spedizione | Opzionale (`include_shipping`) | Opzionale (`include_shipping`) |
    | Sconti ordine | ✅ Inclusi | ❌ Esclusi |
    
    ---
    
    ## 🔄 Workflow consigliato
    
    ### Per nota TOTALE:
    ```
    1. POST /credit-notes con is_partial=false
    2. Sistema storna automaticamente tutto
    ```
    
    ### Per nota PARZIALE:
    ```
    1. GET /fiscal-documents/{id}/details-with-products
    2. Identificare id_order_detail degli articoli da stornare
    3. POST /credit-notes con is_partial=true e items[]
    ```
    
    ---
    
    ## ⚠️ Errori comuni
    
    ### Errori fattura:
    - **400**: "Fattura non trovata" → `id_invoice` errato
    - **400**: "La fattura deve essere elettronica" → Fattura non elettronica con `is_electronic=true`
    - **400**: "Nota di credito elettronica solo per indirizzi italiani" → Indirizzo estero
    
    ### Errori note duplicate:
    - **400**: "Esiste già una nota di credito TOTALE" → Non puoi creare altre note dopo una totale
    
    ### Errori articoli:
    - **400**: "OrderDetail X non presente nella fattura" → `id_order_detail` non valido
    - **400**: "L'articolo X è già stato completamente stornato" → Articolo già stornato in note precedenti
    - **400**: "Quantità superiore alla quantità residua" → Stai provando a stornare più del disponibile
    
    ### Errori spese spedizione:
    - **400**: "Le spese di spedizione sono già state stornate" → Imposta `include_shipping=false`
    
    ---
    
    ## 📄 Output
    
    Restituisce il documento fiscale creato con:
    - `document_type`: "credit_note"
    - `tipo_documento_fe`: "TD04" (se elettronico)
    - `document_number`: Numero sequenziale (se elettronico)
    - `status`: "pending" (se elettronica) o "issued" (se non elettronica)
    - `is_partial`: true/false
    - `includes_shipping`: true/false (traccia se include spese)
    - `total_price_with_tax`: Importo totale stornato (IVA inclusa)
    - `id_fiscal_document_ref`: ID fattura di riferimento
    - `details[]`: Elenco articoli stornati
    
    ### Esempio risposta:
    ```json
    {
      "id_fiscal_document": 456,
      "document_type": "credit_note",
      "tipo_documento_fe": "TD04",
      "id_order": 789,
      "id_fiscal_document_ref": 123,
      "document_number": "00042",
      "status": "pending",
      "is_electronic": true,
      "credit_note_reason": "Reso parziale",
      "is_partial": true,
      "includes_shipping": false,
      "total_price_with_tax": 122.00,
      "date_add": "2025-10-10T10:30:00",
      "date_upd": "2025-10-10T10:30:00",
      "details": [...]
    }
    ```
    """
    repo = get_fiscal_repository(db)
    
    # Prepara items se parziale
    items = None
    if credit_note_data.is_partial and credit_note_data.items:
        items = [
            {
                'id_order_detail': item.id_order_detail,
                'quantity': item.quantity
            }
            for item in credit_note_data.items
        ]
    
    credit_note = repo.create_credit_note(
        id_invoice=credit_note_data.id_invoice,
        reason=credit_note_data.reason,
        is_partial=credit_note_data.is_partial,
        items=items,
        is_electronic=credit_note_data.is_electronic,
        include_shipping=credit_note_data.include_shipping
    )
    
    return credit_note


@router.get("/credit-notes/invoice/{id_invoice}", response_model=List[CreditNoteResponseSchema])
async def get_credit_notes_by_invoice(
    id_invoice: int = Path(..., gt=0, description="ID della fattura"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """Recupera tutte le note di credito di una fattura"""
    repo = get_fiscal_repository(db)
    credit_notes = repo.get_credit_notes_by_invoice(id_invoice)
    return credit_notes


# ==================== OPERAZIONI GENERICHE ====================

@router.get("/{id_fiscal_document}", response_model=FiscalDocumentResponseSchema)
async def get_fiscal_document(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """Recupera documento fiscale per ID (fattura o nota di credito)"""
    repo = get_fiscal_repository(db)
    doc = repo.get_fiscal_document_by_id(id_fiscal_document)
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
    
    return doc


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
    repo = get_fiscal_repository(db)
    success = repo.delete_fiscal_document(id_fiscal_document)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
    
    return None


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
    fatturapa_service = get_fatturapa_service(db)
    repo = get_fiscal_repository(db)
    
    # Genera XML
    result = fatturapa_service.generate_xml_from_fiscal_document(id_fiscal_document)
    
    if result['status'] == 'validation_error':
        # Restituisce errori di validazione dettagliati
        errors = result.get('errors', [])
        
        # Raggruppa errori per campo per evitare duplicati
        errors_by_field = {}
        for err in errors:
            field = err.get('field', 'Campo sconosciuto')
            if field not in errors_by_field:
                errors_by_field[field] = []
            errors_by_field[field].append({
                "message": err.get('message', 'Errore di validazione'),
                "rule": err.get('rule', 'unknown'),
                "value": err.get('value')
            })
        
        # Crea messaggio principale
        error_count = len(errors)
        main_message = f"Validazione XML FatturaPA fallita: {error_count} errore/i trovato/i"
        
        # Formatta errori in modo leggibile
        formatted_errors = []
        for field, field_errors in errors_by_field.items():
            for field_err in field_errors:
                formatted_errors.append({
                    "field": field,
                    "message": field_err["message"],
                    "rule": field_err["rule"],
                    "value": field_err["value"]
                })
        
        # Usa BaseApplicationException per formattare correttamente la risposta
        from src.core.exceptions import BaseApplicationException, ErrorCode
        from fastapi.responses import JSONResponse
        
        exc = BaseApplicationException(
            message=main_message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details={
                "error_count": error_count,
                "errors": formatted_errors
            },
            status_code=422
        )
        
        return JSONResponse(
            status_code=422,
            content=exc.to_dict()
        )
    
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


@router.patch("/{id_fiscal_document}/status", response_model=FiscalDocumentResponseSchema)
async def update_status(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    status_data: FiscalDocumentUpdateStatusSchema = Body(...),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """Aggiorna status di un documento fiscale"""
    repo = get_fiscal_repository(db)
    doc = repo.update_fiscal_document_status(
        id_fiscal_document=id_fiscal_document,
        status=status_data.status,
        upload_result=status_data.upload_result
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
    
    return doc

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
        

# ==================== GENERAZIONE PDF ====================

def _generate_pdf_with_fpdf(fiscal_document, order, invoice_address, delivery_address, 
                            details_with_products, payment_name, company_config, 
                            db, referenced_invoice=None) -> BytesIO:
    """
    DEPRECATED: Usa FiscalDocumentPDFService.generate_pdf()
    Questa funzione è mantenuta per compatibilità ma viene sostituita da FiscalDocumentPDFService
    """
    from src.services.pdf.fiscal_document_pdf_service import FiscalDocumentPDFService
    from io import BytesIO
    
    pdf_service = FiscalDocumentPDFService()
    pdf_bytes = pdf_service.generate_pdf(
        fiscal_document=fiscal_document,
        order=order,
        invoice_address=invoice_address,
        delivery_address=delivery_address,
        details_with_products=details_with_products,
        payment_name=payment_name,
        company_config=company_config,
        referenced_invoice=referenced_invoice,
        db=db
    )
    
    # Converte bytes in BytesIO per compatibilità
    pdf_buffer = BytesIO()
    pdf_buffer.write(pdf_bytes)
    pdf_buffer.seek(0)
    return pdf_buffer


@router.get("/{id_fiscal_document}/pdf")
async def generate_fiscal_document_pdf(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Genera PDF per documento fiscale (fattura o nota di credito)
    
    ## Processo:
    1. Recupera documento fiscale con ordine e indirizzi
    2. Recupera dettagli articoli
    3. Recupera configurazioni aziendali
    4. Genera HTML del documento
    5. Converte in PDF con WeasyPrint
    
    ## Output:
    - Content-Type: application/pdf
    - Content-Disposition: attachment con nome file
    
    ## Validazioni:
    - Se nota di credito senza riferimento fattura → 400
    - Se non ci sono dettagli → 404
    """
    from src.models.fiscal_document import FiscalDocument
    from src.models.fiscal_document_detail import FiscalDocumentDetail
    from src.models.order import Order
    from src.models.order_detail import OrderDetail
    from src.models.address import Address
    from src.models.payment import Payment
    from src.models.tax import Tax
    
    # Recupera documento fiscale
    fiscal_repo = get_fiscal_repository(db)
    fiscal_document = fiscal_repo.get_fiscal_document_by_id(id_fiscal_document)
    
    if not fiscal_document:
        raise HTTPException(status_code=404, detail=f"Documento fiscale {id_fiscal_document} non trovato")
    
    # Validazione: nota di credito deve avere riferimento
    if fiscal_document.document_type == 'credit_note' and not fiscal_document.id_fiscal_document_ref:
        raise HTTPException(
            status_code=400, 
            detail="Nota di credito senza riferimento a fattura. Impossibile generare PDF."
        )
    
    # Recupera ordine
    order = db.query(Order).filter(Order.id_order == fiscal_document.id_order).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Ordine {fiscal_document.id_order} non trovato")
    
    # Recupera indirizzi
    invoice_address = db.query(Address).filter(Address.id_address == order.id_address_invoice).first()
    delivery_address = db.query(Address).filter(Address.id_address == order.id_address_delivery).first()
    
    # Recupera dettagli documento
    details = db.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == id_fiscal_document
    ).all()
    
    if not details:
        raise HTTPException(
            status_code=404, 
            detail=f"Nessun articolo trovato nel documento {id_fiscal_document}. Impossibile generare PDF."
        )
    
    # Arricchisci dettagli con info prodotto e IVA
    details_with_products = []
    for detail in details:
        order_detail = db.query(OrderDetail).filter(
            OrderDetail.id_order_detail == detail.id_order_detail
        ).first()
        
        # Recupera IVA
        vat_rate = 0
        if order_detail and order_detail.id_tax:
            tax = db.query(Tax).filter(Tax.id_tax == order_detail.id_tax).first()
            if tax:
                vat_rate = tax.percentage
        
        details_with_products.append({
            'id_fiscal_document_detail': detail.id_fiscal_document_detail,
            'id_order_detail': detail.id_order_detail,
            'product_qty': detail.product_qty,
            'unit_price': detail.unit_price,
            'total_price_with_tax': detail.total_price_with_tax,
            'product_name': order_detail.product_name if order_detail else 'N/A',
            'product_reference': order_detail.product_reference if order_detail else 'N/A',
            'reduction_percent': order_detail.reduction_percent if order_detail else 0.0,
            'vat_rate': vat_rate
        })
    
    # Recupera metodo pagamento
    payment_name = None
    if order.id_payment:
        payment = db.query(Payment).filter(Payment.id_payment == order.id_payment).first()
        if payment:
            payment_name = payment.name
    
    # Recupera configurazioni azienda
    app_config_repo = AppConfigurationRepository(db)
    company_config = {}
    
    # Prova a recuperare configurazioni dalla categoria 'company_info'
    company_configs = app_config_repo.get_by_category('company_info')
    for config in company_configs:
        company_config[config.name] = config.value or ''
    
    # Fallback se non ci sono configurazioni
    if not company_config:
        company_config = {
            'company_name': 'Azienda',
            'company_vat': 'P.IVA',
            'company_address': 'Indirizzo',
            'company_city': 'Città',
            'company_pec': 'PEC',
            'company_sdi': 'SDI'
        }
    
    # Recupera fattura di riferimento per note di credito
    referenced_invoice = None
    if fiscal_document.document_type == 'credit_note' and fiscal_document.id_fiscal_document_ref:
        referenced_invoice = fiscal_repo.get_fiscal_document_by_id(fiscal_document.id_fiscal_document_ref)
    
    # Genera PDF
    pdf_buffer = _generate_pdf_with_fpdf(
        fiscal_document=fiscal_document,
        order=order,
        invoice_address=invoice_address,
        delivery_address=delivery_address,
        details_with_products=details_with_products,
        payment_name=payment_name,
        company_config=company_config,
        db=db,
        referenced_invoice=referenced_invoice
    )
    
    # Determina nome file
    doc_type = "nota-credito" if fiscal_document.document_type == 'credit_note' else "fattura"
    doc_number = fiscal_document.document_number or fiscal_document.internal_number or str(id_fiscal_document)
    filename = f"{doc_type}-{doc_number}.pdf"
    
    # Ritorna PDF con headers per forzare download
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
            "Content-Type": "application/pdf"
        }
    )
        
