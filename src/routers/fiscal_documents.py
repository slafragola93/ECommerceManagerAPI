from typing import List, Optional, Union
from datetime import date, datetime, time
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from src.database import get_db
from src.services.routers.auth_service import get_current_user, require_permission
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.services.external.fatturapa_service import FatturaPAService
from src.routers.dependencies import get_fiscal_document_service
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.schemas.fiscal_document_schema import (
    InvoiceCreateSchema,
    InvoiceResponseSchema,
    CreditNoteCreateSchema,
    CreditNoteResponseSchema,
    FiscalDocumentResponseSchema,
    FiscalDocumentListResponseSchema,
    FiscalDocumentListFiltersSchema,
    FiscalDocumentUpdateStatusSchema,
    FiscalDocumentUpdateXMLSchema,
    FiscalDocumentDetailResponseSchema,
    FiscalDocumentDetailWithProductSchema,
    InvoiceExportFormatSchema,
    InvoiceExportFiltersSchema,
)
from src.services.pdf.fiscal_document_pdf_builder import build_fiscal_document_pdf_buffer

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
                "summary": "Fattura elettronica FatturaPA",
                "description": "Crea una fattura elettronica da trasmettere via SDI (cliente IT o UE/VIES).",
                "value": {
                    "id_order": 12345,
                }
            },
        }
    ),
    user: dict = user_dependency,
    fiscal_service: IFiscalDocumentService = Depends(get_fiscal_document_service),
    _: None = Depends(require_permission("fiscal_documents", "create")),
):
    """
    Crea una nuova fattura elettronica per un ordine
    
    ## Regole:
    - È consentito creare più fatture sullo stesso ordine (re-emissione / integrazioni)
    - Le fatture sono sempre elettroniche (`is_electronic=true`, tipo TD01)
    - L'indirizzo di fatturazione deve esistere (IT o UE estero/VIES)
    - Viene generato automaticamente un numero sequenziale FatturaPA
    """
    try:
        invoice = await fiscal_service.create_invoice(
            id_order=invoice_data.id_order,
            user=user,
        )
        return await fiscal_service.get_invoice_response_by_id(invoice.id_fiscal_document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/invoices/order/{id_order}", response_model=List[InvoiceResponseSchema])
async def get_invoices_by_order(
    id_order: int = Path(..., gt=0, description="ID dell'ordine"),
    user: dict = user_dependency,
    fiscal_service: IFiscalDocumentService = Depends(get_fiscal_document_service),
    _: None = Depends(require_permission("fiscal_documents", "read")),
):
    """
    Recupera tutte le fatture di un ordine
    
    Un ordine può avere multiple fatture (es. re-emissione, integrazioni).
    """
    invoices = await fiscal_service.get_invoices_by_order_response(id_order)

    if not invoices:
        raise HTTPException(status_code=404, detail=f"Nessuna fattura trovata per ordine {id_order}")

    return invoices


@router.get(
    "/invoices/export",
    status_code=status.HTTP_200_OK,
    summary="Export massivo lista fatture (Excel / ZIP XML)",
)
async def export_invoices(
    fmt: InvoiceExportFormatSchema = Query(
        InvoiceExportFormatSchema.XLSX,
        description="xlsx o xml (ZIP FatturaPA)",
    ),
    is_electronic: Optional[bool] = Query(None, description="Filtra per elettroniche/non elettroniche"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtra per status"),
    id_order: Optional[int] = Query(None, gt=0, description="Filtra per ordine"),
    id_customer: Optional[int] = Query(None, gt=0, description="Filtra per cliente"),
    delivery_country_iso: Optional[str] = Query(
        None,
        min_length=2,
        max_length=5,
        description="ISO paese consegna (stessa logica IVA ordine/corrispettivi)",
    ),
    date_add_from: Optional[date] = Query(None, description="Data emissione da (YYYY-MM-DD)"),
    date_add_to: Optional[date] = Query(None, description="Data emissione a (YYYY-MM-DD)"),
    user: dict = user_dependency,
    fiscal_service: IFiscalDocumentService = Depends(get_fiscal_document_service),
    _: None = Depends(require_permission("fiscal_documents", "read")),
):
    """
    Export massivo fatture.

    - **xlsx**: tabella riepilogativa (max 5000 righe). Filtri opzionali: status,
      is_electronic, id_order, id_customer, delivery_country_iso, date_add_from/to.
    - **xml**: ZIP FatturaPA (max 5000). **Solo filtri** `date_add_from`, `date_add_to`,
      `delivery_country_iso` (paese consegna). Status ed altri filtri query sono **ignorati**.
      Se l'XML non esiste viene generato automaticamente (senza vincoli di status).

    PDF singola fattura: `GET /{id_fiscal_document}/pdf`.
    """
    filters = InvoiceExportFiltersSchema(
        is_electronic=is_electronic if fmt != InvoiceExportFormatSchema.XML else None,
        status=status_filter if fmt != InvoiceExportFormatSchema.XML else None,
        id_order=id_order if fmt != InvoiceExportFormatSchema.XML else None,
        id_customer=id_customer if fmt != InvoiceExportFormatSchema.XML else None,
        delivery_country_iso=delivery_country_iso,
        date_add_from=date_add_from,
        date_add_to=date_add_to,
    )
    content, media_type, filename = await fiscal_service.export_invoices(
        filters, fmt.value
    )

    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



# ==================== NOTE DI CREDITO ====================

@router.post("/credit-notes", response_model=CreditNoteResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_credit_note(
    credit_note_data: CreditNoteCreateSchema,
    user: dict = user_dependency,
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "create")),
):
    """
    Crea una nota di credito elettronica per una fattura esistente
    
    Le note di credito sono sempre elettroniche (`is_electronic=true`, tipo TD04).
    
    ## 📋 Parametri principali
    
    - **`id_invoice`** (int, obbligatorio): ID della fattura da stornare
    - **`reason`** (string, obbligatorio): Motivo della nota di credito (max 500 caratteri)
    - **`is_partial`** (bool, default: false): Tipo di storno
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
      "include_shipping": true
    }
    ```
    
    ### Body esempio (SENZA spese di spedizione):
    ```json
    {
      "id_invoice": 123,
      "reason": "Reso merce - spedizione già stornata",
      "is_partial": false,
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
    - La fattura deve essere elettronica (`is_electronic=true`)
    - Indirizzo di fatturazione presente (IT o UE/VIES)
    
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
    - **400**: "La fattura deve essere elettronica" → Fattura legacy non elettronica
    - **400**: "Indirizzo di fatturazione mancante/non trovato" → Ordine senza indirizzo fattura valido
    
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
    - `tipo_documento_fe`: "TD04"
    - `document_number`: Numero sequenziale FatturaPA
    - `status`: "pending" (in attesa generazione XML)
    - `is_electronic`: sempre `true`
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
        include_shipping=credit_note_data.include_shipping
    )
    
    return credit_note


@router.get("/credit-notes/invoice/{id_invoice}", response_model=List[CreditNoteResponseSchema])
async def get_credit_notes_by_invoice(
    id_invoice: int = Path(..., gt=0, description="ID della fattura"),
    user: dict = user_dependency,
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "read")),
):
    """Recupera tutte le note di credito di una fattura"""
    repo = get_fiscal_repository(db)
    credit_notes = repo.get_credit_notes_by_invoice(id_invoice)
    return credit_notes


# ==================== OPERAZIONI GENERICHE ====================

@router.get(
    "/{id_fiscal_document}",
    response_model=Union[InvoiceResponseSchema, FiscalDocumentResponseSchema],
)
async def get_fiscal_document(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency,
    fiscal_service: IFiscalDocumentService = Depends(get_fiscal_document_service),
    _: None = Depends(require_permission("fiscal_documents", "read")),
):
    """Recupera documento fiscale per ID (fattura arricchita o nota di credito generica)"""
    repo = get_fiscal_repository(db)
    doc = repo.get_fiscal_document_by_id(id_fiscal_document)

    if not doc:
        raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")

    if doc.document_type == "invoice":
        return await fiscal_service.get_invoice_response_by_id(id_fiscal_document)

    return doc


@router.get("/", response_model=FiscalDocumentListResponseSchema)
async def get_fiscal_documents(
    page: int = Query(1, ge=1, description="Numero pagina"),
    limit: int = Query(100, ge=1, le=1000, description="Elementi per pagina"),
    document_type: Optional[str] = Query(None, description="Filtra per tipo (invoice, credit_note)"),
    is_electronic: Optional[bool] = Query(None, description="Filtra per elettronici/non elettronici"),
    status: Optional[str] = Query(None, description="Filtra per status"),
    delivery_country_iso: Optional[str] = Query(
        None,
        min_length=2,
        max_length=5,
        description="ISO paese consegna ordine (stessa logica export/corrispettivi)",
    ),
    date_add_from: Optional[date] = Query(None, description="Data emissione da (YYYY-MM-DD)"),
    date_add_to: Optional[date] = Query(None, description="Data emissione a (YYYY-MM-DD)"),
    user: dict = user_dependency,
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "read")),
):
    """
    Recupera lista documenti fiscali con filtri

    ## Filtri disponibili:
    - `document_type`: 'invoice' o 'credit_note'
    - `is_electronic`: true/false
    - `status`: pending, generated, uploaded, sent, error
    - `delivery_country_iso`: ISO paese **consegna** dell'ordine collegato
    - `date_add_from` / `date_add_to`: range data emissione (`date_add`)
    """
    filters = FiscalDocumentListFiltersSchema(
        document_type=document_type,
        is_electronic=is_electronic,
        status=status,
        delivery_country_iso=delivery_country_iso,
        date_add_from=date_add_from,
        date_add_to=date_add_to,
        page=page,
        limit=limit,
    )
    date_from = (
        datetime.combine(filters.date_add_from, time.min)
        if filters.date_add_from
        else None
    )
    date_to = (
        datetime.combine(filters.date_add_to, time.max)
        if filters.date_add_to
        else None
    )

    repo = get_fiscal_repository(db)
    skip = (filters.page - 1) * filters.limit

    total = repo.count_fiscal_documents(
        document_type=filters.document_type,
        is_electronic=filters.is_electronic,
        status=filters.status,
        delivery_country_iso=filters.delivery_country_iso,
        date_add_from=date_from,
        date_add_to=date_to,
    )
    documents = repo.get_fiscal_documents(
        skip=skip,
        limit=filters.limit,
        document_type=filters.document_type,
        is_electronic=filters.is_electronic,
        status=filters.status,
        delivery_country_iso=filters.delivery_country_iso,
        date_add_from=date_from,
        date_add_to=date_to,
    )

    return FiscalDocumentListResponseSchema(
        documents=documents,
        total=total,
        page=filters.page,
        limit=filters.limit,
    )


@router.delete("/{id_fiscal_document}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fiscal_document(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "delete")),
):
    """
    Elimina documento fiscale.

    ## Regole:
    - **Resi** (`return`): eliminabili in qualsiasi stato
    - **Fatture / note di credito**: solo se `status='pending'`
    - Non è possibile eliminare fatture con note di credito collegate
    """
    repo = get_fiscal_repository(db)
    try:
        success = repo.delete_fiscal_document(id_fiscal_document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Documento {id_fiscal_document} non trovato")
    
    return None


# ==================== GENERA XML ====================

@router.post("/{id_fiscal_document}/generate-xml", response_model=FiscalDocumentResponseSchema)
async def generate_xml(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "update")),
):
    """
    Genera XML FatturaPA per documento fiscale
    
    ## Processo:
    1. Verifica che il documento sia elettronico (is_electronic=True)
    2. Verifica che l'indirizzo di fatturazione esista (IT o UE estero/VIES)
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
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "update")),
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
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "update")),
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

@router.get("/{id_fiscal_document}/pdf")
async def generate_fiscal_document_pdf(
    id_fiscal_document: int = Path(..., gt=0, description="ID del documento fiscale"),
    user: dict = user_dependency,
    db: Session = db_dependency,
    _: None = Depends(require_permission("fiscal_documents", "read")),
):
    """
    Genera PDF pre-fattura / nota di credito (layout elettronew + i18n).

    ## Processo:
    1. Recupera documento fiscale con ordine e indirizzi
    2. Recupera dettagli articoli e aliquote IVA
    3. Recupera `company_info` e `invoice_pdf` (dicitura NOTE)
    4. Genera PDF con fpdf2 (etichette IT/FR/DE/ES/EN in base al paese cliente)

    ## Output:
    - Content-Type: application/pdf
    - Content-Disposition: attachment con nome file

    ## Validazioni:
    - Se nota di credito senza riferimento fattura → 400
    - Se non ci sono dettagli → 404
    """
    pdf_buffer, filename = build_fiscal_document_pdf_buffer(db, id_fiscal_document)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
            "Content-Type": "application/pdf",
        },
    )
        
