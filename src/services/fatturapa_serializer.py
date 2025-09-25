"""
Serializer XML per FatturaPA con ordinamento deterministico e gestione opzionali
"""

import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Optional, List, Union
from datetime import date
from src.schemas.fatturapa_models import (
    FatturaElettronica, FatturaElettronicaHeader, FatturaElettronicaBody,
    DatiTrasmissione, CedentePrestatore, CessionarioCommittente,
    DatiGenerali, DatiBeniServizi, DatiPagamento
)


class FatturaPASerializer:
    """Serializer XML per FatturaPA con ordinamento deterministico"""
    
    def __init__(self):
        self.namespace = "http://www.fatturapa.gov.it/sdi/messaggi/v1.0"
        self.root_ns = {"": self.namespace}
    
    def to_xml(self, fattura: FatturaElettronica) -> str:
        """Converte FatturaElettronica in XML"""
        root = ET.Element("FatturaElettronica")
        root.set("xmlns", self.namespace)
        root.set("versione", "FPR12")
        
        # Header
        header_elem = self._serialize_header(fattura.fattura_elettronica_header)
        root.append(header_elem)
        
        # Body
        body_elem = self._serialize_body(fattura.fattura_elettronica_body)
        root.append(body_elem)
        
        return ET.tostring(root, encoding='unicode', xml_declaration=True)
    
    def _serialize_header(self, header: FatturaElettronicaHeader) -> ET.Element:
        """Serializza FatturaElettronicaHeader"""
        header_elem = ET.Element("FatturaElettronicaHeader")
        
        # DatiTrasmissione
        dati_trasmissione = self._serialize_dati_trasmissione(header.dati_trasmissione)
        header_elem.append(dati_trasmissione)
        
        # CedentePrestatore
        cedente = self._serialize_cedente_prestatore(header.cedente_prestatore)
        header_elem.append(cedente)
        
        # CessionarioCommittente
        cessionario = self._serialize_cessionario_committente(header.cessionario_committente)
        header_elem.append(cessionario)
        
        return header_elem
    
    def _serialize_dati_trasmissione(self, dati: DatiTrasmissione) -> ET.Element:
        """Serializza DatiTrasmissione"""
        elem = ET.Element("DatiTrasmissione")
        
        # IdTrasmittente
        id_trasmittente = ET.SubElement(elem, "IdTrasmittente")
        self._emit(id_trasmittente, "IdPaese", dati.id_trasmittente.id_paese)
        self._emit(id_trasmittente, "IdCodice", dati.id_trasmittente.id_codice)
        
        # ProgressivoInvio
        self._emit(elem, "ProgressivoInvio", dati.progressivo_invio)
        
        # FormatoTrasmissione
        self._emit(elem, "FormatoTrasmissione", dati.formato_trasmissione.value)
        
        # CodiceDestinatario
        self._emit(elem, "CodiceDestinatario", dati.codice_destinatario)
        
        # ContattiTrasmittente (opzionale)
        if dati.contatti_trasmittente:
            contatti = ET.SubElement(elem, "ContattiTrasmittente")
            self._emit(contatti, "Telefono", dati.contatti_trasmittente.telefono)
            self._emit(contatti, "Email", dati.contatti_trasmittente.email)
        
        # PECDestinatario (opzionale)
        self._emit(elem, "PECDestinatario", dati.pec_destinatario)
        
        return elem
    
    def _serialize_cedente_prestatore(self, cedente: CedentePrestatore) -> ET.Element:
        """Serializza CedentePrestatore"""
        elem = ET.Element("CedentePrestatore")
        
        # DatiAnagrafici
        dati_anagrafici = ET.SubElement(elem, "DatiAnagrafici")
        
        # IdFiscaleIVA
        id_fiscale = ET.SubElement(dati_anagrafici, "IdFiscaleIVA")
        self._emit(id_fiscale, "IdPaese", cedente.dati_anagrafici.id_fiscale_iva.id_paese)
        self._emit(id_fiscale, "IdCodice", cedente.dati_anagrafici.id_fiscale_iva.id_codice)
        
        # CodiceFiscale (opzionale)
        self._emit(dati_anagrafici, "CodiceFiscale", cedente.dati_anagrafici.codice_fiscale)
        
        # Anagrafica
        anagrafica = ET.SubElement(dati_anagrafici, "Anagrafica")
        self._emit(anagrafica, "Denominazione", cedente.dati_anagrafici.anagrafica.denominazione)
        self._emit(anagrafica, "Nome", cedente.dati_anagrafici.anagrafica.nome)
        self._emit(anagrafica, "Cognome", cedente.dati_anagrafici.anagrafica.cognome)
        
        # RegimeFiscale
        self._emit(dati_anagrafici, "RegimeFiscale", cedente.dati_anagrafici.regime_fiscale.value)
        
        # Sede
        sede = ET.SubElement(elem, "Sede")
        self._emit(sede, "Indirizzo", cedente.sede.indirizzo)
        self._emit(sede, "CAP", cedente.sede.cap)
        self._emit(sede, "Comune", cedente.sede.comune)
        self._emit(sede, "Provincia", cedente.sede.provincia)
        self._emit(sede, "Nazione", cedente.sede.nazione)
        
        # Contatti
        contatti = ET.SubElement(elem, "Contatti")
        self._emit(contatti, "Telefono", cedente.contatti.telefono)
        self._emit(contatti, "Email", cedente.contatti.email)
        
        return elem
    
    def _serialize_cessionario_committente(self, cessionario: CessionarioCommittente) -> ET.Element:
        """Serializza CessionarioCommittente"""
        elem = ET.Element("CessionarioCommittente")
        
        # DatiAnagrafici
        dati_anagrafici = ET.SubElement(elem, "DatiAnagrafici")
        
        # IdFiscaleIVA
        id_fiscale = ET.SubElement(dati_anagrafici, "IdFiscaleIVA")
        self._emit(id_fiscale, "IdPaese", cessionario.dati_anagrafici.id_fiscale_iva.id_paese)
        self._emit(id_fiscale, "IdCodice", cessionario.dati_anagrafici.id_fiscale_iva.id_codice)
        
        # CodiceFiscale (opzionale)
        self._emit(dati_anagrafici, "CodiceFiscale", cessionario.dati_anagrafici.codice_fiscale)
        
        # Anagrafica
        anagrafica = ET.SubElement(dati_anagrafici, "Anagrafica")
        self._emit(anagrafica, "Denominazione", cessionario.dati_anagrafici.anagrafica.denominazione)
        self._emit(anagrafica, "Nome", cessionario.dati_anagrafici.anagrafica.nome)
        self._emit(anagrafica, "Cognome", cessionario.dati_anagrafici.anagrafica.cognome)
        
        # RegimeFiscale
        self._emit(dati_anagrafici, "RegimeFiscale", cessionario.dati_anagrafici.regime_fiscale.value)
        
        # Sede
        sede = ET.SubElement(elem, "Sede")
        self._emit(sede, "Indirizzo", cessionario.sede.indirizzo)
        self._emit(sede, "CAP", cessionario.sede.cap)
        self._emit(sede, "Comune", cessionario.sede.comune)
        self._emit(sede, "Provincia", cessionario.sede.provincia)
        self._emit(sede, "Nazione", cessionario.sede.nazione)
        
        return elem
    
    def _serialize_body(self, body: FatturaElettronicaBody) -> ET.Element:
        """Serializza FatturaElettronicaBody"""
        elem = ET.Element("FatturaElettronicaBody")
        
        # DatiGenerali
        dati_generali = self._serialize_dati_generali(body.dati_generali)
        elem.append(dati_generali)
        
        # DatiBeniServizi
        dati_beni_servizi = self._serialize_dati_beni_servizi(body.dati_beni_servizi)
        elem.append(dati_beni_servizi)
        
        # DatiPagamento (opzionale)
        if body.dati_pagamento:
            for pagamento in body.dati_pagamento:
                dati_pagamento = self._serialize_dati_pagamento(pagamento)
                elem.append(dati_pagamento)
        
        return elem
    
    def _serialize_dati_generali(self, dati: DatiGenerali) -> ET.Element:
        """Serializza DatiGenerali"""
        elem = ET.Element("DatiGenerali")
        
        # DatiGeneraliDocumento
        documento = ET.SubElement(elem, "DatiGeneraliDocumento")
        self._emit(documento, "TipoDocumento", dati.dati_generali_documento.tipo_documento.value)
        self._emit(documento, "Divisa", dati.dati_generali_documento.divisa)
        self._emit(documento, "Data", dati.dati_generali_documento.data.strftime("%Y-%m-%d"))
        self._emit(documento, "Numero", dati.dati_generali_documento.numero)
        
        # DatiRitenuta (opzionale)
        if dati.dati_generali_documento.dati_ritenuta:
            for ritenuta in dati.dati_generali_documento.dati_ritenuta:
                dati_ritenuta = ET.SubElement(documento, "DatiRitenuta")
                self._emit(dati_ritenuta, "TipoRitenuta", ritenuta.tipo_ritenuta.value)
                self._emit(dati_ritenuta, "ImportoRitenuta", self._format_decimal(ritenuta.importo_ritenuta))
                self._emit(dati_ritenuta, "AliquotaRitenuta", self._format_decimal(ritenuta.aliquota_ritenuta))
                self._emit(dati_ritenuta, "CausalePagamento", ritenuta.causale_pagamento)
        
        # ScontoMaggiorazione (opzionale)
        if dati.dati_generali_documento.sconto_maggiorazione:
            for sconto in dati.dati_generali_documento.sconto_maggiorazione:
                sconto_elem = ET.SubElement(documento, "ScontoMaggiorazione")
                self._emit(sconto_elem, "Tipo", sconto.tipo.value)
                self._emit(sconto_elem, "Percentuale", self._format_decimal(sconto.percentuale))
                self._emit(sconto_elem, "Importo", self._format_decimal(sconto.importo))
        
        # ImportoTotaleDocumento (opzionale)
        self._emit(documento, "ImportoTotaleDocumento", self._format_decimal(dati.dati_generali_documento.importo_totale_documento))
        
        # Causale (opzionale)
        if dati.dati_generali_documento.causale:
            for causale in dati.dati_generali_documento.causale:
                self._emit(documento, "Causale", causale)
        
        return elem
    
    def _serialize_dati_beni_servizi(self, dati: DatiBeniServizi) -> ET.Element:
        """Serializza DatiBeniServizi"""
        elem = ET.Element("DatiBeniServizi")
        
        # DettaglioLinee
        for linea in dati.dettaglio_linee:
            dettaglio = ET.SubElement(elem, "DettaglioLinee")
            self._emit(dettaglio, "NumeroLinea", str(linea.numero_linea))
            self._emit(dettaglio, "TipoCessionePrestazione", linea.tipo_cessione_prestazione.value if linea.tipo_cessione_prestazione else None)
            
            # CodiceArticolo (opzionale)
            if linea.codice_articolo:
                for codice in linea.codice_articolo:
                    codice_elem = ET.SubElement(dettaglio, "CodiceArticolo")
                    self._emit(codice_elem, "CodiceTipo", codice.codice_tipo)
                    self._emit(codice_elem, "CodiceValore", codice.codice_valore)
            
            self._emit(dettaglio, "Descrizione", linea.descrizione)
            self._emit(dettaglio, "Quantita", self._format_decimal(linea.quantita))
            self._emit(dettaglio, "PrezzoUnitario", self._format_decimal(linea.prezzo_unitario))
            self._emit(dettaglio, "PrezzoTotale", self._format_decimal(linea.prezzo_totale))
            self._emit(dettaglio, "AliquotaIVA", self._format_decimal(linea.aliquota_iva))
            self._emit(dettaglio, "Natura", linea.natura.value if linea.natura else None)
            self._emit(dettaglio, "Ritenuta", linea.ritenuta)
        
        # DatiRiepilogo
        for riepilogo in dati.dati_riepilogo:
            riepilogo_elem = ET.SubElement(elem, "DatiRiepilogo")
            self._emit(riepilogo_elem, "AliquotaIVA", self._format_decimal(riepilogo.aliquota_iva))
            self._emit(riepilogo_elem, "ImponibileImporto", self._format_decimal(riepilogo.imponibile_importo))
            self._emit(riepilogo_elem, "Imposta", self._format_decimal(riepilogo.imposta))
            self._emit(riepilogo_elem, "EsigibilitaIVA", riepilogo.esigibilita_iva.value if riepilogo.esigibilita_iva else None)
        
        return elem
    
    def _serialize_dati_pagamento(self, pagamento: DatiPagamento) -> ET.Element:
        """Serializza DatiPagamento"""
        elem = ET.Element("DatiPagamento")
        self._emit(elem, "CondizioniPagamento", pagamento.condizioni_pagamento.value)
        
        # DettaglioPagamento
        for dettaglio in pagamento.dettaglio_pagamento:
            dettaglio_elem = ET.SubElement(elem, "DettaglioPagamento")
            self._emit(dettaglio_elem, "ModalitaPagamento", dettaglio.modalita_pagamento.value)
            self._emit(dettaglio_elem, "ImportoPagamento", self._format_decimal(dettaglio.importo_pagamento))
            self._emit(dettaglio_elem, "DataScadenzaPagamento", dettaglio.data_scadenza.strftime("%Y-%m-%d") if dettaglio.data_scadenza else None)
        
        return elem
    
    def _emit(self, parent: ET.Element, tag: str, value: Union[str, int, float, Decimal, None]) -> None:
        """Emetti tag solo se valore non è None/vuoto"""
        if value is not None and value != "":
            if isinstance(value, (int, float, Decimal)):
                value = str(value)
            elif isinstance(value, str):
                value = value.strip()
                if value:
                    elem = ET.SubElement(parent, tag)
                    elem.text = value
            else:
                elem = ET.SubElement(parent, tag)
                elem.text = str(value)
    
    def _format_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        """Formatta Decimal per XML"""
        if value is None:
            return None
        return f"{value:.2f}".rstrip('0').rstrip('.')
