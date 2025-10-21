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
    - `total_amount`: Importo totale stornato (IVA inclusa)
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
      "total_amount": 122.00,
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
    Genera PDF del documento fiscale usando fpdf2
    
    Args:
        fiscal_document: FiscalDocument (fattura o nota di credito)
        order: Order collegato
        invoice_address: Address di fatturazione
        delivery_address: Address di consegna
        details_with_products: Lista di dettagli con info prodotto
        payment_name: Nome metodo di pagamento
        company_config: Configurazioni aziendali
        referenced_invoice: FiscalDocument di riferimento (per note di credito)
    
    Returns:
        BytesIO: Buffer contenente il PDF
    """
    from datetime import datetime
    from fpdf import FPDF
    # Inizializza PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Determina tipo documento
    is_credit_note = fiscal_document.document_type == 'credit_note'
    doc_title = "NOTA DI CREDITO" if is_credit_note else "FATTURA"
    doc_number = fiscal_document.document_number or fiscal_document.internal_number or "N/A"
    doc_date = fiscal_document.date_add.strftime("%d/%m/%Y") if fiscal_document.date_add else ""
    
    # Logo aziendale (se esiste)
    import os
    company_logo = company_config.get('company_logo', 'media/logos/logo.png')
    if company_logo and os.path.exists(company_logo):
        try:
            pdf.image(company_logo, x=10, y=8, w=40)
        except:
            pass  # Se il logo non è leggibile, continua senza
    
    # Header - Titolo documento (spostato a destra se c'è logo)
    pdf.set_xy(120, 10)
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f"{doc_title} n. {doc_number}", 0, 1, 'R')
    pdf.set_xy(120, 17)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 7, f"Data: {doc_date}", 0, 1, 'R')
    
    # Riferimento fattura per note di credito
    if is_credit_note and referenced_invoice:
        ref_number = referenced_invoice.document_number or referenced_invoice.internal_number or "N/A"
        ref_date = referenced_invoice.date_add.strftime("%d/%m/%Y") if referenced_invoice.date_add else ""
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 5, f"A storno di FATTURA n. {ref_number} del {ref_date}", 0, 1, 'C')
    
    pdf.ln(5)
    
    # Configurazioni azienda (recuperate da app_configuration)
    company_name = company_config.get('company_name')
    company_address = company_config.get('address')
    company_postal_code = company_config.get('postal_code')
    company_city = company_config.get('city')
    company_province = company_config.get('province')
    company_city_full = f"{company_postal_code} - {company_city} ({company_province})"
    company_vat = company_config.get('vat_number')
    company_cf = company_config.get('fiscal_code')
    company_iban = company_config.get('iban')
    company_bic = company_config.get('bic_swift',)
    company_pec = company_config.get('pec', '')
    company_sdi = company_config.get('sdi_code')
    
    # Box Venditore e Cliente (due colonne)
    col_width = 95
    y_start = pdf.get_y()
    
    # VENDITORE (colonna sinistra)
    pdf.set_xy(10, y_start)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(col_width, 6, 'VENDITORE', 1, 0)
    pdf.ln()
    pdf.set_font('Arial', '', 8)
    seller_info = f"{company_name or ''}\n{company_address or ''}\n{company_city_full or ''}\n"
    
    # P.IVA e C.F. solo se presenti
    vat_cf_line = []
    if company_vat:
        vat_cf_line.append(f"P.I. {company_vat}")
    if company_cf:
        vat_cf_line.append(f"C.F. {company_cf}")
    if vat_cf_line:
        seller_info += " - ".join(vat_cf_line) + "\n"
    
    if company_iban:
        seller_info += f"IBAN {company_iban}\n"
    if company_bic:
        seller_info += f"BIC/SWIFT {company_bic}\n"
    if company_pec:
        seller_info += f"PEC: {company_pec}\n"
    if company_sdi:
        seller_info += f"SDI: {company_sdi}"
    
    pdf.multi_cell(col_width, 4, seller_info, 1)
    
    # CLIENTE (colonna destra)
    y_end_seller = pdf.get_y()
    pdf.set_xy(10 + col_width, y_start)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(col_width, 6, 'CLIENTE', 1, 0)
    pdf.ln()
    pdf.set_xy(10 + col_width, y_start + 6)
    
    # Intestatario cliente
    if invoice_address:
        customer_name = invoice_address.company if invoice_address.company else f"{invoice_address.firstname or ''} {invoice_address.lastname or ''}".strip()
        customer_info = f"{customer_name}\n" if customer_name else ""
        
        # Indirizzo solo se presente
        if invoice_address.address1:
            customer_info += f"{invoice_address.address1 or ''} {invoice_address.address2 or ''}".strip() + "\n"
        
        # Città solo se presente
        city_line = f"{invoice_address.postcode or ''} {invoice_address.city or ''}".strip()
        if invoice_address.state:
            city_line += f" ({invoice_address.state})"
        if city_line.strip():
            customer_info += city_line.strip() + "\n"
        
        # P.IVA/CF solo se presenti
        if invoice_address.vat:
            customer_info += f"P.IVA/CF: {invoice_address.vat}\n"
        elif invoice_address.dni:
            customer_info += f"Cod. Fiscale: {invoice_address.dni}\n"
        
        # PEC solo se presente
        if invoice_address.pec:
            customer_info += f"PEC: {invoice_address.pec}\n"
        
        # SDI o IPA solo se presenti
        if invoice_address.sdi:
            customer_info += f"SDI: {invoice_address.sdi}"
        elif invoice_address.ipa:
            customer_info += f"IPA: {invoice_address.ipa}"
        
        # Se non c'è nessuna informazione, mostra N/A
        if not customer_info.strip():
            customer_info = "N/A"
    else:
        customer_info = "N/A"
    
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(col_width, 5, customer_info, 1)
    y_end_customer = pdf.get_y()
    
    # Posiziona dopo la colonna più lunga
    pdf.set_y(max(y_end_seller, y_end_customer))
    pdf.ln(3)
    
    # Box Consegna (se presente)
    if delivery_address:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, 'DESTINAZIONE MERCE', 1, 1)
        pdf.set_font('Arial', '', 9)
        delivery_name = delivery_address.company if delivery_address.company else f"{delivery_address.firstname or ''} {delivery_address.lastname or ''}".strip()
        delivery_info = f"{delivery_name}\n"
        delivery_info += f"{delivery_address.address1 or ''} {delivery_address.address2 or ''}".strip() + "\n"
        delivery_info += f"{delivery_address.postcode or ''} {delivery_address.city or ''} ({delivery_address.state or ''})".strip()
        pdf.multi_cell(0, 5, delivery_info, 1)
        pdf.ln(3)
    
    # Riferimento ordine
    if order and order.reference:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, f"Riferimento ordine: {order.reference}", 0, 1)
        pdf.ln(2)
    
    # Tabella articoli - Header (IVA spostata prima del Totale)
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(224, 224, 224)
    pdf.cell(30, 6, 'Codice', 1, 0, 'L', True)
    pdf.cell(60, 6, 'Descrizione', 1, 0, 'L', True)
    pdf.cell(15, 6, 'Qta', 1, 0, 'R', True)
    pdf.cell(25, 6, 'Prezzo No IVA', 1, 0, 'R', True)
    pdf.cell(15, 6, 'Sc.%', 1, 0, 'C', True)
    pdf.cell(20, 6, 'IVA', 1, 0, 'C', True)
    pdf.cell(25, 6, 'Totale', 1, 1, 'R', True)
    
    # Tabella articoli - Righe
    pdf.set_font('Arial', '', 8)
    subtotal = 0.0  # Somma dei "Prezzo No IVA" (total_amount)
    total_with_vat_sum = 0.0  # Somma dei "Totale" (con IVA)
    total_quantity = 0
    total_weight = 0.0
    
    for detail in details_with_products:
        code = detail.get('product_reference', '')[:15]  # Trunca se troppo lungo
        description = detail.get('product_name', '')[:30]
        quantity = detail.get('quantity', 0)
        unit_price = detail.get('unit_price', 0.0)  # Prezzo unitario senza IVA (già scontato)
        total_amount = detail.get('total_amount', 0.0)  # Totale riga senza IVA (già scontato)
 
        reduction_percent = detail.get('reduction_percent', 0.0)  # Solo a scopo informativo
        vat_rate = detail.get('vat_rate', 0)
        
        # NOTA: total_amount è già comprensivo dello sconto applicato
        # Lo sconto viene mostrato solo come informazione, NON viene ricalcolato
        # Calcola il totale con IVA: total_amount (già scontato) * (1 + IVA%)
        vat_multiplier = 1 + (vat_rate / 100.0) if vat_rate else 1.0
        total_with_vat = total_amount * vat_multiplier
        
        pdf.cell(30, 5, code, 1, 0, 'L')
        pdf.cell(60, 5, description, 1, 0, 'L')
        pdf.cell(15, 5, f"{quantity:.0f}", 1, 0, 'R')
        pdf.cell(25, 5, f"{unit_price:.2f} EUR", 1, 0, 'R')
        pdf.cell(15, 5, f"{reduction_percent:.0f}%" if reduction_percent > 0 else "-", 1, 0, 'C')
        pdf.cell(20, 5, f"{vat_rate}%" if vat_rate else "-", 1, 0, 'C')
        pdf.cell(25, 5, f"{total_with_vat:.2f} EUR", 1, 1, 'R')
        
        # Somma per Imp. Merce / Merce netta (no IVA)
        subtotal += total_amount
        # Somma per Merce lorda (con IVA)
        total_with_vat_sum += total_with_vat
        total_quantity += quantity
    
    pdf.ln(3)
    
    # Sezione Info Spedizione e Riepilogo
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(0, 5, 'INFORMAZIONI SPEDIZIONE E RIEPILOGO', 0, 1, 'L')
    pdf.ln(2)
    
    # Box con info spedizione (3 colonne)
    y_shipping = pdf.get_y()
    col_w = 63
    
    # Colonna 1
    pdf.set_xy(10, y_shipping)
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(col_w, 4, 'Tot. Quant.', 1, 0, 'L')
    pdf.cell(col_w, 4, 'Peso (Kg)', 1, 0, 'L')
    pdf.cell(col_w, 4, 'Colli', 1, 1, 'L')
    
    # Valori shipping
    total_weight_kg = order.total_weight if order and order.total_weight else 0.0
    pdf.set_font('Arial', '', 8)
    pdf.cell(col_w, 4, str(int(total_quantity)), 1, 0, 'C')
    pdf.cell(col_w, 4, f"{total_weight_kg:.3f}", 1, 0, 'C')
    pdf.cell(col_w, 4, '1', 1, 1, 'C')
    
    pdf.ln(2)
    
    # Porto, Causale, Inizio trasporto
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(col_w, 4, 'Porto', 1, 0, 'L')
    pdf.cell(col_w, 4, 'Causale trasporto', 1, 0, 'L')
    pdf.cell(col_w, 4, 'Inizio trasporto', 1, 1, 'L')
    pdf.set_font('Arial', '', 8)
    pdf.cell(col_w, 4, '-', 1, 0, 'C')
    pdf.cell(col_w, 4, '-', 1, 0, 'C')
    pdf.cell(col_w, 4, '-', 1, 1, 'C')
    
    pdf.ln(3)
    
    # Tabella Riepilogo IVA e Totali
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(0, 5, 'RIEPILOGO IVA E TOTALI', 0, 1, 'L')
    pdf.ln(1)
    
    # Header tabella riepilogo
    pdf.set_font('Arial', 'B', 8)
    pdf.set_fill_color(224, 224, 224)
    pdf.cell(25, 5, 'Aliquota', 1, 0, 'C', True)
    pdf.cell(35, 5, 'Imp. Merce', 1, 0, 'R', True)
    pdf.cell(35, 5, 'Imp. Spese', 1, 0, 'R', True)
    pdf.cell(35, 5, 'Tot. IVA', 1, 0, 'R', True)
    pdf.cell(60, 5, '', 0, 1)  # Spazio per i totali a destra
    
    # Calcolo spese trasporto dalla tabella shipments
    shipping_cost = 0.0
    shipping_cost_with_vat = 0.0
    shipping_vat_percentage = 0
    
    if order and order.shipments:
        # Recupera il costo della spedizione dalla relazione shipments
        shipping_cost = order.shipments.price_tax_excl
        
        # Recupera la percentuale IVA dalla tabella Tax usando il repository
        if order.shipments.id_tax:
            from src.repository.tax_repository import TaxRepository
            tax_repo = TaxRepository(db)
            shipping_vat_percentage = tax_repo.get_percentage_by_id(order.shipments.id_tax)
            
            if shipping_vat_percentage:
                # Calcola il totale con IVA applicando la percentuale
                shipping_cost_with_vat = shipping_cost * (1 + shipping_vat_percentage / 100.0)
            else:
                # Fallback: usa il valore già presente
                shipping_cost_with_vat = order.shipments.price_tax_incl if order.shipments.price_tax_incl else 0.0
        else:
            shipping_cost_with_vat = order.shipments.price_tax_incl if order.shipments.price_tax_incl else 0.0
    
    
    # Calcola totale documento
    total_imponibile = fiscal_document.total_amount / (1 + (details_with_products[0]['vat_rate'] / 100.0))

    total_doc = fiscal_document.total_amount
    totale_imponibile = total_doc / (1 + (details_with_products[0]['vat_rate'] / 100.0))
    total_vat = total_doc - totale_imponibile
    
    # Riga IVA (assumiamo 22% come nel tuo esempio)
    pdf.set_font('Arial', '', 8)
    pdf.cell(25, 5, '22%', 1, 0, 'C')
    pdf.cell(35, 5, f"{subtotal:.2f}", 1, 0, 'R')
    pdf.cell(35, 5, f"{shipping_cost:.2f}", 1, 0, 'R')
    pdf.cell(35, 5, f"{total_vat:.2f}", 1, 0, 'R')
    
    # Colonna destra - Totali dettagliati
    pdf.set_xy(140, pdf.get_y())
    pdf.set_font('Arial', 'B', 8)
    shipping_label = f'Spese trasporto'
    if shipping_vat_percentage:
        shipping_label += f' (+{shipping_vat_percentage}% IVA)'
    pdf.cell(35, 5, shipping_label, 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    # Mostra il totale con IVA delle spese di trasporto
    pdf.cell(25, 5, f"{shipping_cost_with_vat:.2f}", 0, 1, 'R')
    
    pdf.ln(5)
    
    # Blocco totali finali (2 colonne)
    y_totals = pdf.get_y()
    
    # Colonna sinistra
    pdf.set_xy(10, y_totals)
    pdf.set_font('Arial', 'B', 8)
    
    # Merce netta = Somma dei "Prezzo No IVA" (subtotal è già corretto)
    # Merce lorda = Somma dei "Totale" (con IVA)
    merce_lorda = total_with_vat_sum
    
    pdf.cell(45, 5, 'Merce netta', 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    pdf.cell(25, 5, f"{subtotal:.2f}", 0, 1, 'R')
    
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 5, 'Totale imponibile', 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    # total_imponibile già calcolato sopra: subtotal + shipping_cost
    pdf.cell(25, 5, f"{total_imponibile:.2f}", 0, 1, 'R')
    
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 5, 'Spese incasso', 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    pdf.cell(25, 5, '0,00', 0, 1, 'R')
    
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 5, 'Merce lorda', 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    pdf.cell(25, 5, f"{merce_lorda:.2f}", 0, 1, 'R')
    
    # Colonna destra
    pdf.set_xy(130, y_totals)
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 5, 'Totale IVA', 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    pdf.cell(25, 5, f"{total_vat:.2f}", 0, 1, 'R')
    
    pdf.set_xy(130, pdf.get_y())
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(45, 5, 'Spese varie', 0, 0, 'L')
    pdf.set_font('Arial', '', 8)
    pdf.cell(25, 5, '0,00', 0, 1, 'R')
    
    # Totale documento (evidenziato)
    pdf.ln(2)
    pdf.set_xy(130, pdf.get_y())
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(45, 8, 'Totale documento', 0, 0, 'L')
    pdf.cell(25, 8, f"{total_doc:.2f} EUR", 0, 1, 'R')
    
    pdf.ln(5)
    
    pdf.ln(3)
    
    # Sezione Pagamento e Scadenze
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(95, 5, 'Pagamento', 1, 0, 'L')
    pdf.cell(95, 5, 'Scadenze', 1, 1, 'L')
    
    pdf.set_font('Arial', '', 9)
    pdf.cell(95, 5, payment_name if payment_name else '-', 1, 0, 'L')
    pdf.cell(95, 5, '', 1, 1, 'L')
    
    pdf.ln(2)
    
    # Firma trasporto
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(63, 5, 'Incaricato del trasporto', 1, 0, 'L')
    pdf.cell(63, 5, 'Aspetto esteriore dei beni', 1, 0, 'L')
    pdf.cell(64, 5, '', 0, 1)
    
    pdf.set_font('Arial', '', 8)
    pdf.cell(63, 8, '', 1, 0, 'L')
    pdf.cell(63, 8, '', 1, 1, 'L')
    
    pdf.ln(1)
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(95, 5, 'Firma destinatario', 1, 0, 'L')
    pdf.cell(95, 5, 'Firma conducente', 1, 1, 'L')
    
    pdf.set_font('Arial', '', 8)
    pdf.cell(95, 8, '', 1, 0, 'L')
    pdf.cell(95, 8, '', 1, 1, 'L')
    
    # Note
    if is_credit_note and fiscal_document.credit_note_reason:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, 'Motivo nota di credito:', 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, fiscal_document.credit_note_reason)
        pdf.ln(2)
    
    if order and order.general_note:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, 'Note:', 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, order.general_note)
    
    # Footer
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, f"Documento generato automaticamente - {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')
    
    # Ritorna buffer PDF
    pdf_buffer = BytesIO()
    pdf_output = pdf.output()  # Restituisce bytes direttamente
    pdf_buffer.write(pdf_output)
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
            'quantity': detail.quantity,
            'unit_price': detail.unit_price,
            'total_amount': detail.total_amount,
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
        
