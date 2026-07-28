import httpx
import json
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from src.models.tax import Tax
from src.models import Order, Address, FiscalDocument, FiscalDocumentDetail, OrderDetail, Country
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.repository.tax_repository import TaxRepository
from src.services.external.fatturapa_validator import FatturaPAValidator
from src.services.external.fatturapa_xsd_validator import validate_fatturapa_xml
from src.services.external.fatturapa_tax_line import (
    FatturaPALineTax,
    build_riepilogo_groups,
    enrich_line_item_tax_fields,
    resolve_line_tax,
    vies_eligible_from_order_data,
)
from src.services.external.fatturapa_filename import (
    build_fatturapa_filename,
    normalize_id_codice,
)
from src.services.external.fatturapa_customer_address import (
    build_sede_fields,
    normalize_customer_vat,
    resolve_codice_destinatario,
    resolve_invoice_state,
)

logger = logging.getLogger(__name__)

# Modalità pagamento che richiedono IBAN / IstitutoFinanziario (FatturaPA)
PAYMENT_MODES_REQUIRING_IBAN = frozenset({"MP05"})
DEFAULT_PAYMENT_TERM_DAYS = 30


def _parse_optional_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and len(raw) >= 10:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    return None


def resolve_document_date(order_data: Dict[str, Any]) -> date:
    """
    Data documento FatturaPA (DatiGeneraliDocumento/Data):
    ``document_date`` / ``fiscal_document_date`` da fiscal_documents.date_add.
    Fallback: oggi solo se assente (es. test legacy).
    """
    raw = order_data.get("document_date") or order_data.get("fiscal_document_date")
    parsed = _parse_optional_date(raw)
    return parsed if parsed is not None else date.today()


def resolve_payment_due_date(
    order_data: Dict[str, Any],
    *,
    payment_term_days: int = DEFAULT_PAYMENT_TERM_DAYS,
) -> date:
    """
    DataScadenzaPagamento: sempre ancorata a ``DatiGeneraliDocumento/Data``.

    - se ``payment_due_date`` >= Data documento → usarla;
    - altrimenti Data documento + ``payment_term_days`` (default 30).

    Non usa mai ``DatiFattureCollegate/Data`` né solo ``order.date_add``.
    """
    document_date = resolve_document_date(order_data)
    due = _parse_optional_date(order_data.get("payment_due_date"))
    if due is not None and due >= document_date:
        return due
    days = payment_term_days if payment_term_days and payment_term_days > 0 else DEFAULT_PAYMENT_TERM_DAYS
    return document_date + timedelta(days=days)


def format_id_documento(document_number: Optional[str]) -> str:
    """IdDocumento FatturaPA: progressivo senza zeri iniziali se numerico."""
    if not document_number:
        return ""
    raw = str(document_number).strip()
    if raw.isdigit():
        return str(int(raw))
    return raw


def resolve_linked_invoice_date(order_data: Dict[str, Any]) -> Optional[date]:
    """Data fattura collegata per DatiFattureCollegate (TD04)."""
    return _parse_optional_date(order_data.get("linked_invoice_date"))


def compute_arrotondamento(
    importo_totale: float,
    riepilogo_groups: List[Dict[str, Any]],
) -> Decimal:
    """Differenza ImportoTotaleDocumento − Σ(ImponibileImporto + Imposta)."""
    total = Decimal(str(importo_totale)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    lines_sum = Decimal("0.00")
    for group in riepilogo_groups:
        lines_sum += Decimal(str(group.get("ImponibileImporto", 0)))
        lines_sum += Decimal(str(group.get("Imposta", 0)))
    lines_sum = lines_sum.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (total - lines_sum).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
        self.company_fiscal_code = self._get_config_value("company_info", "fiscal_code")
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

    def _td04_include_payment_due_date(self) -> bool:
        """Opzione A: emettere DataScadenzaPagamento anche sulle NC TD04 (default: no)."""
        raw = self._get_config_value(
            "electronic_invoicing", "td04_include_payment_due_date", "false"
        )
        if raw is None:
            return False
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    def _payment_term_days(self) -> int:
        """Giorni di pagamento da Data documento se payment_due_date assente/non valida."""
        raw = self._get_config_value(
            "electronic_invoicing",
            "payment_term_days",
            str(DEFAULT_PAYMENT_TERM_DAYS),
        )
        try:
            days = int(str(raw).strip())
            return days if days > 0 else DEFAULT_PAYMENT_TERM_DAYS
        except (TypeError, ValueError):
            return DEFAULT_PAYMENT_TERM_DAYS

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
    
    def _load_tax(self, id_tax: Optional[int]) -> Optional[Tax]:
        if not id_tax:
            return None
        return self.db.query(Tax).filter(Tax.id_tax == id_tax).first()

    def _enrich_line_items_with_tax(
        self, line_items: list, order_data: Dict[str, Any]
    ) -> list:
        """Arricchisce righe con tax_percentage, tax_nature, tax_note (per riga id_tax + VIES)."""
        vies_eligible = vies_eligible_from_order_data(order_data)
        enriched = []
        for line in line_items:
            tax = self._load_tax(line.get("id_tax"))
            line_tax = resolve_line_tax(
                tax, vies_eligible=vies_eligible, is_product_line=True
            )
            enriched.append(enrich_line_item_tax_fields(line, line_tax))
        return enriched

    def _resolve_shipping_line_tax(self, order_data: Dict[str, Any]) -> FatturaPALineTax:
        """Aliquota/natura spedizione — non forza VIES N3.2 (può restare 22%)."""
        tax = self._load_tax(order_data.get("shipping_id_tax"))
        if tax:
            return resolve_line_tax(
                tax,
                vies_eligible=vies_eligible_from_order_data(order_data),
                is_product_line=False,
            )
        pct = order_data.get("shipping_tax_percentage", 22.0)
        return FatturaPALineTax(
            aliquota=Decimal(str(pct)),
            natura=None,
            riferimento_normativo=None,
        )

    def _append_dettaglio_linea_tax_tags(
        self, dettaglio_linea: ET.Element, line_tax: FatturaPALineTax
    ) -> None:
        self._create_element(
            dettaglio_linea, "AliquotaIVA", f"{float(line_tax.aliquota):.2f}"
        )
        if line_tax.natura:
            self._create_element(dettaglio_linea, "Natura", line_tax.natura)

    def _line_tax_for_riepilogo(
        self, line_tax: FatturaPALineTax, net_total: Decimal
    ) -> Dict[str, Any]:
        return {
            "line_net_total": float(net_total),
            "tax_percentage": float(line_tax.aliquota),
            "tax_nature": line_tax.natura,
            "tax_note": line_tax.riferimento_normativo,
        }

    def _fattura_pa_line_tax_from_enriched(self, line: Dict[str, Any]) -> FatturaPALineTax:
        return FatturaPALineTax(
            aliquota=Decimal(str(line.get("tax_percentage", 22))),
            natura=line.get("tax_nature"),
            riferimento_normativo=line.get("tax_note"),
        )

    def _create_element(self, parent, tag: str, text: str = None, use_prefix: bool = False, **attrs) -> ET.Element:
        """Helper per creare elementi XML"""
        element_tag = f"p:{tag}" if use_prefix else tag
        element = ET.SubElement(parent, element_tag)
        if text:
            element.text = text
        for key, value in attrs.items():
            element.set(key, value)
        return element

    def _append_sede(self, parent: ET.Element, fields: Dict[str, Any]) -> ET.Element:
        """
        Serializza blocco Sede FatturaPA (ordine XSD).
        Ommette NumeroCivico/Provincia se assenti in ``fields`` (mai tag vuoti).
        """
        sede = self._create_element(parent, "Sede")
        self._create_element(sede, "Indirizzo", fields["Indirizzo"])
        if fields.get("NumeroCivico"):
            self._create_element(sede, "NumeroCivico", fields["NumeroCivico"])
        self._create_element(sede, "CAP", fields["CAP"])
        self._create_element(sede, "Comune", fields["Comune"])
        if fields.get("Provincia"):
            self._create_element(sede, "Provincia", fields["Provincia"])
        self._create_element(sede, "Nazione", fields["Nazione"])
        return sede
    
    def _generate_filename(self, document_number: str) -> str:
        """
        Genera il nome del file XML FatturaPA (formato SDI).

        [IdPaese][IdCodice]_[ProgressivoInvio].xml — es. IT08632861210_101164.xml
        """
        return build_fatturapa_filename("IT", self.vat_number or "", document_number)

    def _generate_xml(self, order_data: Dict[str, Any], line_items: list, document_number: str, include_shipping: bool = True) -> str:
        """
        Genera l'XML FatturaPA secondo le specifiche ufficiali
        
        Args:
            order_data: Dati dell'ordine/documento
            line_items: Dettagli articoli (possono essere order_details o fiscal_document_details trasformati)
            document_number: Numero documento progressivo
            include_shipping: Se True, include le spese di spedizione (default: True)
        """
        customer_name = order_data.get('invoice_firstname', '') + ' ' + order_data.get('invoice_lastname', '')
        customer_company = order_data.get('invoice_company') or order_data.get('customer_company', '')
        customer_cf = order_data.get('customer_fiscal_code', '')
        customer_pec = order_data.get('invoice_pec', '')
        customer_sdi = order_data.get('invoice_sdi', '')
        country_iso = (order_data.get('country_iso') or 'IT').upper()

        customer_vat_raw = order_data.get('invoice_vat', '')
        customer_vat = normalize_customer_vat(customer_vat_raw, country_iso)

        total_amount = float(order_data.get('total_price', 0))

        if line_items and "tax_percentage" not in line_items[0]:
            line_items = self._enrich_line_items_with_tax(line_items, order_data)

        riepilogo_lines: List[Dict[str, Any]] = []

        logger.debug(
            "Generazione XML FatturaPA doc=%s lines=%s country=%s vies=%s",
            document_number,
            len(line_items),
            country_iso,
            vies_eligible_from_order_data(order_data),
        )

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
        self._create_element(id_trasmittente, "IdCodice", normalize_id_codice(self.vat_number))
        
        self._create_element(dati_trasmissione, "ProgressivoInvio", document_number)
        self._create_element(dati_trasmissione, "FormatoTrasmissione", "FPR12")

        codice_destinatario = resolve_codice_destinatario(country_iso, customer_sdi)
        self._create_element(dati_trasmissione, "CodiceDestinatario", codice_destinatario)

        # Ordine XSD: ContattiTrasmittente prima di PECDestinatario
        if self.company_phone or self.company_email:
            contatti_trasmittente = self._create_element(dati_trasmissione, "ContattiTrasmittente")
            if self.company_phone:
                self._create_element(contatti_trasmittente, "Telefono", self.company_phone)
            if self.company_email:
                self._create_element(contatti_trasmittente, "Email", self.company_email)

        if customer_pec:
            self._create_element(dati_trasmissione, "PECDestinatario", customer_pec)
        elif codice_destinatario == "0000000":
            logger.warning(
                "CodiceDestinatario=0000000 senza PECDestinatario: "
                "recapito SDI solo via area riservata (doc %s)",
                document_number,
            )

        # CedentePrestatore
        cedente = self._create_element(header, "CedentePrestatore")
        
        dati_anagrafici_cedente = self._create_element(cedente, "DatiAnagrafici")
        id_fiscale_cedente = self._create_element(dati_anagrafici_cedente, "IdFiscaleIVA")
        self._create_element(id_fiscale_cedente, "IdPaese", "IT")
        cedente_id_codice = normalize_id_codice(self.vat_number or "")
        self._create_element(id_fiscale_cedente, "IdCodice", cedente_id_codice)

        # CodiceFiscale cedente IT = IdCodice P.IVA (allineato a IdFiscaleIVA)
        if cedente_id_codice:
            self._create_element(dati_anagrafici_cedente, "CodiceFiscale", cedente_id_codice)
        
        anagrafica_cedente = self._create_element(dati_anagrafici_cedente, "Anagrafica")
        self._create_element(anagrafica_cedente, "Denominazione", self.company_name)
        
        # Recupera il regime fiscale dalla configurazione, default RF01 se null
        tax_regime = self._get_config_value("electronic_invoicing", "tax_regime", "RF01")
        self._create_element(dati_anagrafici_cedente, "RegimeFiscale", tax_regime)
        
        self._append_sede(
            cedente,
            build_sede_fields(
                indirizzo=self.company_address or "",
                nazione="IT",
                comune=self.company_city or "",
                cap=self.company_cap,
                numero_civico=self.company_civic,
                provincia=self.company_province,
            ),
        )

        contatti_cedente = self._create_element(cedente, "Contatti")
        if self.company_phone:
            self._create_element(contatti_cedente, "Telefono", self.company_phone)
        if self.company_email:
            self._create_element(contatti_cedente, "Email", self.company_email)

        if self.company_contact:
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
            logger.debug("CodiceFiscale cessionario non presente")
        
        anagrafica_cessionario = self._create_element(dati_anagrafici_cessionario, "Anagrafica")
        
        if customer_company:
            self._create_element(anagrafica_cessionario, "Denominazione", customer_company)
        else:
            name_parts = customer_name.strip().split(' ', 1)
            if len(name_parts) >= 1:
                self._create_element(anagrafica_cessionario, "Nome", name_parts[0])
            if len(name_parts) >= 2:
                self._create_element(anagrafica_cessionario, "Cognome", name_parts[1])
        
        indirizzo = order_data.get('invoice_address1', 'VIA CLIENTE')
        indirizzo_pulito = indirizzo.replace(',', '').replace(';', '').strip()
        if not indirizzo_pulito:
            error_msg = "Indirizzo cliente non può essere vuoto"
            logger.error(f"ERRORE VALIDAZIONE: {error_msg}")
            raise ValueError(error_msg)
        self._append_sede(
            cessionario,
            build_sede_fields(
                indirizzo=indirizzo_pulito,
                nazione=country_iso,
                comune=order_data.get('invoice_city', 'MILANO'),
                cap=order_data.get('invoice_postcode'),
                numero_civico=order_data.get('invoice_address2'),
                provincia=order_data.get('invoice_state'),
            ),
        )

        # Body
        body = self._create_element(root, "FatturaElettronicaBody")
        
        # DatiGenerali
        dati_generali = self._create_element(body, "DatiGenerali")
        dati_generali_documento = self._create_element(dati_generali, "DatiGeneraliDocumento")
        
        # TipoDocumento viene passato come parametro (TD01 per fatture, TD04 per note di credito)
        tipo_documento = order_data.get('tipo_documento_fe')
        self._create_element(dati_generali_documento, "TipoDocumento", tipo_documento)
        self._create_element(dati_generali_documento, "Divisa", "EUR")
        document_date = resolve_document_date(order_data)
        self._create_element(dati_generali_documento, "Data", document_date.strftime("%Y-%m-%d"))
        # Converte il document_number in intero per il campo Numero
        numero_sequenziale = int(document_number)
        self._create_element(dati_generali_documento, "Numero", str(numero_sequenziale))
        self._create_element(dati_generali_documento, "ImportoTotaleDocumento", f"{total_amount:.2f}")
        # Arrotondamento: aggiunto dopo DatiRiepilogo (stesso elemento, ordine XSD)

        # TD04: riferimento obbligatorio alla fattura originale (BE-PA-P0-06)
        if tipo_documento == "TD04":
            linked_number = format_id_documento(order_data.get("linked_invoice_number"))
            if not linked_number:
                raise ValueError(
                    "Nota di credito TD04 richiede fattura di riferimento "
                    "(linked_invoice_number / id_fiscal_document_ref)"
                )
            dati_collegate = self._create_element(dati_generali, "DatiFattureCollegate")
            self._create_element(dati_collegate, "IdDocumento", linked_number)
            linked_date = resolve_linked_invoice_date(order_data)
            if linked_date:
                self._create_element(
                    dati_collegate, "Data", linked_date.strftime("%Y-%m-%d")
                )

        # DatiBeniServizi
        dati_beni_servizi = self._create_element(body, "DatiBeniServizi")

        # DettaglioLinee — aliquota/natura per riga (id_tax + VIES N3.2 su prodotti)
        line_num = 0
        for detail in line_items:
            line_num += 1
            line_tax = self._fattura_pa_line_tax_from_enriched(detail)
            dettaglio_linea = self._create_element(dati_beni_servizi, "DettaglioLinee")
            self._create_element(dettaglio_linea, "NumeroLinea", str(line_num))
            self._create_element(dettaglio_linea, "Descrizione", detail.get('product_name', 'Prodotto'))

            product_qty_raw = detail.get('product_qty')
            quantita = float(product_qty_raw) if product_qty_raw is not None else 1.0
            self._create_element(dettaglio_linea, "Quantita", f"{quantita:.2f}")

            product_price_raw = detail.get('product_price', 0)
            prezzo_unitario_netto = float(product_price_raw)
            self._create_element(dettaglio_linea, "PrezzoUnitario", f"{prezzo_unitario_netto:.2f}")

            reduction_percent_raw = detail.get('reduction_percent', 0)
            reduction_amount_raw = detail.get('reduction_amount', 0)
            reduction_percent = float(reduction_percent_raw) if reduction_percent_raw is not None else 0.0
            reduction_amount = float(reduction_amount_raw) if reduction_amount_raw is not None else 0.0

            prezzo_totale_base = float(prezzo_unitario_netto) * quantita
            prezzo_totale_netto = prezzo_totale_base

            if reduction_percent != 0:
                sconto = prezzo_totale_base * (reduction_percent / 100)
                prezzo_totale_netto = prezzo_totale_base - sconto
            elif reduction_amount != 0:
                prezzo_totale_netto = prezzo_totale_base - reduction_amount

            prezzo_totale_netto = Decimal(str(prezzo_totale_netto)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            if reduction_percent != 0 or reduction_amount != 0:
                sconto_maggiorazione = self._create_element(dettaglio_linea, "ScontoMaggiorazione")
                self._create_element(sconto_maggiorazione, "Tipo", "SC")
                if reduction_percent != 0:
                    self._create_element(sconto_maggiorazione, "Percentuale", f"{reduction_percent:.2f}")
                elif reduction_amount != 0:
                    self._create_element(sconto_maggiorazione, "Importo", f"{reduction_amount:.2f}")

            self._create_element(dettaglio_linea, "PrezzoTotale", f"{prezzo_totale_netto:.2f}")
            self._append_dettaglio_linea_tax_tags(dettaglio_linea, line_tax)
            riepilogo_lines.append(
                self._line_tax_for_riepilogo(line_tax, prezzo_totale_netto)
            )

        # Buoni sconto ordine: non applicare su TD04 (totali NC senza voucher carrello).
        # Su TD01 resta la riga "Buoni Sconto" da order.total_discounts.
        total_discounts = float(order_data.get('total_discounts', 0))
        if tipo_documento == "TD04":
            total_discounts = 0.0
        if total_discounts > 0:
            discount_tax = (
                self._fattura_pa_line_tax_from_enriched(line_items[0])
                if line_items
                else FatturaPALineTax(Decimal("22"), None, None)
            )
            discount_rate = float(discount_tax.aliquota)
            if discount_rate == 0:
                total_discounts_no_iva = total_discounts
            else:
                total_discounts_no_iva = total_discounts / (1 + discount_rate / 100)
            total_discounts_no_iva = Decimal(str(total_discounts_no_iva)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            line_num += 1
            dettaglio_sconto = self._create_element(dati_beni_servizi, "DettaglioLinee")
            self._create_element(dettaglio_sconto, "NumeroLinea", str(line_num))
            self._create_element(dettaglio_sconto, "TipoCessionePrestazione", "SC")
            self._create_element(dettaglio_sconto, "Descrizione", "Buoni Sconto")
            self._create_element(dettaglio_sconto, "Quantita", "1.00")
            self._create_element(dettaglio_sconto, "PrezzoUnitario", f"{-float(total_discounts_no_iva):.2f}")
            self._create_element(dettaglio_sconto, "PrezzoTotale", f"{-float(total_discounts_no_iva):.2f}")
            self._append_dettaglio_linea_tax_tags(dettaglio_sconto, discount_tax)
            riepilogo_lines.append(
                self._line_tax_for_riepilogo(discount_tax, -total_discounts_no_iva)
            )

        # Spese di spedizione (aliquota spedizione — può differire da prodotti VIES)
        shipping_price = float(order_data.get('shipping_price_tax_excl', 0))
        if include_shipping and shipping_price > 0:
            shipping_tax = self._resolve_shipping_line_tax(order_data)
            shipping_net = Decimal(str(shipping_price)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            line_num += 1
            dettaglio_spedizione = self._create_element(dati_beni_servizi, "DettaglioLinee")
            self._create_element(dettaglio_spedizione, "NumeroLinea", str(line_num))
            self._create_element(dettaglio_spedizione, "TipoCessionePrestazione", "AC")
            self._create_element(dettaglio_spedizione, "Descrizione", "SPESE")
            self._create_element(dettaglio_spedizione, "PrezzoUnitario", f"{shipping_net:.2f}")
            self._create_element(dettaglio_spedizione, "PrezzoTotale", f"{shipping_net:.2f}")
            self._append_dettaglio_linea_tax_tags(dettaglio_spedizione, shipping_tax)
            riepilogo_lines.append(
                self._line_tax_for_riepilogo(shipping_tax, shipping_net)
            )

        # DatiRiepilogo — un blocco per (AliquotaIVA, Natura); ordine XSD
        riepilogo_groups = build_riepilogo_groups(riepilogo_lines)
        for group in riepilogo_groups:
            dati_riepilogo = self._create_element(dati_beni_servizi, "DatiRiepilogo")
            self._create_element(
                dati_riepilogo, "AliquotaIVA", f"{group['AliquotaIVA']:.2f}"
            )
            if group.get("Natura"):
                self._create_element(dati_riepilogo, "Natura", group["Natura"])
            self._create_element(
                dati_riepilogo, "ImponibileImporto", f"{group['ImponibileImporto']:.2f}"
            )
            self._create_element(dati_riepilogo, "Imposta", f"{group['Imposta']:.2f}")
            self._create_element(dati_riepilogo, "EsigibilitaIVA", "I")
            if group.get("RiferimentoNormativo"):
                self._create_element(
                    dati_riepilogo, "RiferimentoNormativo", group["RiferimentoNormativo"]
                )

        # Arrotondamento sempre presente (anche 0.00) dopo ImportoTotaleDocumento
        arrotondamento = compute_arrotondamento(total_amount, riepilogo_groups)
        self._create_element(
            dati_generali_documento, "Arrotondamento", f"{arrotondamento:.2f}"
        )

        # DatiPagamento
        dati_pagamento = self._create_element(body, "DatiPagamento")
        
        # CondizioniPagamento (TP01=immediato, TP02=scadenza, TP03=rate)
        condizioni_pagamento = order_data.get('condizioni_pagamento', 'TP02')  # Default: scadenza
        self._create_element(dati_pagamento, "CondizioniPagamento", condizioni_pagamento)
        
        # DettaglioPagamento — ordine XSD: Modalita → DataScadenza → Importo → Istituto → IBAN
        dettaglio_pagamento = self._create_element(dati_pagamento, "DettaglioPagamento")
        
        fiscal_mode_payment = order_data.get('fiscal_mode_payment', 'MP05')  # Default: bonifico
        if not fiscal_mode_payment or fiscal_mode_payment not in [f'MP{i:02d}' for i in range(1, 24)]:
            fiscal_mode_payment = 'MP05'  # Fallback a bonifico
            logger.warning("Modalita pagamento non valida, uso default MP05")
        
        self._create_element(dettaglio_pagamento, "ModalitaPagamento", fiscal_mode_payment)

        # TD04 storno: di default omettere DataScadenzaPagamento (Opzione B).
        # Flag electronic_invoicing.td04_include_payment_due_date=true → Opzione A.
        include_scadenza = condizioni_pagamento == "TP02"
        if tipo_documento == "TD04":
            include_scadenza = include_scadenza and self._td04_include_payment_due_date()
        if include_scadenza:
            term_days = self._payment_term_days()
            scadenza = resolve_payment_due_date(order_data, payment_term_days=term_days)
            self._create_element(
                dettaglio_pagamento,
                "DataScadenzaPagamento",
                scadenza.strftime("%Y-%m-%d"),
            )

        self._create_element(dettaglio_pagamento, "ImportoPagamento", f"{total_amount:.2f}")

        if fiscal_mode_payment in PAYMENT_MODES_REQUIRING_IBAN:
            if self.company_bank_name:
                self._create_element(
                    dettaglio_pagamento, "IstitutoFinanziario", self.company_bank_name
                )
            if self.company_iban:
                self._create_element(dettaglio_pagamento, "IBAN", self.company_iban)
        
        ET.indent(root, space="  ", level=0)
        xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
        logger.debug("XML FatturaPA generato (%s caratteri) per doc %s", len(xml_str), document_number)
        
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
                        logger.info("UploadStart1 completato: %s", name)
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
            endpoint = "UploadStop1"
            url = f"{self.base_url}/{endpoint}/{self.api_key}/{name}"
            
            status_code, _, body = await self._http_request('GET', url)
            
            if status_code == 200:
                try:
                    result = json.loads(body)
                    logger.info("UploadStop completato: %s", endpoint)
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

            address = self.db.query(Address).filter(
                Address.id_address == order.id_address_invoice
            ).first()
            if not address:
                raise ValueError("Indirizzo di fatturazione non trovato")
            
            # Prepara order_data con tipo documento
            order_data = self._prepare_order_data_from_fiscal_document(fiscal_doc, order, address)
            
            # Recupera line items da fiscal_document_details (non da order_details)
            line_items = self._get_order_details_for_fiscal_document(fiscal_doc)
            line_items = self._enrich_line_items_with_tax(line_items, order_data)
            
            # Determina se includere spese di spedizione dal campo includes_shipping del documento
            # Usa il valore salvato nel FiscalDocument (gestito al momento della creazione)
            include_shipping = fiscal_doc.includes_shipping
            
            # Prepara company_data per validazione (CF cedente = IdCodice P.IVA)
            cedente_id = normalize_id_codice(self.vat_number or "")
            company_data = {
                'vat_number': cedente_id,
                'fiscal_code': cedente_id,
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

            # Validazione XSD ufficiale (BE-PA-P0-02)
            xsd_result = validate_fatturapa_xml(xml_content)
            if not xsd_result["valid"]:
                logger.error(
                    "Validazione XSD FatturaPA fallita per fiscal document %s: %s errori",
                    id_fiscal_document,
                    len(xsd_result["errors"]),
                )
                return {
                    "status": "validation_error",
                    "errors": xsd_result["errors"],
                }
            
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
        
        country_iso = 'IT'
        if address.id_country:
            country = self.db.query(Country).filter(
                Country.id_country == address.id_country
            ).first()
            if country:
                country_iso = country.iso_code

        customer_company = address.company
        provincia_abbreviation = resolve_invoice_state(address.state, country_iso)

        tax_electronic_code = None
        tax_note = None
        id_tax = customer.get("id_tax")
        if id_tax:
            tax = self.db.query(Tax).filter(Tax.id_tax == id_tax).first()
            if tax:
                tax_electronic_code = tax.electronic_code
                tax_note = tax.note

        linked_invoice_number = None
        linked_invoice_date = None
        if fiscal_doc.tipo_documento_fe == "TD04" and fiscal_doc.id_fiscal_document_ref:
            referenced = fiscal_doc.referenced_document
            if referenced is None:
                referenced = (
                    self.db.query(FiscalDocument)
                    .filter(
                        FiscalDocument.id_fiscal_document
                        == fiscal_doc.id_fiscal_document_ref
                    )
                    .first()
                )
            if referenced:
                linked_invoice_number = (
                    referenced.document_number or referenced.internal_number
                )
                linked_invoice_date = referenced.date_add
        
        return {
            'id_order': order.id_order,
            'tipo_documento_fe': fiscal_doc.tipo_documento_fe,  # TD01 o TD04
            'id_fiscal_document_ref': fiscal_doc.id_fiscal_document_ref,
            'linked_invoice_number': linked_invoice_number,
            'linked_invoice_date': linked_invoice_date,
            
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
            'invoice_company': customer_company or '',
            
            # Altri campi legacy
            'address_line1': address.address1,
            'address_line2': address.address2,
            'city': address.city,
            'postcode': address.postcode,
            'country_iso': country_iso,
            'provincia': provincia_abbreviation,
            'pec': address.pec,
            'sdi': address.sdi,
            'total_price': fiscal_doc.total_price_with_tax or 0.0,
            # Su TD04 non riusare i buoni carrello ordine (create_credit_note non li include nei totali)
            'total_discounts': (
                0.0
                if fiscal_doc.tipo_documento_fe == "TD04"
                else (order.total_discounts or 0.0)
            ),
            'shipping_price_tax_excl': customer.get('shipping_price_tax_excl', 0.0),
            'shipping_id_tax': customer.get('shipping_id_tax'),
            'shipping_tax_percentage': customer.get('shipping_tax_percentage', 22.0),
            'id_tax': customer.get('id_tax'),
            'tax_electronic_code': tax_electronic_code,
            'tax_note': tax_note,
            'tax_percentage_customer': customer.get('tax_percentage_customer'),
            'vies_status': (
                order.vies_status.value if order.vies_status is not None else None
            ),
            # date_add ordine (legacy / audit; DataScadenza usa document_date)
            'date_add': order.date_add,
            # data legale documento fiscale → DatiGeneraliDocumento/Data
            'document_date': fiscal_doc.date_add,
            'payment_due_date': order.payment_due_date,
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
            
            # Calcola reduction dal confronto tra total_price_with_tax e prezzo base
            prezzo_base = fdd.unit_price * fdd.product_qty
            sconto = prezzo_base - fdd.total_price_with_tax
            
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
                'product_qty': fdd.product_qty,  
                'product_price': fdd.unit_price,
                'reduction_percent': reduction_percent,
                'reduction_amount': reduction_amount,
                'id_tax': tax_id
            })
        
        return details
