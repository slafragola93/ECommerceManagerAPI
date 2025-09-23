import httpx
import json
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from src.models import Order, Address, Invoice, AppConfiguration
from src.repository.invoice_repository import InvoiceRepository
from src.repository.app_configuration_repository import AppConfigurationRepository

logger = logging.getLogger(__name__)


class FatturaPAService:
    """
    Servizio per l'integrazione con FatturaPA
    Basato sulla documentazione ufficiale: https://www.fatturapa.gov.it/it/norme-e-regole/documentazione-fattura-elettronica/formato-fatturapa
    """
    
    def __init__(self, db: Session, vat_number: Optional[str] = None):
        self.db = db
        self.vat_number = vat_number
        self.invoice_repo = InvoiceRepository(db)
        self.config_repo = AppConfigurationRepository(db)
        
        # Configurazione FatturaPA
        self.api_key = self._get_config_value("fatturapa", "api_key")
        self.base_url = self._get_config_value("fatturapa", "base_url", "https://api.fatturapa.com/ws/V10.svc/rest")
        self.timeout = 30
        self.user_agent = "ECommerceManager-FatturaPA-Client/1.0"
        
        # Configurazione azienda
        if not self.vat_number:
            self.vat_number = self._get_config_value("company_info", "vat_number")
        
        self.company_name = self._get_config_value("company_info", "company_name", "WEB MARKET S.R.L.")
        self.company_address = self._get_config_value("company_info", "address", "CORSO VITTORIO EMANUELE")
        self.company_civic = self._get_config_value("company_info", "civic_number", "110/5")
        self.company_cap = self._get_config_value("company_info", "cap", "80121")
        self.company_city = self._get_config_value("company_info", "city", "NAPOLI")
        self.company_province = self._get_config_value("company_info", "province", "NA")
        self.company_phone = self._get_config_value("company_info", "phone", "0815405273")
        self.company_email = self._get_config_value("company_info", "email", "FATTURAZIONE@ELETTRONEW.COM")
        self.company_contact = self._get_config_value("company_info", "contact", "CRISTIANO VINCENZO")
        self.company_iban = self._get_config_value("company_info", "iban", "IT79A0306939845100000014622")
    
    def _get_config_value(self, category: str, name: str, default: str = None) -> str:
        """Recupera un valore dalla configurazione"""
        try:
            config = self.config_repo.get_by_name_and_category(name, category)
            return config.value if config else default
        except Exception as e:
            logger.warning(f"Errore nel recupero configurazione {category}.{name}: {e}")
            return default
    
    def _get_next_document_number(self) -> str:
        """Genera il prossimo numero di documento sequenziale annuale"""
        current_year = datetime.now().year
        
        # Trova l'ultimo numero di documento per l'anno corrente
        query = text("""
            SELECT MAX(CAST(SUBSTRING(document_number, 1, 5) AS UNSIGNED)) as max_num
            FROM invoices 
            WHERE YEAR(date_add) = :year
        """)
        
        result = self.db.execute(query, {"year": current_year}).fetchone()
        max_num = result.max_num if result and result.max_num else 0
        
        # Incrementa di 1 e formatta con padding a 5 cifre
        next_num = max_num + 1
        return f"{next_num:05d}"
    
    def _get_order_data(self, order_id: int) -> Dict[str, Any]:
        """Recupera i dati dell'ordine"""
        query = text("""
            SELECT o.*, 
                   a_inv.firstname as invoice_firstname,
                   a_inv.lastname as invoice_lastname,
                   a_inv.company as invoice_company,
                   a_inv.address1 as invoice_address1,
                   a_inv.address2 as invoice_address2,
                   a_inv.postcode as invoice_postcode,
                   a_inv.city as invoice_city,
                   a_inv.state as invoice_state,
                   a_inv.vat as invoice_vat,
                   a_inv.dni as invoice_dni,
                   a_inv.pec as invoice_pec,
                   a_inv.phone as invoice_phone,
                   c.name as country_name,
                   c.iso_code as country_iso
            FROM orders o
            LEFT JOIN addresses a_inv ON o.id_address_invoice = a_inv.id_address
            LEFT JOIN countries c ON a_inv.id_country = c.id_country
            WHERE o.id_order = :order_id
        """)
        
        result = self.db.execute(query, {"order_id": order_id}).fetchone()
        if not result:
            raise ValueError(f"Ordine {order_id} non trovato")
        
        return dict(result._mapping)
    
    def _get_order_details(self, order_id: int) -> list:
        """Recupera i dettagli dell'ordine"""
        query = text("""
            SELECT od.*, p.name as product_name
            FROM order_details od
            LEFT JOIN products p ON od.id_product = p.id_product
            WHERE od.id_order = :order_id
        """)
        
        results = self.db.execute(query, {"order_id": order_id}).fetchall()
        return [dict(row._mapping) for row in results]
    
    def _generate_xml(self, order_data: Dict[str, Any], order_details: list, document_number: str) -> str:
        """Genera l'XML FatturaPA secondo le specifiche ufficiali"""
        
        # Estrai dati cliente
        customer_name = order_data.get('invoice_firstname', '') + ' ' + order_data.get('invoice_lastname', '')
        customer_company = order_data.get('invoice_company', '')
        customer_cf = order_data.get('invoice_dni', '')
        customer_pec = order_data.get('invoice_pec', '')
        
        # Calcola totali
        total_amount = float(order_data.get('total_paid_tax_incl', 0))
        tax_amount = float(order_data.get('total_paid_tax_incl', 0)) - float(order_data.get('total_paid_tax_excl', 0))
        net_amount = float(order_data.get('total_paid_tax_excl', 0))
        tax_rate = 22.0  # Default IVA 22%
        
        # Crea root element
        root = ET.Element("p:FatturaElettronica")
        root.set("versione", "FPR12")
        root.set("xmlns:p", "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2")
        root.set("xmlns:ds", "http://www.w3.org/2000/09/xmldsig#")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        
        # Header
        header = ET.SubElement(root, "FatturaElettronicaHeader")
        
        # DatiTrasmissione
        dati_trasmissione = ET.SubElement(header, "DatiTrasmissione")
        
        id_trasmittente = ET.SubElement(dati_trasmissione, "IdTrasmittente")
        ET.SubElement(id_trasmittente, "IdPaese").text = "IT"
        ET.SubElement(id_trasmittente, "IdCodice").text = self.vat_number
        
        ET.SubElement(dati_trasmissione, "ProgressivoInvio").text = document_number
        ET.SubElement(dati_trasmissione, "FormatoTrasmissione").text = "FPR12"
        ET.SubElement(dati_trasmissione, "CodiceDestinatario").text = "0000000"
        
        if customer_pec:
            ET.SubElement(dati_trasmissione, "PECDestinatario").text = customer_pec
        
        contatti_trasmittente = ET.SubElement(dati_trasmissione, "ContattiTrasmittente")
        ET.SubElement(contatti_trasmittente, "Telefono").text = self.company_phone
        ET.SubElement(contatti_trasmittente, "Email").text = self.company_email
        
        # CedentePrestatore
        cedente = ET.SubElement(header, "CedentePrestatore")
        
        dati_anagrafici_cedente = ET.SubElement(cedente, "DatiAnagrafici")
        id_fiscale_cedente = ET.SubElement(dati_anagrafici_cedente, "IdFiscaleIVA")
        ET.SubElement(id_fiscale_cedente, "IdPaese").text = "IT"
        ET.SubElement(id_fiscale_cedente, "IdCodice").text = self.vat_number
        
        ET.SubElement(dati_anagrafici_cedente, "CodiceFiscale").text = self.vat_number
        
        anagrafica_cedente = ET.SubElement(dati_anagrafici_cedente, "Anagrafica")
        ET.SubElement(anagrafica_cedente, "Denominazione").text = self.company_name
        
        ET.SubElement(dati_anagrafici_cedente, "RegimeFiscale").text = "RF01"
        
        sede_cedente = ET.SubElement(cedente, "Sede")
        ET.SubElement(sede_cedente, "Indirizzo").text = self.company_address
        ET.SubElement(sede_cedente, "NumeroCivico").text = self.company_civic
        ET.SubElement(sede_cedente, "CAP").text = self.company_cap
        ET.SubElement(sede_cedente, "Comune").text = self.company_city
        ET.SubElement(sede_cedente, "Provincia").text = self.company_province
        ET.SubElement(sede_cedente, "Nazione").text = "IT"
        
        contatti_cedente = ET.SubElement(cedente, "Contatti")
        ET.SubElement(contatti_cedente, "Telefono").text = self.company_phone
        ET.SubElement(contatti_cedente, "Email").text = self.company_email
        
        ET.SubElement(cedente, "RiferimentoAmministrazione").text = self.company_contact
        
        # CessionarioCommittente
        cessionario = ET.SubElement(header, "CessionarioCommittente")
        
        dati_anagrafici_cessionario = ET.SubElement(cessionario, "DatiAnagrafici")
        
        if customer_cf:
            ET.SubElement(dati_anagrafici_cessionario, "CodiceFiscale").text = customer_cf
        
        anagrafica_cessionario = ET.SubElement(dati_anagrafici_cessionario, "Anagrafica")
        
        if customer_company:
            ET.SubElement(anagrafica_cessionario, "Denominazione").text = customer_company
        else:
            name_parts = customer_name.strip().split(' ', 1)
            if len(name_parts) >= 1:
                ET.SubElement(anagrafica_cessionario, "Nome").text = name_parts[0]
            if len(name_parts) >= 2:
                ET.SubElement(anagrafica_cessionario, "Cognome").text = name_parts[1]
        
        sede_cessionario = ET.SubElement(cessionario, "Sede")
        ET.SubElement(sede_cessionario, "Indirizzo").text = order_data.get('invoice_address1', 'VIA CLIENTE')
        ET.SubElement(sede_cessionario, "NumeroCivico").text = "1"
        ET.SubElement(sede_cessionario, "CAP").text = order_data.get('invoice_postcode', '20100')
        ET.SubElement(sede_cessionario, "Comune").text = order_data.get('invoice_city', 'MILANO')
        ET.SubElement(sede_cessionario, "Provincia").text = order_data.get('invoice_state', 'MI')
        ET.SubElement(sede_cessionario, "Nazione").text = order_data.get('country_iso', 'IT')
        
        # Body
        body = ET.SubElement(root, "FatturaElettronicaBody")
        
        # DatiGenerali
        dati_generali = ET.SubElement(body, "DatiGenerali")
        dati_generali_documento = ET.SubElement(dati_generali, "DatiGeneraliDocumento")
        
        ET.SubElement(dati_generali_documento, "TipoDocumento").text = "TD01"
        ET.SubElement(dati_generali_documento, "Divisa").text = "EUR"
        ET.SubElement(dati_generali_documento, "Data").text = date.today().strftime("%Y-%m-%d")
        ET.SubElement(dati_generali_documento, "Numero").text = f"FATT-{document_number}"
        ET.SubElement(dati_generali_documento, "ImportoTotaleDocumento").text = f"{total_amount:.2f}"
        
        # DatiBeniServizi
        dati_beni_servizi = ET.SubElement(body, "DatiBeniServizi")
        
        # DettaglioLinee
        for i, detail in enumerate(order_details, 1):
            dettaglio_linea = ET.SubElement(dati_beni_servizi, "DettaglioLinee")
            ET.SubElement(dettaglio_linea, "NumeroLinea").text = str(i)
            ET.SubElement(dettaglio_linea, "Descrizione").text = detail.get('product_name', 'Prodotto')
            ET.SubElement(dettaglio_linea, "Quantita").text = f"{float(detail.get('product_quantity', 1)):.2f}"
            ET.SubElement(dettaglio_linea, "PrezzoUnitario").text = f"{float(detail.get('unit_price_tax_excl', 0)):.2f}"
            ET.SubElement(dettaglio_linea, "PrezzoTotale").text = f"{float(detail.get('total_price_tax_excl', 0)):.2f}"
            ET.SubElement(dettaglio_linea, "AliquotaIVA").text = f"{tax_rate:.2f}"
        
        # DatiRiepilogo
        dati_riepilogo = ET.SubElement(dati_beni_servizi, "DatiRiepilogo")
        ET.SubElement(dati_riepilogo, "AliquotaIVA").text = f"{tax_rate:.2f}"
        ET.SubElement(dati_riepilogo, "ImponibileImporto").text = f"{net_amount:.2f}"
        ET.SubElement(dati_riepilogo, "Imposta").text = f"{tax_amount:.2f}"
        ET.SubElement(dati_riepilogo, "EsigibilitaIVA").text = "I"
        
        # DatiPagamento
        dati_pagamento = ET.SubElement(body, "DatiPagamento")
        ET.SubElement(dati_pagamento, "CondizioniPagamento").text = "TP02"
        
        dettaglio_pagamento = ET.SubElement(dati_pagamento, "DettaglioPagamento")
        ET.SubElement(dettaglio_pagamento, "ModalitaPagamento").text = "MP05"
        ET.SubElement(dettaglio_pagamento, "DataScadenzaPagamento").text = date.today().strftime("%Y-%m-%d")
        ET.SubElement(dettaglio_pagamento, "ImportoPagamento").text = f"{total_amount:.2f}"
        ET.SubElement(dettaglio_pagamento, "IBAN").text = self.company_iban
        
        # Converti in stringa XML
        ET.indent(root, space="  ", level=0)
        xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
        
        return xml_str
    
    async def _http_request(self, method: str, url: str, **kwargs) -> Tuple[int, str, str]:
        """Esegue una richiesta HTTP"""
        headers = kwargs.get('headers', {})
        headers['User-Agent'] = self.user_agent
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if method.upper() == 'GET':
                response = await client.get(url, headers=headers)
            elif method.upper() == 'PUT':
                response = await client.put(url, headers=headers, content=kwargs.get('content'))
            else:
                raise ValueError(f"Metodo HTTP non supportato: {method}")
            
            return response.status_code, response.headers.get('content-type', ''), response.text
    
    async def verify_api(self) -> bool:
        """Verifica la connessione API"""
        try:
            url = f"{self.base_url}/Verify/{self.api_key}"
            status_code, _, body = await self._http_request('GET', url)
            
            if status_code == 200 and 'true' in body.lower():
                logger.info("Verifica API FatturaPA completata con successo")
                return True
            else:
                logger.error(f"Verifica API fallita: {status_code} - {body}")
                return False
        except Exception as e:
            logger.error(f"Errore nella verifica API: {e}")
            return False
    
    async def upload_start(self, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """Avvia il processo di upload"""
        try:
            # Prova prima UploadStart1
            url = f"{self.base_url}/UploadStart1/{self.api_key}/{filename}"
            status_code, _, body = await self._http_request('GET', url)
            
            if status_code == 200:
                try:
                    data = json.loads(body)
                    name = data.get('Name') or data.get('name')
                    complete = data.get('Complete') or data.get('complete')
                    
                    if name and complete:
                        logger.info(f"UploadStart1 completato: {name}")
                        return name, complete
                except json.JSONDecodeError:
                    pass
            
        except Exception as e:
            logger.error(f"Errore in upload_start: {e}")
            return None, None
    
    async def upload_xml(self, complete_url: str, xml_content: str) -> bool:
        """Carica l'XML su Azure Blob"""
        try:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/xml',
                'Content-Length': str(len(xml_content)),
                'x-ms-blob-type': 'BlockBlob',
                'x-ms-version': '2018-03-28'
            }
            
            status_code, _, body = await self._http_request('PUT', complete_url, 
                                                          headers=headers, content=xml_content)
            
            if 200 <= status_code < 300:
                logger.info("Upload XML completato con successo")
                return True
            else:
                logger.error(f"Upload XML fallito: {status_code} - {body}")
                return False
                
        except Exception as e:
            logger.error(f"Errore nell'upload XML: {e}")
            return False
    
    async def upload_stop(self, name: str, send_to_sdi: bool = False) -> Dict[str, Any]:
        """Completa il processo di upload"""
        try:
            endpoint = "UploadStop" if send_to_sdi else "UploadStop1"
            url = f"{self.base_url}/{endpoint}/{self.api_key}/{name}"
            
            status_code, _, body = await self._http_request('GET', url)
            
            if status_code == 200:
                try:
                    result = json.loads(body)
                    logger.info(f"UploadStop completato: {endpoint}")
                    return result
                except json.JSONDecodeError:
                    return {"status": "success", "message": body}
            else:
                logger.error(f"UploadStop fallito: {status_code} - {body}")
                return {"status": "error", "message": body}
                
        except Exception as e:
            logger.error(f"Errore in upload_stop: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_events(self) -> Dict[str, Any]:
        """Recupera gli eventi dal pool"""
        try:
            url = f"{self.base_url}/Pool/{self.api_key}"
            status_code, _, body = await self._http_request('GET', url)
            
            if status_code == 200:
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {"status": "error", "message": "Risposta non JSON"}
            else:
                return {"status": "error", "message": f"HTTP {status_code}"}
                
        except Exception as e:
            logger.error(f"Errore nel recupero eventi: {e}")
            return {"status": "error", "message": str(e)}
    
    async def generate_and_upload_invoice(self, order_id: int, iso_code: str = "IT") -> Dict[str, Any]:
        """
        Genera e carica una fattura per un ordine
        
        Args:
            order_id: ID dell'ordine
            iso_code: Codice ISO del paese (default: IT)
            
        Returns:
            Dict con il risultato dell'operazione
        """
        try:
            # 1. Verifica API
            if not await self.verify_api():
                return {"status": "error", "message": "Verifica API fallita"}
            
            # 2. Recupera dati ordine
            order_data = self._get_order_data(order_id)
            order_details = self._get_order_details(order_id)
            
            if not order_details:
                return {"status": "error", "message": "Nessun dettaglio ordine trovato"}
            
            # 3. Genera numero documento sequenziale
            document_number = self._get_next_document_number()
            
            # 4. Genera XML
            xml_content = self._generate_xml(order_data, order_details, document_number)
            
            # 5. Genera nome file
            filename = f"{self.vat_number}_{document_number}.xml"
            
            # 6. Upload Start
            name, complete_url = await self.upload_start(filename)
            if not name or not complete_url:
                return {"status": "error", "message": "UploadStart fallito"}
            
            # 7. Upload XML
            if not await self.upload_xml(complete_url, xml_content):
                return {"status": "error", "message": "Upload XML fallito"}
            
            # 8. Upload Stop (senza invio a SdI)
            stop_result = await self.upload_stop(name, send_to_sdi=False)
            
            # 9. Crea record Invoice nel database
            invoice_data = {
                "id_order": order_id,
                "document_number": document_number,
                "filename": filename,
                "xml_content": xml_content,
                "status": "uploaded",
                "upload_result": stop_result,
                "date_add": datetime.now()
            }
            
            invoice_id = self.invoice_repo.create_invoice(invoice_data)
            
            return {
                "status": "success",
                "message": "Fattura generata e caricata con successo",
                "invoice_id": invoice_id,
                "document_number": document_number,
                "filename": filename,
                "upload_result": stop_result
            }
            
        except Exception as e:
            logger.error(f"Errore nella generazione fattura: {e}")
            return {"status": "error", "message": str(e)}
