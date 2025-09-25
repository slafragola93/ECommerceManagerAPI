"""
Router FastAPI per FatturaPA
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from src.database import get_db
from src.services.fatturapa_service import FatturaPAService
from src.schemas.fatturapa_models import (
    FatturaElettronica, OrderToFatturaPAMapper, 
    FormatoTrasmissione
)

router = APIRouter(prefix="/fatturapa", tags=["FatturaPA"])


class FatturaPARequest(BaseModel):
    """Request per generazione fattura da Order"""
    order_id: int
    formato_trasmissione: FormatoTrasmissione = FormatoTrasmissione.FPR12
    progressivo_invio: str
    codice_destinatario: str
    pec_destinatario: Optional[str] = None


class ValidationRequest(BaseModel):
    """Request per validazione fattura"""
    fattura: FatturaElettronica


class ValidationResponse(BaseModel):
    """Response per validazione"""
    valid: bool
    errors: list


@router.post("/validate", response_model=ValidationResponse)
async def validate_fattura(
    request: ValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Valida una FatturaElettronica secondo le specifiche FatturaPA
    
    - **fattura**: Oggetto FatturaElettronica da validare
    """
    try:
        service = FatturaPAService(db)
        result = service.validate_fattura(request.fattura)
        
        return ValidationResponse(
            valid=result["valid"],
            errors=result["errors"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella validazione: {str(e)}"
        )



@router.get("/orders/{order_id}/issue-invoice")
async def issue_invoice_by_order_id(
    order_id: int,
    formato_trasmissione: FormatoTrasmissione = FormatoTrasmissione.FPR12,
    progressivo_invio: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Genera, carica e scarica automaticamente XML FatturaPA da ID ordine
    
    Questo endpoint:
    1. Genera la fattura XML per l'ordine specificato
    2. Carica la fattura sul sistema FatturaPA (senza invio a SDI)
    3. Scarica automaticamente il file XML generato
    
    - **order_id**: ID dell'ordine
    - **formato_trasmissione**: Formato trasmissione (FPR12/FPA12)
    - **progressivo_invio**: Progressivo invio (opzionale, auto-generato se non fornito)
    
    **Response**: File XML scaricabile con nome formato `{VAT_NUMBER}_{DOCUMENT_NUMBER}.xml`
    In caso di errore nel download XML, restituisce una risposta JSON con i dettagli.
    """
    try:
        # Genera progressivo se non fornito
        if not progressivo_invio:
            progressivo_invio = f"{order_id:010d}"
        
        # Recupera dati ordine per ottenere codice SDI dall'indirizzo
        service = FatturaPAService(db)
        
        
        # Usa il servizio esistente per generare e caricare la fattura
        service = FatturaPAService(db)
        result = await service.generate_and_upload_invoice(order_id)
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        # Dopo l'upload riuscito, genera anche l'XML per il download
        try:
            # Recupera i dati necessari per generare l'XML
            order_data = service._get_order_data(order_id)
            order_details = service._get_order_details(order_id)
            
            # Genera XML per il download (usa lo stesso document_number)
            xml_content = service._generate_xml(order_data, order_details, result["document_number"])
            filename = result["filename"]
            
            # Restituisce l'XML come file scaricabile insieme alla risposta
            return Response(
                content=xml_content,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Type": "application/xml; charset=utf-8",
                    "X-Invoice-Info": f"order_id:{order_id},invoice_id:{result.get('invoice_id')},document_number:{result.get('document_number')}"
                }
            )
            
        except Exception as xml_error:
            # Se il download XML fallisce, restituisce comunque la risposta JSON
            return {
                "status": "success",
                "order_id": order_id,
                "invoice_id": result.get("invoice_id"),
                "document_number": result.get("document_number"),
                "filename": result.get("filename"),
                "message": "Fattura generata e caricata con successo",
                "xml_download_error": str(xml_error)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione fattura per ordine {order_id}: {str(e)}"
        )


@router.get("/orders/{order_id}/data")
async def get_order_fattura_data(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Recupera tutti i dati necessari per FatturaPA da un ordine
    
    - **order_id**: ID dell'ordine
    """
    try:
        service = FatturaPAService(db)
        
        # Recupera dati ordine
        order_data = service._get_order_data(order_id)
        order_details = service._get_order_details(order_id)
        
        return {
            "status": "success",
            "order_id": order_id,
            "order_data": order_data,
            "order_details": order_details,
            "message": "Dati ordine recuperati con successo"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero dati ordine {order_id}: {str(e)}"
        )


@router.get("/verify")
async def verify_fatturapa_api(
    db: Session = Depends(get_db)
):
    """
    Verifica la connessione con l'API FatturaPA
    """
    try:
        service = FatturaPAService(db)
        is_connected = await service.verify_api()
        
        return {
            "status": "success" if is_connected else "error",
            "connected": is_connected,
            "message": "API FatturaPA verificata" if is_connected else "Errore nella verifica API"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella verifica API: {str(e)}"
        )


@router.get("/events")
async def get_fatturapa_events(
    db: Session = Depends(get_db)
):
    """
    Recupera gli eventi dal pool FatturaPA
    """
    try:
        service = FatturaPAService(db)
        events = await service.get_events()
        
        return {
            "status": "success",
            "events": events,
            "message": "Eventi recuperati con successo"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero eventi: {str(e)}"
        )


@router.get("/orders/{order_id}/get-xml")
async def get_xml_by_order_id(
    order_id: int,
    formato_trasmissione: FormatoTrasmissione = FormatoTrasmissione.FPR12,
    progressivo_invio: Optional[str] = None,
    codice_destinatario: Optional[str] = None,
    pec_destinatario: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Genera e scarica l'XML FatturaPA senza upload
    
    - **order_id**: ID dell'ordine
    - **formato_trasmissione**: Formato trasmissione (FPR12/FPA12)
    - **progressivo_invio**: Progressivo invio (opzionale, auto-generato se non fornito)
    - **codice_destinatario**: Codice destinatario SDI (opzionale, recuperato da address se presente)
    - **pec_destinatario**: PEC destinatario (opzionale, recuperato da address se presente)
    
    **Response**: File XML scaricabile con nome formato `{VAT_NUMBER}_{DOCUMENT_NUMBER}.xml`
    """
    try:
        # Genera progressivo se non fornito
        if not progressivo_invio:
            progressivo_invio = f"{order_id:010d}"
        
        # Recupera dati ordine per ottenere codice SDI dall'indirizzo
        service = FatturaPAService(db)
        order_data = service._get_order_data(order_id)
        order_details = service._get_order_details(order_id)
        
        # Usa codice destinatario dall'indirizzo se non fornito esplicitamente
        if not codice_destinatario:
            codice_destinatario = order_data.get('invoice_sdi', '0000000')
        
        # Usa PEC dall'indirizzo se non fornita esplicitamente
        if not pec_destinatario:
            pec_destinatario = order_data.get('invoice_pec')
        
        # Genera numero documento sequenziale
        document_number = service._get_next_document_number()
        
        # Genera XML
        xml_content = service._generate_xml(order_data, order_details, document_number)
        
        # Genera nome file
        filename = f"{service.vat_number}_{document_number}.xml"
        
        # Restituisce l'XML come file scaricabile
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/xml; charset=utf-8"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione XML per ordine {order_id}: {str(e)}"
        )

@router.get("/orders/{order_id}/debug")
async def debug_order_fatturapa(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Debug completo per ordine FatturaPA - mostra tutti i dati e possibili errori
    """
    try:
        service = FatturaPAService(db)
        
        # Recupera dati ordine
        order_data = service._get_order_data(order_id)
        order_details = service._get_order_details(order_id)
        
        # Analisi dettagliata dei dati
        debug_info = {
            "order_id": order_id,
            "order_data": {
                "total_price": order_data.get('total_price'),
                "invoice_address1": order_data.get('invoice_address1'),
                "invoice_city": order_data.get('invoice_city'),
                "invoice_state": order_data.get('invoice_state'),
                "invoice_postcode": order_data.get('invoice_postcode'),
                "invoice_sdi": order_data.get('invoice_sdi'),
                "invoice_pec": order_data.get('invoice_pec'),
                "invoice_dni": order_data.get('invoice_dni'),
                "invoice_company": order_data.get('invoice_company'),
                "invoice_firstname": order_data.get('invoice_firstname'),
                "invoice_lastname": order_data.get('invoice_lastname'),
            },
            "order_details": [
                {
                    "product_name": detail.get('product_name'),
                    "product_qty": detail.get('product_qty'),
                    "product_price": detail.get('product_price'),
                }
                for detail in order_details
            ],
            "validation_issues": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Validazioni dettagliate
        validation_issues = []
        warnings = []
        suggestions = []
        
        # 1. Validazione CodiceDestinatario
        customer_sdi = order_data.get('invoice_sdi')
        if customer_sdi:
            if len(customer_sdi) != 7:
                validation_issues.append({
                    "field": "CodiceDestinatario",
                    "issue": f"Lunghezza non valida: {len(customer_sdi)} caratteri (richiesti: 7)",
                    "value": customer_sdi,
                    "severity": "error"
                })
        else:
            warnings.append({
                "field": "CodiceDestinatario", 
                "issue": "Non presente - verrà usato 0000000 (PEC)",
                "suggestion": "Aggiungi codice SDI nell'indirizzo di fatturazione"
            })
        
        # 2. Validazione CodiceFiscale
        customer_cf = order_data.get('invoice_dni')
        if customer_cf:
            if len(customer_cf) < 11 or len(customer_cf) > 16:
                validation_issues.append({
                    "field": "CodiceFiscale",
                    "issue": f"Lunghezza non valida: {len(customer_cf)} caratteri (richiesti: 11-16)",
                    "value": customer_cf,
                    "severity": "error"
                })
        else:
            warnings.append({
                "field": "CodiceFiscale",
                "issue": "Non presente",
                "suggestion": "Aggiungi codice fiscale o P.IVA nell'indirizzo di fatturazione"
            })
        
        # 3. Validazione Indirizzo
        indirizzo = order_data.get('invoice_address1', '')
        if not indirizzo or not indirizzo.strip():
            validation_issues.append({
                "field": "Indirizzo",
                "issue": "Indirizzo vuoto o mancante",
                "value": indirizzo,
                "severity": "error"
            })
        elif ',' in indirizzo or ';' in indirizzo:
            warnings.append({
                "field": "Indirizzo",
                "issue": "Contiene caratteri speciali che potrebbero causare problemi",
                "value": indirizzo,
                "suggestion": "Rimuovi virgole e punti e virgola dall'indirizzo"
            })
        
        # 4. Validazione Provincia
        provincia_originale = order_data.get('invoice_state')
        if not provincia_originale:
            validation_issues.append({
                "field": "Provincia",
                "issue": "Provincia mancante",
                "value": provincia_originale,
                "severity": "error"
            })
        else:
            # Simula la logica del servizio: tronca alle prime due lettere e maiuscolo
            provincia_elaborata = provincia_originale[:2].upper()
            if len(provincia_elaborata) != 2:
                validation_issues.append({
                    "field": "Provincia",
                    "issue": f"Provincia troppo corta: '{provincia_originale}' → '{provincia_elaborata}' (richiesti: 2 caratteri)",
                    "value": provincia_originale,
                    "severity": "error"
                })
            else:
                # Mostra la trasformazione
                if provincia_originale != provincia_elaborata:
                    warnings.append({
                        "field": "Provincia",
                        "issue": f"Provincia verrà troncata: '{provincia_originale}' → '{provincia_elaborata}'",
                        "value": provincia_originale,
                        "suggestion": f"Risultato finale: {provincia_elaborata}"
                    })
        
        # 5. Validazione CAP
        cap = order_data.get('invoice_postcode')
        if not cap:
            validation_issues.append({
                "field": "CAP",
                "issue": "CAP mancante",
                "value": cap,
                "severity": "error"
            })
        elif len(cap) != 5:
            validation_issues.append({
                "field": "CAP",
                "issue": f"Lunghezza non valida: {len(cap)} caratteri (richiesti: 5)",
                "value": cap,
                "severity": "error"
            })
        
        # 6. Validazione Dettagli Ordine
        if not order_details:
            validation_issues.append({
                "field": "DettagliOrdine",
                "issue": "Nessun dettaglio ordine trovato",
                "value": None,
                "severity": "error"
            })
        else:
            for i, detail in enumerate(order_details):
                if not detail.get('product_name'):
                    validation_issues.append({
                        "field": f"DettaglioOrdine[{i}].product_name",
                        "issue": "Nome prodotto mancante",
                        "value": detail.get('product_name'),
                        "severity": "error"
                    })
                
                if not detail.get('product_price') or float(detail.get('product_price', 0)) <= 0:
                    validation_issues.append({
                        "field": f"DettaglioOrdine[{i}].product_price",
                        "issue": "Prezzo prodotto mancante o non valido",
                        "value": detail.get('product_price'),
                        "severity": "error"
                    })
        
        # 7. Calcoli IVA
        total_amount = float(order_data.get('total_price', 0))
        if total_amount <= 0:
            validation_issues.append({
                "field": "TotalPrice",
                "issue": "Totale ordine non valido",
                "value": total_amount,
                "severity": "error"
            })
        
        debug_info["validation_issues"] = validation_issues
        debug_info["warnings"] = warnings
        debug_info["suggestions"] = suggestions
        
        # Statistiche
        debug_info["stats"] = {
            "total_errors": len(validation_issues),
            "total_warnings": len(warnings),
            "total_suggestions": len(suggestions),
            "can_generate_xml": len(validation_issues) == 0
        }
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "order_id": order_id,
            "message": "Errore durante l'analisi debug"
        }

@router.get("/orders/{order_id}/debug-xml-generation")
async def debug_xml_generation(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Debug dettagliato per la generazione XML - mostra step by step
    """
    try:
        service = FatturaPAService(db)
        
        # Recupera dati ordine
        order_data = service._get_order_data(order_id)
        order_details = service._get_order_details(order_id)
        
        # Genera numero documento
        document_number = service._get_next_document_number()
        
        debug_info = {
            "order_id": order_id,
            "document_number": document_number,
            "step_by_step": [],
            "errors": [],
            "warnings": []
        }
        
        # Step 1: Verifica dati ordine
        debug_info["step_by_step"].append({
            "step": 1,
            "name": "Verifica Dati Ordine",
            "status": "success",
            "details": {
                "total_price": order_data.get('total_price'),
                "has_invoice_address": bool(order_data.get('invoice_address1')),
                "has_invoice_city": bool(order_data.get('invoice_city')),
                "has_invoice_state": bool(order_data.get('invoice_state')),
                "has_invoice_postcode": bool(order_data.get('invoice_postcode')),
                "has_invoice_sdi": bool(order_data.get('invoice_sdi')),
                "has_invoice_pec": bool(order_data.get('invoice_pec')),
                "has_invoice_dni": bool(order_data.get('invoice_dni'))
            }
        })
        
        # Step 2: Verifica dettagli ordine
        debug_info["step_by_step"].append({
            "step": 2,
            "name": "Verifica Dettagli Ordine",
            "status": "success" if order_details else "error",
            "details": {
                "count": len(order_details),
                "products": [
                    {
                        "name": detail.get('product_name'),
                        "qty": detail.get('product_qty'),
                        "price": detail.get('product_price')
                    }
                    for detail in order_details
                ]
            }
        })
        
        if not order_details:
            debug_info["errors"].append("Nessun dettaglio ordine trovato")
        
        # Step 3: Calcoli IVA
        tax_rate = 22.0
        totale_imponibile = 0
        totale_imposta = 0
        
        for i, detail in enumerate(order_details):
            quantita = float(detail.get('product_qty', 1))
            prezzo_unitario_iva = float(detail.get('product_price', 0))
            prezzo_unitario_netto = prezzo_unitario_iva / (1 + tax_rate / 100)
            prezzo_totale_netto = prezzo_unitario_netto * quantita
            imposta_linea = (prezzo_unitario_iva - prezzo_unitario_netto) * quantita
            
            totale_imponibile += prezzo_totale_netto
            totale_imposta += imposta_linea
        
        total_amount = totale_imponibile + totale_imposta
        
        debug_info["step_by_step"].append({
            "step": 3,
            "name": "Calcoli IVA",
            "status": "success",
            "details": {
                "tax_rate": tax_rate,
                "totale_imponibile": round(totale_imponibile, 2),
                "totale_imposta": round(totale_imposta, 2),
                "total_amount": round(total_amount, 2)
            }
        })
        
        # Step 4: Validazioni critiche
        validation_results = []
        
        # CodiceDestinatario
        customer_sdi = order_data.get('invoice_sdi')
        if customer_sdi and len(customer_sdi) == 7:
            validation_results.append({"field": "CodiceDestinatario", "status": "success", "value": customer_sdi})
        else:
            validation_results.append({"field": "CodiceDestinatario", "status": "error", "value": customer_sdi, "issue": "Lunghezza non valida"})
            debug_info["errors"].append(f"CodiceDestinatario: '{customer_sdi}' (lunghezza: {len(customer_sdi) if customer_sdi else 0})")
        
        # CodiceFiscale
        customer_cf = order_data.get('invoice_dni')
        if customer_cf and 11 <= len(customer_cf) <= 16:
            validation_results.append({"field": "CodiceFiscale", "status": "success", "value": customer_cf})
        else:
            validation_results.append({"field": "CodiceFiscale", "status": "error", "value": customer_cf, "issue": "Lunghezza non valida"})
            debug_info["errors"].append(f"CodiceFiscale: '{customer_cf}' (lunghezza: {len(customer_cf) if customer_cf else 0})")
        
        # Indirizzo
        indirizzo = order_data.get('invoice_address1', '')
        if indirizzo and indirizzo.strip():
            validation_results.append({"field": "Indirizzo", "status": "success", "value": indirizzo})
        else:
            validation_results.append({"field": "Indirizzo", "status": "error", "value": indirizzo, "issue": "Vuoto o mancante"})
            debug_info["errors"].append(f"Indirizzo: '{indirizzo}' (vuoto)")
        
        # Provincia
        provincia = order_data.get('invoice_state')
        if provincia:
            provincia_elaborata = provincia[:2].upper()
            if len(provincia_elaborata) == 2:
                validation_results.append({"field": "Provincia", "status": "success", "value": f"{provincia} → {provincia_elaborata}"})
            else:
                validation_results.append({"field": "Provincia", "status": "error", "value": provincia, "issue": "Troppo corta"})
                debug_info["errors"].append(f"Provincia: '{provincia}' (troppo corta)")
        else:
            validation_results.append({"field": "Provincia", "status": "error", "value": provincia, "issue": "Mancante"})
            debug_info["errors"].append(f"Provincia: '{provincia}' (mancante)")
        
        # CAP
        cap = order_data.get('invoice_postcode')
        if cap and len(cap) == 5:
            validation_results.append({"field": "CAP", "status": "success", "value": cap})
        else:
            validation_results.append({"field": "CAP", "status": "error", "value": cap, "issue": "Lunghezza non valida"})
            debug_info["errors"].append(f"CAP: '{cap}' (lunghezza: {len(cap) if cap else 0})")
        
        debug_info["step_by_step"].append({
            "step": 4,
            "name": "Validazioni Critiche",
            "status": "success" if not debug_info["errors"] else "error",
            "details": {
                "validations": validation_results,
                "error_count": len(debug_info["errors"])
            }
        })
        
        # Step 5: Tentativo generazione XML
        try:
            xml_content = service._generate_xml(order_data, order_details, document_number)
            debug_info["step_by_step"].append({
                "step": 5,
                "name": "Generazione XML",
                "status": "success",
                "details": {
                    "xml_length": len(xml_content),
                    "has_xml_declaration": xml_content.startswith('<?xml'),
                    "contains_fatturapa": 'FatturaElettronica' in xml_content
                }
            })
        except Exception as e:
            debug_info["step_by_step"].append({
                "step": 5,
                "name": "Generazione XML",
                "status": "error",
                "details": {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            })
            debug_info["errors"].append(f"Errore generazione XML: {str(e)}")
        
        # Riepilogo
        debug_info["summary"] = {
            "can_generate_xml": len(debug_info["errors"]) == 0,
            "total_errors": len(debug_info["errors"]),
            "total_warnings": len(debug_info["warnings"]),
            "steps_completed": len([s for s in debug_info["step_by_step"] if s["status"] == "success"]),
            "total_steps": len(debug_info["step_by_step"])
        }
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "order_id": order_id,
            "message": "Errore durante il debug della generazione XML",
            "error_type": type(e).__name__
        }


@router.post("/orders/{order_id}/validate-xml")
async def validate_order_xml(
    order_id: int,
    formato_trasmissione: FormatoTrasmissione = FormatoTrasmissione.FPR12,
    progressivo_invio: Optional[str] = None,
    codice_destinatario: Optional[str] = None,
    pec_destinatario: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Valida l'XML FatturaPA per un ordine e identifica gli errori specifici
    
    - **order_id**: ID dell'ordine
    - **formato_trasmissione**: Formato trasmissione (FPR12/FPA12)
    - **progressivo_invio**: Progressivo invio (opzionale, auto-generato se non fornito)
    - **codice_destinatario**: Codice destinatario SDI (opzionale, recuperato da address se presente)
    - **pec_destinatario**: PEC destinatario (opzionale, recuperato da address se presente)
    """
    try:
        # Genera progressivo se non fornito
        if not progressivo_invio:
            progressivo_invio = f"{order_id:010d}"
        
        # Recupera dati ordine
        service = FatturaPAService(db)
        order_data = service._get_order_data(order_id)
        order_details = service._get_order_details(order_id)
        
        # Usa codice destinatario dall'indirizzo se non fornito esplicitamente
        if not codice_destinatario:
            codice_destinatario = order_data.get('invoice_sdi', '0000000')
        
        # Usa PEC dall'indirizzo se non fornita esplicitamente
        if not pec_destinatario:
            pec_destinatario = order_data.get('invoice_pec')
        
        # Genera numero documento sequenziale
        document_number = service._get_next_document_number()
        
        # Genera XML
        xml_content = service._generate_xml(order_data, order_details, document_number)
        
        # Analizza i dati per identificare potenziali problemi
        validation_issues = []
        
        # Controlla dati cliente
        if not order_data.get('invoice_firstname') and not order_data.get('invoice_company'):
            validation_issues.append({
                "field": "anagrafica_cliente",
                "issue": "Manca nome/cognome o denominazione azienda",
                "severity": "error"
            })
        
        if not order_data.get('invoice_vat') and not order_data.get('invoice_dni'):
            validation_issues.append({
                "field": "identificazione_cliente", 
                "issue": "Manca P.IVA o Codice Fiscale",
                "severity": "warning"
            })
        
        if not order_data.get('invoice_address1'):
            validation_issues.append({
                "field": "indirizzo_cliente",
                "issue": "Indirizzo cliente mancante",
                "severity": "error"
            })
        
        # Controlla dettagli ordine
        if not order_details:
            validation_issues.append({
                "field": "dettagli_ordine",
                "issue": "Nessun dettaglio ordine trovato",
                "severity": "error"
            })
        
        # Controlla totali
        total_price = order_data.get('total_price', 0)
        if total_price <= 0:
            validation_issues.append({
                "field": "totale_ordine",
                "issue": "Totale ordine zero o negativo",
                "severity": "warning"
            })
        
        # Controlla codice destinatario
        if codice_destinatario == "0000000":
            validation_issues.append({
                "field": "codice_destinatario",
                "issue": "Codice destinatario SDI non specificato (usato 0000000)",
                "severity": "warning"
            })
        
        return {
            "status": "success",
            "order_id": order_id,
            "document_number": document_number,
            "xml_content": xml_content,
            "validation_issues": validation_issues,
            "data_summary": {
                "cliente_nome": order_data.get('invoice_firstname', '') + ' ' + order_data.get('invoice_lastname', ''),
                "cliente_azienda": order_data.get('invoice_company', ''),
                "cliente_piva": order_data.get('invoice_vat', ''),
                "cliente_cf": order_data.get('invoice_dni', ''),
                "cliente_indirizzo": order_data.get('invoice_address1', ''),
                "cliente_citta": order_data.get('invoice_city', ''),
                "codice_destinatario": codice_destinatario,
                "pec_destinatario": pec_destinatario,
                "totale_ordine": total_price,
                "numero_dettagli": len(order_details)
            },
            "message": "Validazione XML completata"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella validazione XML per ordine {order_id}: {str(e)}"
        )


@router.get("/invoices/{invoice_id}")
async def get_invoice_details(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """
    Recupera i dettagli di una fattura generata
    
    - **invoice_id**: ID della fattura nel database
    """
    try:
        from src.repository.invoice_repository import InvoiceRepository
        
        invoice_repo = InvoiceRepository(db)
        invoice = invoice_repo.get_invoice_by_id(invoice_id)
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fattura {invoice_id} non trovata"
            )
        
        # Parse upload_result se presente
        upload_result = None
        if invoice.upload_result:
            try:
                import json
                upload_result = json.loads(invoice.upload_result)
            except (json.JSONDecodeError, TypeError):
                upload_result = {"raw": invoice.upload_result}
        
        return {
            "status": "success",
            "invoice": {
                "id_invoice": invoice.id_invoice,
                "id_order": invoice.id_order,
                "document_number": invoice.document_number,
                "filename": invoice.filename,
                "status": invoice.status,
                "upload_result": upload_result,
                "date_add": invoice.date_add.isoformat() if invoice.date_add else None,
                "date_upd": invoice.date_upd.isoformat() if invoice.date_upd else None,
                "xml_content_length": len(invoice.xml_content) if invoice.xml_content else 0
            },
            "message": "Dettagli fattura recuperati con successo"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero dettagli fattura: {str(e)}"
        )
