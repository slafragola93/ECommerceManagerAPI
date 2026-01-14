import httpx
import json
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from src.models.tax import Tax
from src.services.core.tool import calculate_amount_with_percentage
from src.models import Order, Address, FiscalDocument, FiscalDocumentDetail, OrderDetail, Country
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.repository.tax_repository import TaxRepository
from src.services.external.province_service import province_service
from src.services.external.fatturapa_validator import FatturaPAValidator

logger = logging.getLogger(__name__)


class FatturaPAService:
    """
    Servizio per l'integrazione con FatturaPA
    Basato sulla documentazione ufficiale: https://www.fatturapa.gov.it/it/norme-e-regole/documentazione-fattura-elettronica/formato-fatturapa
    """
    
    def __init__(self, db: Session, vat_number: Optional[str] = None):
        self.db = db
        self.vat_number = vat_number
        self.config_repo = AppConfigurationRepository(db)
        self.tax_repo = TaxRepository(db)
        
        # Configurazione FatturaPA
        self.api_key = self._get_config_value("fatturapa", "api_key")
        self.base_url = self._get_config_value("fatturapa", "base_url", "https://api.fatturapa.com/ws/V10.svc/rest")
        self.timeout = 30
        self.user_agent = "ECommerceManager-FatturaPA-Client/1.0"
        
        # Configurazione azienda
        if not self.vat_number:
            self.vat_number = self._get_config_value("company_info", "vat_number")
        
        self.company_name = self._get_config_value("company_info", "company_name")
        self.company_address = self._get_config_value("company_info", "address")
        self.company_civic = self._get_config_value("company_info", "civic_number")
        self.company_cap = self._get_config_value("company_info", "postal_code")
        self.company_city = self._get_config_value("company_info", "city")
        self.company_province = self._get_config_value("company_info", "province")
        self.company_phone = self._get_config_value("company_info", "phone")
        self.company_email = self._get_config_value("company_info", "email")
        self.company_contact = self._get_config_value("company_info", "account_holder")
        self.company_iban = self._get_config_value("company_info", "iban")
        self.company_bank_name = self._get_config_value("company_info",  "bank_name")
        
        # Inizializza validatore
        self.validator = FatturaPAValidator()
    
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
        
        # Trova l'ultimo numero di documento per l'anno corrente da fiscal_documents
        query = text("""
            SELECT MAX(CAST(SUBSTRING(document_number, 1, 5) AS UNSIGNED)) as max_num
            FROM fiscal_documents 
            WHERE YEAR(date_add) = :year 
            AND document_type = 'invoice'
            AND is_electronic = TRUE
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
                   a_inv.sdi as invoice_sdi,
                   a_inv.phone as invoice_phone,
                   c.name as country_name,
                   c.iso_code as country_iso,
                   t.id_tax,
                   t.percentage as tax_percentage,
                   t.electronic_code as tax_electronic_code,
                   t.note as tax_note,
                   a_del.id_country as delivery_country_id,
                   t_del.percentage as tax_percentage_customer,
                   s.price_tax_excl as shipping_price_tax_excl,
                   s.id_tax as shipping_id_tax,
                   t_ship.percentage as shipping_tax_percentage,
                   p.name as payment_name,
                   p.fiscal_mode_payment,
                   p.is_complete_payment
            FROM orders o
            LEFT JOIN addresses a_inv ON o.id_address_invoice = a_inv.id_address
            LEFT JOIN countries c ON a_inv.id_country = c.id_country
            LEFT JOIN addresses a_del ON o.id_address_delivery = a_del.id_address
            LEFT JOIN countries c_del ON a_del.id_country = c_del.id_country
            LEFT JOIN taxes t_del ON a_del.id_country = t_del.id_country
            LEFT JOIN orders_document od ON o.id_order = od.id_order
            LEFT JOIN shipments s ON o.id_shipping = s.id_shipping
            LEFT JOIN taxes t_ship ON s.id_tax = t_ship.id_tax
            LEFT JOIN payments p ON o.id_payment = p.id_payment
            WHERE o.id_order = :order_id
        """)
        
        result = self.db.execute(query, {"order_id": order_id}).fetchone()
        print(result)
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
    
    def _create_element(self, parent, tag: str, text: str = None, use_prefix: bool = False, **attrs) -> ET.Element:
        """Helper per creare elementi XML"""
        # Usa prefisso p: solo se esplicitamente richiesto (per FatturaElettronica root)
        element_tag = f"p:{tag}" if use_prefix else tag
        element = ET.SubElement(parent, element_tag)
        if text:
            element.text = text
        for key, value in attrs.items():
            element.set(key, value)
        return element
    
    def _generate_filename(self, document_number: str) -> str:
        """
        Genera il nome del file XML FatturaPA
        
        Args:
            document_number: Numero documento (es. "000001")
        
        Returns:
            Nome file formato: IT{VAT_NUMBER}_{DOCUMENT_NUMBER}.xml
        """
        return f"{self.vat_number}_{document_number}.xml"

    def _generate_xml(self, order_data: Dict[str, Any], line_items: list, document_number: str, include_shipping: bool = True) -> str:
        """
        Genera l'XML FatturaPA secondo le specifiche ufficiali
        
        Args:
            order_data: Dati dell'ordine/documento
            line_items: Dettagli articoli (possono essere order_details o fiscal_document_details trasformati)
            document_number: Numero documento progressivo
            include_shipping: Se True, include le spese di spedizione (default: True)
        """
        print(f"=== _generate_xml CHIAMATO ===")
        print(f"=== INIZIO GENERAZIONE XML FATTURAPA ===")
        print(f"Documento: {document_number}")
        print(f"Line items count: {len(line_items)}")
        
        print(order_data)
        # Estrai dati cliente
        customer_name = order_data.get('invoice_firstname', '') + ' ' + order_data.get('invoice_lastname', '')
        customer_company = order_data.get('invoice_company', '')
        customer_cf = order_data.get('customer_fiscal_code', '')
        customer_pec = order_data.get('invoice_pec', '')
        customer_sdi = order_data.get('invoice_sdi', '')
        
        # Partita IVA - rimuovi lettere (es. "IT12345678901" → "12345678901")
        customer_vat_raw = order_data.get('invoice_vat', '')
        customer_vat = ''.join(filter(str.isdigit, customer_vat_raw)) if customer_vat_raw else ''
        
        print(f"=== DATI CLIENTE ===")
        print(f"Cliente: '{customer_name.strip()}' (company: '{customer_company}')")
        print(f"CodiceFiscale: '{customer_cf}' (lunghezza: {len(customer_cf) if customer_cf else 0})")
        print(f"SDI: '{customer_sdi}' (lunghezza: {len(customer_sdi) if customer_sdi else 0})")
        print(f"PEC: '{customer_pec}'")
        print(f"VAT: '{customer_vat}' (originale: '{customer_vat_raw}')")
        
        # Calcola totali corretti
        # Recupera la percentuale IVA dal paese di delivery
        delivery_tax_percentage = order_data.get('tax_percentage_customer')  # t_del.percentage
        if delivery_tax_percentage is not None:
            tax_rate = float(delivery_tax_percentage)
        else:
            # Recupera la percentuale IVA di default dal database
            default_tax = self.tax_repo.get_default_tax_rate()
            if default_tax and default_tax[0]:
                tax_rate = float(default_tax[0])
                print(f"[WARNING] Tax percentage not found for delivery country, using default {tax_rate}%")
            else:
                tax_rate = 22.0  # Fallback hardcoded se non c'è nemmeno il default nel DB
                print(f"[WARNING] No default tax found in DB, using hardcoded fallback {tax_rate}%")
            
        
        # Ricalcola imponibile e imposta dalle linee di dettaglio
        totale_imponibile = 0
        totale_imposta = 0
        
        print(f"=== DETTAGLI ARTICOLI ===")
        for i, detail in enumerate(line_items):
            # PROBABILI ERRORI QUI
            product_qty = float(detail.get('product_qty', 1))
            product_price_no_tax = float(detail.get('product_price', 0))  # Prezzo unitario senza IVA
            
            # Calcolo corretto imponibile e imposta
            prezzo_totale_netto = product_price_no_tax * product_qty  # Imponibile (base imponibile)
            imposta_linea = calculate_amount_with_percentage(prezzo_totale_netto, tax_rate)  # IVA = imponibile * aliquota 
            
            print(f"  Prezzo unitario senza IVA: {product_price_no_tax:.4f}")
            print(f"  Quantità: {product_qty:.2f}")
            print(f"  Imponibile linea: {prezzo_totale_netto:.4f}")
            print(f"  Imposta linea ({tax_rate}%): {imposta_linea:.4f}")
            
            totale_imponibile += prezzo_totale_netto
            totale_imposta += imposta_linea
        
        # Calcola il totale con IVA usando total_price dell'ordine * percentuale tassa
        total_amount = float(order_data.get('total_price', 0))
        totale_imponibile = total_amount / (1 + tax_rate / 100)
        totale_imposta = total_amount - totale_imponibile
        
        print(f"=== TOTALI CALCOLATI ===")
        print(f"Totale imponibile: {totale_imponibile:.2f}")
        print(f"Totale imposta: {totale_imposta:.2f}")
        print(f"Totale con IVA: {total_amount:.2f}")
        

        # Se non ci sono dettagli, usa il totale dell'ordine
        if totale_imponibile == 0:
            logger.warning("Nessun dettaglio ordine trovato, uso totale ordine")
            total_amount = float(order_data.get('total_price', 0))
            if total_amount > 0:
                totale_imponibile = total_amount / (1 + tax_rate / 100)
                totale_imposta = total_amount - totale_imponibile
                print(f"Totale ordine: {total_amount:.2f}")
                print(f"Imponibile calcolato: {totale_imponibile:.2f}")
                print(f"Imposta calcolata: {totale_imposta:.2f}")
        
        print(f"=== CREAZIONE XML ===")
        # Crea root element con prefisso p:
        root = ET.Element("p:FatturaElettronica")
        root.set("versione", "FPR12")
        root.set("xmlns:p", "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2")
        root.set("xmlns:ds", "http://www.w3.org/2000/09/xmldsig#")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:schemaLocation", "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2 http://www.fatturapa.gov.it/export/fatturazione/sdi/fatturapa/v1.2/Schema_del_file_xml_FatturaPA_versione_1.2.xsd")

        # Header
        header = self._create_element(root, "FatturaElettronicaHeader")
        
        # DatiTrasmissione
        dati_trasmissione = self._create_element(header, "DatiTrasmissione")
        
        id_trasmittente = self._create_element(dati_trasmissione, "IdTrasmittente")
        self._create_element(id_trasmittente, "IdPaese", "IT")
        self._create_element(id_trasmittente, "IdCodice", self.vat_number)
        
        self._create_element(dati_trasmissione, "ProgressivoInvio", document_number)
        self._create_element(dati_trasmissione, "FormatoTrasmissione", "FPR12")
        
        # Logica CodiceDestinatario basata su FormatoTrasmissione
        formato_trasmissione = "FPR12"  # Default per privati
        print(f"=== VALIDAZIONE CODICE DESTINATARIO ===")
        print(f"FormatoTrasmissione: {formato_trasmissione}")
        
        if formato_trasmissione == "FPR12":
            # Fatture verso privati: 7 caratteri o 0000000 se non accreditato
            if customer_sdi and len(customer_sdi) == 7:
                codice_destinatario = customer_sdi
                print(f"CodiceDestinatario da SDI: '{codice_destinatario}'")
            else:
                codice_destinatario = "0000000"
                print(f"CodiceDestinatario default (non accreditato): '{codice_destinatario}'")
        elif formato_trasmissione == "FPA12":
            # Fatture verso PA: 6 caratteri
            if customer_sdi and len(customer_sdi) == 6:
                codice_destinatario = customer_sdi
                print(f"CodiceDestinatario PA: '{codice_destinatario}'")
            else:
                error_msg = f"Per FPA12 CodiceDestinatario deve essere esattamente 6 caratteri. Ricevuto: '{customer_sdi}' (lunghezza: {len(customer_sdi) if customer_sdi else 0})"
                logger.error(f"ERRORE VALIDAZIONE: {error_msg}")
                raise ValueError(error_msg)
        else:
            # Operazioni transfrontaliere: XXXXXXX
            codice_destinatario = "XXXXXXX"
            print(f"CodiceDestinatario transfrontaliero: '{codice_destinatario}'")
            
        self._create_element(dati_trasmissione, "CodiceDestinatario", codice_destinatario)
        print(f"[OK] CodiceDestinatario validato: {codice_destinatario}")
        
        # Gestione PEC del destinatario
        if customer_pec:
            self._create_element(dati_trasmissione, "PECDestinatario", customer_pec)
        else:
            # Se non c'è PEC nell'indirizzo, cerca SDI o usa "0000000"
            # TODO: Implementare fallback PEC da altri indirizzi customer se necessario
            pass
        
        contatti_trasmittente = self._create_element(dati_trasmissione, "ContattiTrasmittente")
        self._create_element(contatti_trasmittente, "Telefono", self.company_phone)
        self._create_element(contatti_trasmittente, "Email", self.company_email)
        


        # CedentePrestatore
        cedente = self._create_element(header, "CedentePrestatore")
        
        dati_anagrafici_cedente = self._create_element(cedente, "DatiAnagrafici")
        id_fiscale_cedente = self._create_element(dati_anagrafici_cedente, "IdFiscaleIVA")
        self._create_element(id_fiscale_cedente, "IdPaese", "IT")
        self._create_element(id_fiscale_cedente, "IdCodice", self.vat_number)
        
        
        # Aggiungi CodiceFiscale solo se presente
        if customer_cf:
            self._create_element(dati_anagrafici_cedente, "CodiceFiscale", customer_cf) 
        
        anagrafica_cedente = self._create_element(dati_anagrafici_cedente, "Anagrafica")
        self._create_element(anagrafica_cedente, "Denominazione", self.company_name)
        
        # Recupera il regime fiscale dalla configurazione, default RF01 se null
        tax_regime = self._get_config_value("electronic_invoicing", "tax_regime", "RF01")
        self._create_element(dati_anagrafici_cedente, "RegimeFiscale", tax_regime)
        
        sede_cedente = self._create_element(cedente, "Sede")
        self._create_element(sede_cedente, "Indirizzo", self.company_address)
        self._create_element(sede_cedente, "NumeroCivico", self.company_civic)
        self._create_element(sede_cedente, "CAP", self.company_cap)
        self._create_element(sede_cedente, "Comune", self.company_city)
        self._create_element(sede_cedente, "Provincia", self.company_province)
        self._create_element(sede_cedente, "Nazione", "IT")
        
        contatti_cedente = self._create_element(cedente, "Contatti")
        self._create_element(contatti_cedente, "Telefono", self.company_phone)
        self._create_element(contatti_cedente, "Email", self.company_email)
        
        self._create_element(cedente, "RiferimentoAmministrazione", self.company_contact)
        
        # CessionarioCommittente
        cessionario = self._create_element(header, "CessionarioCommittente")
        
        dati_anagrafici_cessionario = self._create_element(cessionario, "DatiAnagrafici")
        
        # IdFiscaleIVA - se presente la partita IVA del cliente
        if customer_vat:
            id_fiscale_iva = self._create_element(dati_anagrafici_cessionario, "IdFiscaleIVA")
            # Usa il codice paese dell'indirizzo di fatturazione
            paese_iso = order_data.get('country_iso', 'IT')
            self._create_element(id_fiscale_iva, "IdPaese", paese_iso)
            self._create_element(id_fiscale_iva, "IdCodice", customer_vat)
        
        if customer_cf:
            if len(customer_cf) < 11 or len(customer_cf) > 16:
                error_msg = f"CodiceFiscale deve essere tra 11 e 16 caratteri. Ricevuto: '{customer_cf}' (lunghezza: {len(customer_cf)})"
                logger.error(f"ERRORE VALIDAZIONE: {error_msg}")
                raise ValueError(error_msg)
            self._create_element(dati_anagrafici_cessionario, "CodiceFiscale", customer_cf)
        else:
            logger.warning("[WARNING] CodiceFiscale non presente")
        
        anagrafica_cessionario = self._create_element(dati_anagrafici_cessionario, "Anagrafica")
        
        if customer_company:
            self._create_element(anagrafica_cessionario, "Denominazione", customer_company)
        else:
            name_parts = customer_name.strip().split(' ', 1)
            if len(name_parts) >= 1:
                self._create_element(anagrafica_cessionario, "Nome", name_parts[0])
            if len(name_parts) >= 2:
                self._create_element(anagrafica_cessionario, "Cognome", name_parts[1])
        
        sede_cessionario = self._create_element(cessionario, "Sede")
        # Pulisci l'indirizzo da caratteri speciali e virgole
        indirizzo = order_data.get('invoice_address1', 'VIA CLIENTE')
        indirizzo_pulito = indirizzo.replace(',', '').replace(';', '').strip()
        if not indirizzo_pulito:
            error_msg = "Indirizzo cliente non può essere vuoto"
            logger.error(f"ERRORE VALIDAZIONE: {error_msg}")
            raise ValueError(error_msg)
        self._create_element(sede_cessionario, "Indirizzo", indirizzo_pulito)
        cap = order_data.get('invoice_postcode', '20100')
        if not cap or len(cap) != 5:
            error_msg = f"CAP deve essere esattamente 5 caratteri. Ricevuto: '{cap}' (lunghezza: {len(cap) if cap else 0})"
            logger.error(f"ERRORE VALIDAZIONE: {error_msg}")
            raise ValueError(error_msg)
        self._create_element(sede_cessionario, "CAP", cap)
        
        self._create_element(sede_cessionario, "Comune", order_data.get('invoice_city', 'MILANO'))
        
        # Provincia limitata a 2 caratteri (formato NA, MI, etc.)
        provincia_originale = order_data.get('invoice_state') or order_data.get('provincia')
        
        # Usa ProvinceService per conversione
        if provincia_originale:
            # Se è già un'abbreviazione (2 caratteri), usala
            if len(provincia_originale) == 2:
                provincia = provincia_originale.upper()
            else:
                # Altrimenti converti usando il service
                provincia = province_service.get_province_abbreviation(provincia_originale)
                if not provincia:
                    # Fallback: prime 2 lettere
                    provincia = provincia_originale[:2].upper()
        else:
            provincia = None
        
        if not provincia or len(provincia) != 2:
            error_msg = f"Provincia deve essere esattamente 2 caratteri. Ricevuto: '{provincia_originale}' (lunghezza: {len(provincia) if provincia else 0})"
            logger.error(f"ERRORE VALIDAZIONE: {error_msg}")
            raise ValueError(error_msg)
        self._create_element(sede_cessionario, "Provincia", provincia)
        self._create_element(sede_cessionario, "Nazione", order_data.get('country_iso', 'IT'))
        
        # Body
        body = self._create_element(root, "FatturaElettronicaBody")
        
        # DatiGenerali
        dati_generali = self._create_element(body, "DatiGenerali")
        dati_generali_documento = self._create_element(dati_generali, "DatiGeneraliDocumento")
        
        # TipoDocumento viene passato come parametro (TD01 per fatture, TD04 per note di credito)
        tipo_documento = order_data.get('tipo_documento_fe')
        self._create_element(dati_generali_documento, "TipoDocumento", tipo_documento)
        self._create_element(dati_generali_documento, "Divisa", "EUR")
        self._create_element(dati_generali_documento, "Data", date.today().strftime("%Y-%m-%d"))
        # Converte il document_number in intero per il campo Numero
        numero_sequenziale = int(document_number)
        self._create_element(dati_generali_documento, "Numero", str(numero_sequenziale))
        self._create_element(dati_generali_documento, "ImportoTotaleDocumento", f"{total_amount:.2f}")
        
        # DatiCassaPrevidenziale - solo se electronic_code è presente
        tax_electronic_code = order_data.get('tax_electronic_code')
        #if tax_electronic_code and tax_electronic_code.strip():
        
        # DatiBeniServizi
        dati_beni_servizi = self._create_element(body, "DatiBeniServizi")
        
        
        # DettaglioLinee
        for i, detail in enumerate(line_items, 1):
            dettaglio_linea = self._create_element(dati_beni_servizi, "DettaglioLinee")
            self._create_element(dettaglio_linea, "NumeroLinea", str(i))
            self._create_element(dettaglio_linea, "Descrizione", detail.get('product_name', 'Prodotto'))
            
            # Quantità
            product_qty_raw = detail.get('product_qty')
            quantita = float(product_qty_raw) if product_qty_raw is not None else 1.0
            self._create_element(dettaglio_linea, "Quantita", f"{quantita:.2f}")
            
            # Prezzo unitario (product_price è il prezzo con IVA)
            product_price_raw = detail.get('product_price', 0)
            prezzo_unitario_netto = float(product_price_raw)
            self._create_element(dettaglio_linea, "PrezzoUnitario", f"{prezzo_unitario_netto:.2f}")
            print(f"PrezzoUnitario: {prezzo_unitario_netto:.2f}")

                      
            # Controlla se ci sono sconti o maggiorazioni
            reduction_percent_raw = detail.get('reduction_percent', 0)
            reduction_amount_raw = detail.get('reduction_amount', 0)
            
            # Gestisci valori None convertendoli a 0
            reduction_percent = float(reduction_percent_raw) if reduction_percent_raw is not None else 0.0
            reduction_amount = float(reduction_amount_raw) if reduction_amount_raw is not None else 0.0
            
            # Calcola PrezzoTotale PRIMA dello sconto (prezzo base * quantità)
            prezzo_totale_base = float(prezzo_unitario_netto) * quantita
            
            # Applica sconti per ottenere PrezzoTotale finale (IVA esclusa)
            prezzo_totale_netto = prezzo_totale_base
            
            if reduction_percent != 0:
                # Applica sconto percentuale
                sconto = prezzo_totale_base * (reduction_percent / 100)
                prezzo_totale_netto = prezzo_totale_base - sconto
            elif reduction_amount != 0:
                # Applica sconto importo (già IVA esclusa)
                prezzo_totale_netto = prezzo_totale_base - reduction_amount
            
            # Arrotonda usando ROUND_HALF_UP
            prezzo_totale_netto = Decimal(str(prezzo_totale_netto)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Tag ScontoMaggiorazione
            if reduction_percent != 0 or reduction_amount != 0:
                sconto_maggiorazione = self._create_element(dettaglio_linea, "ScontoMaggiorazione")
                self._create_element(sconto_maggiorazione, "Tipo", "SC")
                
                if reduction_percent != 0:
                    self._create_element(sconto_maggiorazione, "Percentuale", f"{reduction_percent:.2f}")
                elif reduction_amount != 0:
                    # reduction_amount è già IVA esclusa
                    self._create_element(sconto_maggiorazione, "Importo", f"{reduction_amount:.2f}")
            
            # PrezzoTotale = prezzo base * quantità - sconti (IVA ESCLUSA)
            self._create_element(dettaglio_linea, "PrezzoTotale", f"{prezzo_totale_netto:.2f}")
            
            self._create_element(dettaglio_linea, "AliquotaIVA", f"{tax_rate:.2f}")
            if tax_electronic_code and tax_electronic_code.strip():
                self._create_element(dettaglio_linea, "Natura", f"{tax_electronic_code:.2f}")
        
        # Aggiungi linea per sconti se total_discounts > 0
        total_discounts = float(order_data.get('total_discounts', 0))
        if total_discounts > 0:
            total_discounts_no_iva = total_discounts / (1 + tax_rate / 100)
            i += 1  # Incrementa numero linea
            dettaglio_sconto = self._create_element(dati_beni_servizi, "DettaglioLinee")
            self._create_element(dettaglio_sconto, "NumeroLinea", str(i))
            self._create_element(dettaglio_sconto, "TipoCessionePrestazione", "SC")
            self._create_element(dettaglio_sconto, "Descrizione", "Buoni Sconto")
            self._create_element(dettaglio_sconto, "Quantita", "1.00")
            self._create_element(dettaglio_sconto, "PrezzoUnitario", f"{-total_discounts_no_iva:.2f}")
            self._create_element(dettaglio_sconto, "PrezzoTotale", f"{-total_discounts_no_iva:.2f}")
            self._create_element(dettaglio_sconto, "AliquotaIVA", f"{tax_rate:.2f}")
        
        # Aggiungi linea per spese di spedizione (SOLO per fatture, NON per note di credito)
        tipo_documento = order_data.get('tipo_documento_fe')
        shipping_price = float(order_data.get('shipping_price_tax_excl', 0))
        if include_shipping and shipping_price > 0:
            i += 1  # Incrementa numero linea
            dettaglio_spedizione = self._create_element(dati_beni_servizi, "DettaglioLinee")
            self._create_element(dettaglio_spedizione, "NumeroLinea", str(i))
            self._create_element(dettaglio_spedizione, "TipoCessionePrestazione", "AC")
            self._create_element(dettaglio_spedizione, "Descrizione", "SPESE")
            self._create_element(dettaglio_spedizione, "PrezzoUnitario", f"{shipping_price:.2f}")
            self._create_element(dettaglio_spedizione, "PrezzoTotale", f"{shipping_price:.2f}")
            
            # Usa l'aliquota IVA delle spese di spedizione se disponibile, altrimenti quella generale
            shipping_tax_rate = float(order_data.get('shipping_tax_percentage', tax_rate))
            self._create_element(dettaglio_spedizione, "AliquotaIVA", f"{shipping_tax_rate:.2f}")
            print(f"Spese di spedizione aggiunte: EUR {shipping_price:.2f}")
        else:
            print(f"[INFO] Spese di spedizione NON aggiunte (include_shipping={include_shipping})")
        
        # DatiRiepilogo
        dati_riepilogo = self._create_element(dati_beni_servizi, "DatiRiepilogo")
        self._create_element(dati_riepilogo, "AliquotaIVA", f"{tax_rate:.2f}")

        if tax_electronic_code and tax_electronic_code.strip():
            self._create_element(dati_riepilogo, "Natura", tax_electronic_code)
            # Usa il campo note della tassa per RiferimentoNormativo
            tax_note = order_data.get('tax_note')
            if tax_note and tax_note.strip():
                self._create_element(dati_riepilogo, "RiferimentoNormativo", tax_note)

        # Arrotonda i totali usando ROUND_HALF_UP
        self._create_element(dati_riepilogo, "ImponibileImporto", f"{totale_imponibile:.2f}")
        self._create_element(dati_riepilogo, "Imposta", f"{totale_imposta:.2f}")
        self._create_element(dati_riepilogo, "EsigibilitaIVA", "I")
        
        # DatiPagamento
        print(f"=== AGGIUNTA DATI PAGAMENTO ===")
        dati_pagamento = self._create_element(body, "DatiPagamento")
        
        # CondizioniPagamento (TP01=immediato, TP02=scadenza, TP03=rate)
        condizioni_pagamento = order_data.get('condizioni_pagamento', 'TP02')  # Default: scadenza
        self._create_element(dati_pagamento, "CondizioniPagamento", condizioni_pagamento)
        
        # DettaglioPagamento
        dettaglio_pagamento = self._create_element(dati_pagamento, "DettaglioPagamento")
        
        # ModalitaPagamento - recupera dal payment method
        fiscal_mode_payment = order_data.get('fiscal_mode_payment', 'MP05')  # Default: bonifico
        if not fiscal_mode_payment or fiscal_mode_payment not in [f'MP{i:02d}' for i in range(1, 24)]:
            fiscal_mode_payment = 'MP05'  # Fallback a bonifico
            print(f"[WARNING] Modalita pagamento non valida, uso default: {fiscal_mode_payment}")
        
        self._create_element(dettaglio_pagamento, "ModalitaPagamento", fiscal_mode_payment)
        print(f"Modalità pagamento: {fiscal_mode_payment}")
        
        # Se bonifico (MP05), aggiungi dati bancari
        if fiscal_mode_payment == 'MP05':
            self._create_element(dettaglio_pagamento, "IstitutoFinanziario", self.company_bank_name)
            self._create_element(dettaglio_pagamento, "IBAN", self.company_iban)
            print(f"Dati bancari: {self.company_bank_name} - {self.company_iban}")
        
        # ImportoPagamento (totale documento)
        self._create_element(dettaglio_pagamento, "ImportoPagamento", f"{total_amount:.2f}")
        print(f"Importo pagamento: {total_amount:.2f}")
        
        # DataScadenzaPagamento (opzionale, solo se TP02)
        if condizioni_pagamento == 'TP02':
            # Aggiungi 30 giorni alla data ordine come scadenza
            from datetime import timedelta
            order_date = order_data.get('date_add', datetime.now())
            if isinstance(order_date, str):
                order_date = datetime.strptime(order_date, '%Y-%m-%d %H:%M:%S')
            scadenza = order_date + timedelta(days=30)
            self._create_element(dettaglio_pagamento, "DataScadenzaPagamento", scadenza.strftime('%Y-%m-%d'))
            print(f"Data scadenza: {scadenza.strftime('%Y-%m-%d')}")
        
        print(f"=== DATI PAGAMENTO COMPLETATI ===")
        
        # Converti in stringa XML
        print(f"=== FINALIZZAZIONE XML ===")
        ET.indent(root, space="  ", level=0)
        xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
        print(f"XML generato con successo (lunghezza: {len(xml_str)} caratteri)")
        print(f"=== FINE GENERAZIONE XML FATTURAPA ===")
        
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
                print("Verifica API FatturaPA completata con successo")
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
                        print(f"UploadStart1 completato: {name}")
                        return name, complete
                except json.JSONDecodeError:
                    pass
            
        except Exception as e:
            logger.error(f"Errore in upload_start: {e}")
            return None, None
    
    async def upload_xml(self, complete_url: str, xml_content: str) -> bool:
        """Carica l'XML su Azure Blob"""
        try:
            # Converti la stringa XML in bytes UTF-8
            xml_bytes = xml_content.encode('utf-8')
            
            # Calcola Content-Length sui bytes (non sulla stringa)
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/xml; charset=utf-8',
                'Content-Length': str(len(xml_bytes)),
                'x-ms-blob-type': 'BlockBlob',
                'x-ms-version': '2018-03-28'
            }
            
            # Invia i bytes invece della stringa
            status_code, _, body = await self._http_request('PUT', complete_url, 
                                                          headers=headers, content=xml_bytes)
            
            if 200 <= status_code < 300:
                print("Upload XML completato con successo")
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
            endpoint = "UploadStop1"
            url = f"{self.base_url}/{endpoint}/{self.api_key}/{name}"
            
            status_code, _, body = await self._http_request('GET', url)
            
            if status_code == 200:
                try:
                    result = json.loads(body)
                    print(f"UploadStop completato: {endpoint}")
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
    
    
    
    # ==================== NUOVI METODI PER FISCAL DOCUMENTS ====================
    
    def generate_xml_from_fiscal_document(self, id_fiscal_document: int) -> Dict[str, Any]:
        """
        Genera XML FatturaPA da un FiscalDocument (fattura o nota di credito)
        
        Args:
            id_fiscal_document: ID del documento fiscale
        
        Returns:
            Dict con status, filename, xml_content
        """
        try:
            # Recupera fiscal document
            fiscal_doc = self.db.query(FiscalDocument).filter(
                FiscalDocument.id_fiscal_document == id_fiscal_document
            ).first()
            
            if not fiscal_doc:
                raise ValueError(f"Documento fiscale {id_fiscal_document} non trovato")
            
            if not fiscal_doc.is_electronic:
                raise ValueError("Il documento non è elettronico, non è possibile generare XML")
            
            # Recupera ordine
            order = self.db.query(Order).filter(Order.id_order == fiscal_doc.id_order).first()
            if not order:
                raise ValueError(f"Ordine {fiscal_doc.id_order} non trovato")
            
            # Verifica indirizzo italiano
            italy = self.db.query(Country).filter(Country.iso_code == 'IT').first()
            if not italy:
                raise ValueError("Paese Italia (IT) non trovato nel database")
            
            address = self.db.query(Address).filter(Address.id_address == order.id_address_invoice).first()
            if not address or address.id_country != italy.id_country:
                raise ValueError("La fattura elettronica può essere emessa solo per indirizzi italiani")
            
            # Prepara order_data con tipo documento
            order_data = self._prepare_order_data_from_fiscal_document(fiscal_doc, order, address)
            
            # Recupera line items da fiscal_document_details (non da order_details)
            # Per note di credito parziali, contiene SOLO gli articoli da stornare
            line_items = self._get_order_details_for_fiscal_document(fiscal_doc)
            
            # Determina se includere spese di spedizione dal campo includes_shipping del documento
            # Usa il valore salvato nel FiscalDocument (gestito al momento della creazione)
            include_shipping = fiscal_doc.includes_shipping
            
            # Prepara company_data per validazione
            company_data = {
                'vat_number': self.vat_number,
                'fiscal_code': self._get_config_value("company_info", "fiscal_code"),
                'company_name': self.company_name,
                'address': self.company_address,
                'civic_number': self.company_civic,
                'postal_code': self.company_cap,
                'city': self.company_city,
                'province': self.company_province,
                'phone': self.company_phone,
                'email': self.company_email,
                'fax': self._get_config_value("company_info", "fax"),
                'account_holder': self.company_contact,
                'tax_regime': self._get_config_value("electronic_invoicing", "tax_regime", "RF01")
            }
            
            # Valida dati prima di generare XML
            validation_result = self.validator.validate(order_data, line_items, company_data)
            
            if not validation_result['valid']:
                logger.error(f"Validazione XML FatturaPA fallita per fiscal document {id_fiscal_document}: {len(validation_result['errors'])} errori")
                return {
                    "status": "validation_error",
                    "errors": validation_result['errors']
                }
            
            # Genera XML
            xml_content = self._generate_xml(order_data, line_items, fiscal_doc.document_number, include_shipping=include_shipping)
            
            # Genera filename
            filename = self._generate_filename(fiscal_doc.document_number)
            
            return {
                "status": "success",
                "filename": filename,
                "xml_content": xml_content
            }
            
        except Exception as e:
            logger.error(f"Errore generazione XML per fiscal document {id_fiscal_document}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _prepare_order_data_from_fiscal_document(
        self, 
        fiscal_doc: FiscalDocument, 
        order: Order, 
        address: Address
    ) -> Dict[str, Any]:
        """Prepara dizionario order_data da FiscalDocument"""
        
        # Query per ottenere dati customer, shipping, tax e delivery country tax
        customer_query = text("""
            SELECT c.*, 
                   s.price_tax_excl as shipping_price_tax_excl,
                   s.id_tax as shipping_id_tax,
                   t_ship.percentage as shipping_tax_percentage,
                   t_del.id_tax as id_tax,
                   t_del.percentage as tax_percentage,
                   a_del.id_country as delivery_country_id,
                   t_del.percentage as tax_percentage_customer
            FROM customers c
            LEFT JOIN orders o ON c.id_customer = o.id_customer
            LEFT JOIN addresses a_del ON o.id_address_delivery = a_del.id_address
            LEFT JOIN taxes t_del ON a_del.id_country = t_del.id_country
            LEFT JOIN shipments s ON o.id_shipping = s.id_shipping
            LEFT JOIN taxes t_ship ON s.id_tax = t_ship.id_tax
            LEFT JOIN orders_document od ON o.id_order = od.id_order
            WHERE c.id_customer = :id_customer AND o.id_order = :id_order
        """)
        customer_result = self.db.execute(customer_query, {
            "id_customer": order.id_customer,
            "id_order": order.id_order
        }).fetchone()
        
        if not customer_result:
            raise ValueError(f"Cliente {order.id_customer} non trovato")
        
        # Converti result in dict
        customer = dict(customer_result._mapping)
        
        # Recupera country ISO dall'address
        country_iso = 'IT'  # Default
        if address.id_country:
            country = self.db.query(Country).filter(Country.id_country == address.id_country).first()
            if country:
                country_iso = country.iso_code
        
        # Determina company name da address o customer
        customer_company = address.company
        
        
        # Converti provincia usando ProvinceService
        provincia_abbreviation = None
        if address.state:
            provincia_abbreviation = province_service.get_province_abbreviation(address.state)
            if not provincia_abbreviation:
                # Se non trova, usa le prime 2 lettere maiuscole come fallback
                provincia_abbreviation = address.state[:2].upper() if len(address.state) >= 2 else address.state.upper()
        
        return {
            'id_order': order.id_order,
            'tipo_documento_fe': fiscal_doc.tipo_documento_fe,  # TD01 o TD04
            
            # Dati anagrafici - usa address (priorità) o customer (fallback)
            'customer_company': customer_company,
            'customer_firstname': address.firstname or customer.get('firstname'),
            'customer_lastname': address.lastname or customer.get('lastname'),
            'customer_vat': address.vat or '',
            'customer_fiscal_code': address.dni or '',
            
            # Campi usati in _generate_xml (con prefisso invoice_)
            'invoice_firstname': address.firstname or customer.get('firstname', ''),
            'invoice_lastname': address.lastname or customer.get('lastname', ''),
            'invoice_address1': address.address1,
            'invoice_address2': address.address2,
            'invoice_city': address.city,
            'invoice_postcode': address.postcode,
            'invoice_state': provincia_abbreviation,
            'invoice_pec': address.pec,
            'invoice_sdi': address.sdi,
            'invoice_vat': address.vat,
            
            # Altri campi legacy
            'address_line1': address.address1,
            'address_line2': address.address2,
            'city': address.city,
            'postcode': address.postcode,
            'country_iso': country_iso,
            'provincia': provincia_abbreviation,
            'pec': address.pec,
            'sdi': address.sdi,
            'total_price': fiscal_doc.total_amount or 0.0,
            'total_discounts': order.total_discounts or 0.0,
            'shipping_price_tax_excl': customer.get('shipping_price_tax_excl', 0.0),
            'shipping_tax_percentage': customer.get('shipping_tax_percentage', 22.0),
            'id_tax': customer.get('id_tax'),
            'tax_percentage_customer': customer.get('tax_percentage_customer')  # Percentuale IVA del paese di delivery
        }
    
    def _get_order_details_for_fiscal_document(self, fiscal_doc: FiscalDocument) -> list:
        """
        Recupera i dettagli articoli per un fiscal document.
        
        IMPORTANTE: Questo metodo usa FISCAL_DOCUMENT_DETAILS (non order_details).
        Per note di credito parziali, restituisce SOLO gli articoli da stornare.
        
        Returns:
            Lista di dict nel formato compatibile con _generate_xml:
            [{'product_name': str, 'product_qty': float, 'product_price': float, ...}]
        """
        
        # Recupera fiscal_document_details (NON order_details)
        fiscal_details = self.db.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == fiscal_doc.id_fiscal_document
        ).all()
        
        if not fiscal_details:
            return []
        
        details = []
        for fdd in fiscal_details:
            # Recupera OrderDetail per ottenere product_name e id_tax
            od = self.db.query(OrderDetail).filter(
                OrderDetail.id_order_detail == fdd.id_order_detail
            ).first()
            
            if not od:
                continue
            
            # Calcola reduction dal confronto tra total_amount e prezzo base
            prezzo_base = fdd.unit_price * fdd.quantity
            sconto = prezzo_base - fdd.total_amount
            
            # Determina se è percentuale o importo
            reduction_percent = 0.0
            reduction_amount = 0.0
            
            if sconto > 0:
                if od.reduction_percent and od.reduction_percent > 0:
                    reduction_percent = od.reduction_percent
                else:
                    reduction_amount = sconto
            
            # Se id_tax non è specificato, usa quello del paese di consegna
            tax_id = od.id_tax
            if not tax_id or tax_id == 0:
                # Recupera l'id_tax basandosi sul paese dell'indirizzo di consegna
                delivery_address = self.db.query(Address).join(Order).filter(
                    Order.id_order == fiscal_doc.id_order,
                    Order.id_address_delivery == Address.id_address
                ).first()
                
                if delivery_address and delivery_address.id_country:
                    tax = self.db.query(Tax).filter(
                        Tax.id_country == delivery_address.id_country
                    ).first()
                    tax_id = tax.id_tax
                else:
                    # Fallback alla tassa di default
                    tax_id = 1
            
            details.append({
                'product_name': od.product_name,
                'product_qty': fdd.quantity,  
                'product_price': fdd.unit_price,
                'reduction_percent': reduction_percent,
                'reduction_amount': reduction_amount,
                'id_tax': tax_id
            })
        
        return details
