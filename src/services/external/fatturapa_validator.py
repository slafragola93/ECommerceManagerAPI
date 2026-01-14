import re
import base64
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
import logging

from src.services.core.tool import valida_piva


logger = logging.getLogger(__name__)


class FatturaPAValidator:
    """
    Validatore per XML FatturaPA
    
    Valida tutti i campi dell'XML secondo le specifiche FatturaPA
    prima della generazione, restituendo errori dettagliati se la validazione fallisce.
    """
    
    # Regole di validazione 
    VALIDATION_RULES = {
        # ===== HEADER - DATI TRASMISSIONE =====
        'IdTrasmittente/IdPaese': 'regex:/^[A-Z]{2}$/',
        'IdTrasmittente/IdCodice': 'partita_iva',
        'ProgressivoInvio': 'alfanumerico|max:20',
        'FormatoTrasmissione': 'enum:FPA12,FPR12',
        'CodiceDestinatario': 'codice_destinatario',
        'PECDestinatario': 'email_pec',
        'ContattiTrasmittente/Telefono': 'regex:/^[\\d\\s\\+\\-\\(\\)]{5,20}$/',
        'ContattiTrasmittente/Email': 'email',
        
        # ===== CEDENTE PRESTATORE =====
        'CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdPaese': 'regex:/^[A-Z]{2}$/',
        'CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdCodice': 'partita_iva',
        'CedentePrestatore/DatiAnagrafici/CodiceFiscale': 'codice_fiscale',
        'CedentePrestatore/DatiAnagrafici/Anagrafica/Denominazione': 'string|max:80|required_without:Nome,Cognome',
        'CedentePrestatore/DatiAnagrafici/Anagrafica/Nome': 'string|max:60|required_with:Cognome',
        'CedentePrestatore/DatiAnagrafici/Anagrafica/Cognome': 'string|max:60|required_with:Nome',
        'CedentePrestatore/DatiAnagrafici/Anagrafica/Titolo': 'string|max:10',
        'CedentePrestatore/DatiAnagrafici/Anagrafica/CodEORI': 'string|max:17',
        'CedentePrestatore/DatiAnagrafici/RegimeFiscale': 'regime_fiscale',
        'CedentePrestatore/Sede/Indirizzo': 'string|max:60|required',
        'CedentePrestatore/Sede/NumeroCivico': 'string|max:8',
        'CedentePrestatore/Sede/CAP': 'cap_italiano',
        'CedentePrestatore/Sede/Comune': 'string|max:60|required',
        'CedentePrestatore/Sede/Provincia': 'provincia_italiana',
        'CedentePrestatore/Sede/Nazione': 'regex:/^[A-Z]{2}$/',
        'CedentePrestatore/Contatti/Telefono': 'regex:/^[\\d\\s\\+\\-\\(\\)]{5,20}$/',
        'CedentePrestatore/Contatti/Email': 'email',
        'CedentePrestatore/Contatti/Fax': 'regex:/^[\\d\\s\\+\\-\\(\\)]{5,20}$/',
        'CedentePrestatore/RiferimentoAmministrazione': 'string|max:20',
        
        # ===== CESSIONARIO COMMITTENTE =====
        'CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdPaese': 'regex:/^[A-Z]{2}$/',
        'CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice': 'partita_iva_estera',
        'CessionarioCommittente/DatiAnagrafici/CodiceFiscale': 'codice_fiscale|required_without:IdFiscaleIVA',
        'CessionarioCommittente/DatiAnagrafici/Anagrafica/Denominazione': 'string|max:80|required_without:Nome,Cognome',
        'CessionarioCommittente/DatiAnagrafici/Anagrafica/Nome': 'string|max:60|required_with:Cognome',
        'CessionarioCommittente/DatiAnagrafici/Anagrafica/Cognome': 'string|max:60|required_with:Nome',
        'CessionarioCommittente/DatiAnagrafici/Anagrafica/Titolo': 'string|max:10',
        'CessionarioCommittente/DatiAnagrafici/Anagrafica/CodEORI': 'string|max:17',
        'CessionarioCommittente/Sede/Indirizzo': 'string|max:60|required',
        'CessionarioCommittente/Sede/NumeroCivico': 'string|max:8',
        'CessionarioCommittente/Sede/CAP': 'cap_internazionale',
        'CessionarioCommittente/Sede/Comune': 'string|max:60|required',
        'CessionarioCommittente/Sede/Provincia': 'provincia_internazionale',
        'CessionarioCommittente/Sede/Nazione': 'regex:/^[A-Z]{2}$/',
        
        # ===== TERZO INTERMEDIARIO (opzionale) =====
        'TerzoIntermediarioOSoggettoEmittente/DatiAnagrafici/IdFiscaleIVA/IdPaese': 'regex:/^[A-Z]{2}$/',
        'TerzoIntermediarioOSoggettoEmittente/DatiAnagrafici/IdFiscaleIVA/IdCodice': 'partita_iva',
        'TerzoIntermediarioOSoggettoEmittente/DatiAnagrafici/CodiceFiscale': 'codice_fiscale',
        'TerzoIntermediarioOSoggettoEmittente/DatiAnagrafici/Anagrafica/Denominazione': 'string|max:80|required',
        
        # ===== BODY - DATI GENERALI DOCUMENTO =====
        'DatiGeneraliDocumento/TipoDocumento': 'tipo_documento',
        'DatiGeneraliDocumento/Divisa': 'enum:EUR,USD,GBP,CHF',
        'DatiGeneraliDocumento/Data': 'data_fattura',
        'DatiGeneraliDocumento/Numero': 'numero_documento',
        'DatiGeneraliDocumento/DatiRitenuta/TipoRitenuta': 'tipo_ritenuta',
        'DatiGeneraliDocumento/DatiRitenuta/ImportoRitenuta': 'decimal:2|min:0',
        'DatiGeneraliDocumento/DatiRitenuta/AliquotaRitenuta': 'decimal:2|between:0,100',
        'DatiGeneraliDocumento/DatiRitenuta/CausalePagamento': 'causale_pagamento',
        'DatiGeneraliDocumento/DatiBollo/BolloVirtuale': 'enum:SI',
        'DatiGeneraliDocumento/DatiBollo/ImportoBollo': 'decimal:2|min:0',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/TipoCassa': 'tipo_cassa',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/AlCassa': 'decimal:2|between:0,100',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/ImportoContributoCassa': 'decimal:2|min:0',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/ImponibileCassa': 'decimal:2|min:0',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/AliquotaIVA': 'aliquota_iva',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/Ritenuta': 'enum:SI',
        'DatiGeneraliDocumento/DatiCassaPrevidenziale/Natura': 'natura_iva',
        'DatiGeneraliDocumento/ScontoMaggiorazione/Tipo': 'enum:SC,MG',
        'DatiGeneraliDocumento/ScontoMaggiorazione/Percentuale': 'decimal:2|between:0,100',
        'DatiGeneraliDocumento/ScontoMaggiorazione/Importo': 'decimal:2',
        
        # ===== DETTAGLIO LINEE =====
        'DettaglioLinee/NumeroLinea': 'integer|min:1',
        'DettaglioLinee/TipoCessionePrestazione': 'enum:SC,PR,AB,AC',
        'DettaglioLinee/CodiceArticolo/CodiceTipo': 'string|max:35',
        'DettaglioLinee/CodiceArticolo/CodiceValore': 'string|max:35',
        'DettaglioLinee/Descrizione': 'string|max:1000|required',
        'DettaglioLinee/Quantita': 'decimal:8|min:0',
        'DettaglioLinee/UnitaMisura': 'string|max:10',
        'DettaglioLinee/DataInizioPeriodo': 'date_format:Y-m-d',
        'DettaglioLinee/DataFinePeriodo': 'date_format:Y-m-d|after_or_equal:DataInizioPeriodo',
        'DettaglioLinee/PrezzoUnitario': 'decimal:8',
        'DettaglioLinee/ScontoMaggiorazione/Tipo': 'enum:SC,MG',
        'DettaglioLinee/ScontoMaggiorazione/Percentuale': 'decimal:2|between:0,100',
        'DettaglioLinee/ScontoMaggiorazione/Importo': 'decimal:2',
        'DettaglioLinee/PrezzoTotale': 'decimal:2|required',
        'DettaglioLinee/AliquotaIVA': 'aliquota_iva|required',
        'DettaglioLinee/Ritenuta': 'enum:SI',
        'DettaglioLinee/Natura': 'natura_iva_linea',
        'DettaglioLinee/RiferimentoAmministrazione': 'string|max:20',
        'DettaglioLinee/AltriDatiGestionali/TipoDato': 'string|max:10',
        'DettaglioLinee/AltriDatiGestionali/RiferimentoTesto': 'string|max:60',
        'DettaglioLinee/AltriDatiGestionali/RiferimentoNumero': 'decimal:8',
        'DettaglioLinee/AltriDatiGestionali/RiferimentoData': 'date_format:Y-m-d',
        
        # ===== DATI RIEPILOGO =====
        'DatiRiepilogo/AliquotaIVA': 'aliquota_iva|required',
        'DatiRiepilogo/Natura': 'natura_iva_riepilogo',
        'DatiRiepilogo/SpeseAccessorie': 'decimal:2|min:0',
        'DatiRiepilogo/Arrotondamento': 'decimal:2',
        'DatiRiepilogo/ImponibileImporto': 'decimal:2|required|min:0',
        'DatiRiepilogo/Imposta': 'decimal:2|required|min:0',
        'DatiRiepilogo/EsigibilitaIVA': 'enum:I,D,S',
        'DatiRiepilogo/RiferimentoNormativo': 'string|max:100',
        
        # ===== DATI PAGAMENTO =====
        'DatiPagamento/CondizioniPagamento': 'enum:TP01,TP02,TP03',
        'DatiPagamento/DettaglioPagamento/ModalitaPagamento': 'modalita_pagamento',
        'DatiPagamento/DettaglioPagamento/DataRiferimentoTerminiPagamento': 'date_format:Y-m-d',
        'DatiPagamento/DettaglioPagamento/GiorniTerminiPagamento': 'integer|between:0,999',
        'DatiPagamento/DettaglioPagamento/DataScadenzaPagamento': 'date_format:Y-m-d',
        'DatiPagamento/DettaglioPagamento/ImportoPagamento': 'decimal:2|required|min:0',
        'DatiPagamento/DettaglioPagamento/CodiceUfficioPostale': 'string|size:5',
        'DatiPagamento/DettaglioPagamento/CognomeQuietanzante': 'string|max:60',
        'DatiPagamento/DettaglioPagamento/NomeQuietanzante': 'string|max:60',
        'DatiPagamento/DettaglioPagamento/CFQuietanzante': 'codice_fiscale',
        'DatiPagamento/DettaglioPagamento/TitoloQuietanzante': 'string|max:10',
        'DatiPagamento/DettaglioPagamento/IstitutoFinanziario': 'string|max:80',
        'DatiPagamento/DettaglioPagamento/IBAN': 'iban',
        'DatiPagamento/DettaglioPagamento/ABI': 'regex:/^\\d{5}$/',
        'DatiPagamento/DettaglioPagamento/CAB': 'regex:/^\\d{5}$/',
        'DatiPagamento/DettaglioPagamento/BIC': 'bic',
        'DatiPagamento/DettaglioPagamento/ScontoPagamentoAnticipato': 'decimal:2|between:0,100',
        'DatiPagamento/DettaglioPagamento/DataLimitePagamentoAnticipato': 'date_format:Y-m-d',
        'DatiPagamento/DettaglioPagamento/PenalitaPagamentiRitardati': 'decimal:2|between:0,100',
        'DatiPagamento/DettaglioPagamento/DataDecorrenzaPenale': 'date_format:Y-m-d',
        'DatiPagamento/DettaglioPagamento/CodicePagamento': 'string|max:60',
        
        # ===== ALLEGATI (opzionali) =====
        'Allegati/NomeAttachment': 'string|max:60|required_with:Attachment',
        'Allegati/AlgoritmoCompressione': 'string|max:10',
        'Allegati/FormatoAttachment': 'string|max:10',
        'Allegati/DescrizioneAttachment': 'string|max:100',
        'Allegati/Attachment': 'base64',
    }
    
    def __init__(self):
        """Inizializza il validatore"""
        pass
    
    # ==================== CONTROLLI PERSONALIZZATI ====================
    
    def _validate_partita_iva(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida P.IVA italiana (11 cifre + check digit Luhn)
        
        Args:
            value: P.IVA da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "P.IVA non può essere vuota"
        
        # Rimuovi spazi e caratteri non numerici
        piva_clean = ''.join(filter(str.isdigit, value))
        
        if len(piva_clean) != 11:
            return False, f"P.IVA deve essere esattamente 11 cifre (ricevuto: {len(piva_clean)})"
        
        # Verifica check digit usando la funzione valida_piva
        try:
            is_valid, error_message = valida_piva(piva_clean)
            if not is_valid:
                return False, error_message
            return True, None
        except (ValueError, IndexError):
            return False, "P.IVA non valida: formato errato"
    
    def _validate_partita_iva_estera(self, value: str, country_code: str = 'IT') -> Tuple[bool, Optional[str]]:
        """
        Valida P.IVA estera secondo regole UE
        
        Args:
            value: P.IVA da validare
            country_code: Codice paese (2 caratteri ISO)
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "P.IVA non può essere vuota"
        
        # Rimuovi spazi e caratteri non alfanumerici
        piva_clean = ''.join(filter(str.isalnum, value.upper()))
        
        if country_code == 'IT':
            # Se Italia, usa validazione P.IVA italiana
            return self._validate_partita_iva(value)
        
        # Per altri paesi UE, validazione base (lunghezza variabile)
        if len(piva_clean) < 2:
            return False, f"P.IVA estera troppo corta (minimo 2 caratteri)"
        
        if len(piva_clean) > 15:
            return False, f"P.IVA estera troppo lunga (massimo 15 caratteri)"
        
        return True, None
    
    def _validate_codice_fiscale(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida Codice Fiscale italiano (16 caratteri alfanumerici + check)
        
        Args:
            value: Codice Fiscale da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "Codice Fiscale non può essere vuoto"
        
        cf_clean = value.upper().strip()
        
        if len(cf_clean) < 11 or len(cf_clean) > 16:
            return False, f"Codice Fiscale deve essere tra 11 e 16 caratteri (ricevuto: {len(cf_clean)})"
        
        # Per CF italiano standard (16 caratteri), verifica formato
        if len(cf_clean) == 16:
            # Formato: 6 caratteri (cognome) + 2 caratteri (nome) + 2 cifre (anno) + 1 carattere (mese) + 2 cifre (giorno) + 1 carattere (comune) + 1 carattere (check)
            if not re.match(r'^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$', cf_clean):
                return False, "Codice Fiscale italiano: formato non valido"
        
        return True, None
    
    def _validate_cap_italiano(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida CAP italiano (esattamente 5 cifre)
        
        Args:
            value: CAP da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "CAP non può essere vuoto"
        
        cap_clean = ''.join(filter(str.isdigit, value))
        
        if len(cap_clean) != 5:
            return False, f"CAP italiano deve essere esattamente 5 cifre (ricevuto: {len(cap_clean)})"
        
        return True, None
    
    def _validate_cap_internazionale(self, value: str, country_code: str = 'IT') -> Tuple[bool, Optional[str]]:
        """
        Valida CAP italiano o estero
        
        Args:
            value: CAP da validare
            country_code: Codice paese (2 caratteri ISO)
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "CAP non può essere vuoto"
        
        if country_code == 'IT':
            return self._validate_cap_italiano(value)
        
        # Per paesi esteri, validazione base (lunghezza variabile)
        cap_clean = value.strip()
        if len(cap_clean) < 3 or len(cap_clean) > 10:
            return False, f"CAP deve essere tra 3 e 10 caratteri (ricevuto: {len(cap_clean)})"
        
        return True, None
    
    def _validate_provincia_italiana(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida provincia italiana (2 caratteri maiuscoli)
        
        Args:
            value: Provincia da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "Provincia non può essere vuota"
        
        provincia_clean = value.upper().strip()
        
        if len(provincia_clean) != 2:
            return False, f"Provincia italiana deve essere esattamente 2 caratteri (ricevuto: {len(provincia_clean)})"
        
        return True, None
    
    def _validate_provincia_internazionale(self, value: str, country_code: str = 'IT') -> Tuple[bool, Optional[str]]:
        """
        Valida provincia (2 caratteri se Italia, opzionale se estero)
        
        Args:
            value: Provincia da validare
            country_code: Codice paese (2 caratteri ISO)
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            if country_code == 'IT':
                return False, "Provincia obbligatoria per nazione Italia"
            return True, None  # Opzionale per paesi esteri
        
        if country_code == 'IT':
            return self._validate_provincia_italiana(value)
        
        # Per paesi esteri, validazione base (lunghezza variabile)
        provincia_clean = value.strip()
        if len(provincia_clean) < 2 or len(provincia_clean) > 10:
            return False, f"Provincia deve essere tra 2 e 10 caratteri (ricevuto: {len(provincia_clean)})"
        
        return True, None
    
    def _validate_codice_destinatario(self, value: str, formato_trasmissione: str = 'FPR12') -> Tuple[bool, Optional[str]]:
        """
        Valida Codice Destinatario (6 o 7 caratteri o XXXXXXX)
        
        Args:
            value: Codice destinatario da validare
            formato_trasmissione: FPA12 o FPR12
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "CodiceDestinatario non può essere vuoto"
        
        codice_clean = value.strip()
        
        if codice_clean == "XXXXXXX":
            return True, None
        
        if formato_trasmissione == 'FPA12':
            # Fatture verso PA: 6 caratteri
            if len(codice_clean) != 6:
                return False, f"CodiceDestinatario per FPA12 deve essere esattamente 6 caratteri (ricevuto: {len(codice_clean)})"
        elif formato_trasmissione == 'FPR12':
            # Fatture verso privati: 7 caratteri
            if len(codice_clean) != 7:
                return False, f"CodiceDestinatario per FPR12 deve essere esattamente 7 caratteri o XXXXXXX (ricevuto: {len(codice_clean)})"
        
        return True, None
    
    def _validate_email_pec(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida formato email valido (PEC)
        
        Args:
            value: Email da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            return False, f"Email non valida: '{value}'"
        
        return True, None
    
    def _validate_regime_fiscale(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida codice regime fiscale (RF01-RF19)
        
        Args:
            value: Regime fiscale da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "RegimeFiscale non può essere vuoto"
        
        valid_regimes = {'RF01', 'RF02', 'RF03', 'RF04', 'RF05', 'RF06', 'RF07', 'RF08', 'RF09', 
                        'RF10', 'RF11', 'RF12', 'RF13', 'RF14', 'RF15', 'RF16', 'RF17', 'RF18', 'RF19'}
        
        if value not in valid_regimes:
            return False, f"RegimeFiscale '{value}' non valido (valori ammessi: RF01-RF19)"
        
        return True, None
    
    def _validate_tipo_documento(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida tipo documento (TD01, TD04, TD05, etc.)
        
        Args:
            value: Tipo documento da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "TipoDocumento non può essere vuoto"
        
        valid_types = {'TD01', 'TD02', 'TD03', 'TD04', 'TD05', 'TD06', 'TD16', 'TD17', 'TD18', 'TD19', 'TD20', 'TD21', 'TD22', 'TD23', 'TD24', 'TD25', 'TD26', 'TD27'}
        
        if value not in valid_types:
            return False, f"TipoDocumento '{value}' non valido (valori ammessi: TD01-TD27)"
        
        return True, None
    
    def _validate_data_fattura(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida data fattura (formato YYYY-MM-DD, non futura)
        
        Args:
            value: Data da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "Data non può essere vuota"
        
        try:
            data_fattura = datetime.strptime(value, '%Y-%m-%d').date()
            oggi = date.today()
            
            if data_fattura > oggi:
                return False, f"Data fattura non può essere futura (data: {value}, oggi: {oggi})"
            
            return True, None
        except ValueError:
            return False, f"Data non valida: formato atteso YYYY-MM-DD (ricevuto: '{value}')"
    
    def _validate_numero_documento(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida numero documento (deve contenere almeno una cifra)
        
        Args:
            value: Numero documento da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "Numero documento non può essere vuoto"
        
        if not any(c.isdigit() for c in value):
            return False, "Numero documento deve contenere almeno una cifra"
        
        return True, None
    
    def _validate_tipo_ritenuta(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida tipo ritenuta (RT01, RT02, etc.)
        
        Args:
            value: Tipo ritenuta da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        valid_types = {'RT01', 'RT02', 'RT03', 'RT04', 'RT05', 'RT06'}
        
        if value not in valid_types:
            return False, f"TipoRitenuta '{value}' non valido (valori ammessi: RT01-RT06)"
        
        return True, None
    
    def _validate_causale_pagamento(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida causale pagamento ritenuta (A-ZO)
        
        Args:
            value: Causale da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        # Causale pagamento: lettera A-Z o "ZO"
        if not re.match(r'^[A-Z]|ZO$', value):
            return False, f"CausalePagamento '{value}' non valida (formato: A-Z o ZO)"
        
        return True, None
    
    def _validate_tipo_cassa(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida tipo cassa previdenziale (TC01-TC22)
        
        Args:
            value: Tipo cassa da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        valid_types = {f'TC{i:02d}' for i in range(1, 23)}
        
        if value not in valid_types:
            return False, f"TipoCassa '{value}' non valido (valori ammessi: TC01-TC22)"
        
        return True, None
    
    def _validate_aliquota_iva(self, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Valida aliquota IVA (0.00-99.99 con 2 decimali)
        
        Args:
            value: Aliquota IVA da validare
            
        Returns:
            (is_valid, error_message)
        """
        if value is None:
            return False, "AliquotaIVA non può essere vuota"
        
        try:
            aliquota = float(value)
            if aliquota < 0 or aliquota > 99.99:
                return False, f"AliquotaIVA deve essere tra 0.00 e 99.99 (ricevuto: {aliquota})"
            
            # Verifica 2 decimali
            if round(aliquota, 2) != aliquota:
                return False, f"AliquotaIVA deve avere massimo 2 decimali (ricevuto: {aliquota})"
            
            return True, None
        except (ValueError, TypeError):
            return False, f"AliquotaIVA non valida: '{value}'"
    
    def _validate_natura_iva(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida natura operazione (N1-N7)
        
        Args:
            value: Natura da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        valid_nature = {'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7'}
        
        if value not in valid_nature:
            return False, f"Natura '{value}' non valida (valori ammessi: N1-N7)"
        
        return True, None
    
    def _validate_modalita_pagamento(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida modalità pagamento (MP01-MP23)
        
        Args:
            value: Modalità pagamento da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return False, "ModalitaPagamento non può essere vuota"
        
        valid_modes = {f'MP{i:02d}' for i in range(1, 24)}
        
        if value not in valid_modes:
            return False, f"ModalitaPagamento '{value}' non valida (valori ammessi: MP01-MP23)"
        
        return True, None
    
    def _validate_iban(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida formato IBAN internazionale
        
        Args:
            value: IBAN da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        iban_clean = value.replace(' ', '').upper()
        
        # IBAN: 2 lettere (paese) + 2 cifre (check) + fino a 30 caratteri alfanumerici
        if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$', iban_clean):
            return False, f"IBAN non valido: formato errato (ricevuto: '{value}')"
        
        if len(iban_clean) < 15 or len(iban_clean) > 34:
            return False, f"IBAN deve essere tra 15 e 34 caratteri (ricevuto: {len(iban_clean)})"
        
        return True, None
    
    def _validate_bic(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida formato BIC/SWIFT (8-11 caratteri alfanumerici)
        
        Args:
            value: BIC da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        bic_clean = value.upper().strip()
        
        if len(bic_clean) < 8 or len(bic_clean) > 11:
            return False, f"BIC deve essere tra 8 e 11 caratteri (ricevuto: {len(bic_clean)})"
        
        if not re.match(r'^[A-Z0-9]+$', bic_clean):
            return False, f"BIC non valido: solo caratteri alfanumerici (ricevuto: '{value}')"
        
        return True, None
    
    def _validate_base64(self, value: str) -> Tuple[bool, Optional[str]]:
        """
        Valida formato Base64
        
        Args:
            value: Stringa Base64 da validare
            
        Returns:
            (is_valid, error_message)
        """
        if not value:
            return True, None  # Opzionale
        
        try:
            # Prova a decodificare
            base64.b64decode(value, validate=True)
            return True, None
        except Exception:
            return False, "Attachment non valido: formato Base64 errato"
    
    # ==================== METODI HELPER PER VALIDAZIONE ====================
    
    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """
        Recupera valore di un campo usando path separato da /
        
        Args:
            data: Dict con i dati
            field_path: Path del campo (es. "CedentePrestatore/Sede/Indirizzo")
            
        Returns:
            Valore del campo o None se non trovato
        """
        parts = field_path.split('/')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            
            if current is None:
                return None
        
        return current
    
    def _parse_validation_rule(self, rule_str: str) -> Dict[str, Any]:
        """
        Parse una regola di validazione (es. "string|max:80|required")
        
        Args:
            rule_str: Stringa con le regole separate da |
            
        Returns:
            Dict con le regole parseate
        """
        rules = {}
        parts = rule_str.split('|')
        
        for part in parts:
            part = part.strip()
            if ':' in part:
                key, value = part.split(':', 1)
                rules[key.strip()] = value.strip()
            else:
                rules[part] = True
        
        return rules
    
    def _validate_field(
        self, 
        field_path: str, 
        value: Any, 
        rule_str: str, 
        context: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Valida un singolo campo secondo le regole specificate
        
        Args:
            field_path: Path del campo (es. "CedentePrestatore/Sede/Indirizzo")
            value: Valore da validare
            rule_str: Regole di validazione (es. "string|max:80|required")
            context: Contesto aggiuntivo per validazioni condizionali
            
        Returns:
            Lista di errori (vuota se validazione OK)
        """
        errors = []
        context = context or {}
        
        # CORREZIONE 1: Converti "" in None (campi opzionali vuoti)
        if value == "" or value == "undefined":
            value = None
        
        # Parse regole
        rules = self._parse_validation_rule(rule_str)
        
        # Controlla se campo è richiesto
        is_required = rules.get('required', False)
        required_without = rules.get('required_without')
        required_with = rules.get('required_with')
        
        # Se campo vuoto e non richiesto, skip validazione
        if value is None:
            if is_required:
                errors.append({
                    "field": field_path,
                    "message": f"Campo obbligatorio mancante",
                    "rule": "required",
                    "value": None
                })
                return errors
            
            # Controlla required_without
            if required_without:
                other_fields = [f.strip() for f in required_without.split(',')]
                all_empty = True
                other_values_found = []
                # HYPOTHESIS C FIX: Cerca i campi in xml_data se disponibile, altrimenti nel context
                xml_data_for_lookup = context.get('_xml_data') if context else None
                for other_field in other_fields:
                    # Costruisci path completo relativo al campo corrente
                    # Es: se field_path = "CessionarioCommittente/DatiAnagrafici/Anagrafica/Denominazione"
                    # e other_field = "Nome", il path completo è "CessionarioCommittente/DatiAnagrafici/Anagrafica/Nome"
                    # Es: se field_path = "CessionarioCommittente/DatiAnagrafici/CodiceFiscale"
                    # e other_field = "IdFiscaleIVA", il path completo è "CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice"
                    field_path_parts = field_path.split('/')
                    if len(field_path_parts) > 1:
                        # Se other_field è "IdFiscaleIVA", costruisci il path completo
                        if other_field == "IdFiscaleIVA":
                            other_field_path = '/'.join(field_path_parts[:-1]) + '/IdFiscaleIVA/IdCodice'
                        else:
                            # Sostituisci l'ultima parte con other_field
                            other_field_path = '/'.join(field_path_parts[:-1]) + '/' + other_field
                    else:
                        other_field_path = other_field
                    
                    # Cerca prima in xml_data, poi nel context
                    if xml_data_for_lookup:
                        other_value = self._get_field_value(xml_data_for_lookup, other_field_path)
                    else:
                        other_value = self._get_field_value(context, other_field)
                    
                    other_values_found.append({"field": other_field, "field_path": other_field_path, "value": str(other_value) if other_value is not None else None, "is_empty": not (other_value and (not isinstance(other_value, str) or other_value.strip()))})
                    if other_value and (not isinstance(other_value, str) or other_value.strip()):
                        all_empty = False
                        break
                if all_empty:
                    errors.append({
                        "field": field_path,
                        "message": f"Campo obbligatorio se {required_without} non presente",
                        "rule": "required_without",
                        "value": None
                    })
                    return errors
            
            # Controlla required_with
            if required_with:
                other_field = required_with.strip()
                other_value = self._get_field_value(context, other_field)
                if other_value and (not isinstance(other_value, str) or other_value.strip()):
                    errors.append({
                        "field": field_path,
                        "message": f"Campo obbligatorio se {required_with} presente",
                        "rule": "required_with",
                        "value": None
                    })
                    return errors
            
            # Se non richiesto e vuoto, skip altre validazioni
            if not is_required and not required_without and not required_with:
                return errors
        
        # Se value è None e non è required, non applicare altre validazioni
        if value is None:
            return errors
        
        # Converti value a stringa per validazioni
        value_str = str(value) if value is not None else ""
        
        # Applica regole di validazione
        for rule_name, rule_value in rules.items():
            if rule_name == 'required' or rule_name == 'required_without' or rule_name == 'required_with':
                continue  # Già gestito sopra
            
            # Regex
            if rule_name == 'regex':
                pattern = rule_value.replace('/', '').replace('^', '^').replace('$', '$')
                if not re.match(pattern, value_str):
                    errors.append({
                        "field": field_path,
                        "message": f"Valore non corrisponde al pattern richiesto",
                        "rule": "regex",
                        "value": value_str
                    })
            
            # Enum
            elif rule_name == 'enum':
                valid_values = [v.strip() for v in rule_value.split(',')]
                if value_str not in valid_values:
                    errors.append({
                        "field": field_path,
                        "message": f"Valore non valido (valori ammessi: {', '.join(valid_values)})",
                        "rule": "enum",
                        "value": value_str
                    })
            
            # String
            elif rule_name == 'string':
                if not isinstance(value, str):
                    errors.append({
                        "field": field_path,
                        "message": "Valore deve essere una stringa",
                        "rule": "string",
                        "value": value_str
                    })
                elif 'max' in rules:
                    max_len = int(rules['max'])
                    if len(value_str) > max_len:
                        errors.append({
                            "field": field_path,
                            "message": f"Stringa troppo lunga (massimo {max_len} caratteri, ricevuto {len(value_str)})",
                            "rule": "max",
                            "value": value_str
                        })
                elif 'size' in rules:
                    size = int(rules['size'])
                    if len(value_str) != size:
                        errors.append({
                            "field": field_path,
                            "message": f"Stringa deve essere esattamente {size} caratteri (ricevuto {len(value_str)})",
                            "rule": "size",
                            "value": value_str
                        })
            
            # Integer
            elif rule_name == 'integer':
                try:
                    int_value = int(value)
                    if 'min' in rules:
                        min_val = int(rules['min'])
                        if int_value < min_val:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve essere >= {min_val} (ricevuto: {int_value})",
                                "rule": "min",
                                "value": value_str
                            })
                    if 'max' in rules:
                        max_val = int(rules['max'])
                        if int_value > max_val:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve essere <= {max_val} (ricevuto: {int_value})",
                                "rule": "max",
                                "value": value_str
                            })
                    if 'between' in rules:
                        min_val, max_val = map(int, rules['between'].split(','))
                        if int_value < min_val or int_value > max_val:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve essere tra {min_val} e {max_val} (ricevuto: {int_value})",
                                "rule": "between",
                                "value": value_str
                            })
                except (ValueError, TypeError):
                    errors.append({
                        "field": field_path,
                        "message": "Valore deve essere un intero",
                        "rule": "integer",
                        "value": value_str
                    })
            
            # Decimal
            elif rule_name == 'decimal':
                try:
                    decimal_places = int(rule_value) if rule_value else 2
                    decimal_value = Decimal(str(value))
                    
                    # Verifica decimali
                    if decimal_places > 0:
                        scale = Decimal('10') ** -decimal_places
                        if decimal_value % scale != 0:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve avere massimo {decimal_places} decimali",
                                "rule": "decimal",
                                "value": value_str
                            })
                    
                    if 'min' in rules:
                        min_val = Decimal(rules['min'])
                        if decimal_value < min_val:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve essere >= {min_val} (ricevuto: {decimal_value})",
                                "rule": "min",
                                "value": value_str
                            })
                    if 'max' in rules:
                        max_val = Decimal(rules['max'])
                        if decimal_value > max_val:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve essere <= {max_val} (ricevuto: {decimal_value})",
                                "rule": "max",
                                "value": value_str
                            })
                    if 'between' in rules:
                        min_val, max_val = map(Decimal, rules['between'].split(','))
                        if decimal_value < min_val or decimal_value > max_val:
                            errors.append({
                                "field": field_path,
                                "message": f"Valore deve essere tra {min_val} e {max_val} (ricevuto: {decimal_value})",
                                "rule": "between",
                                "value": value_str
                            })
                except (ValueError, TypeError, Exception):
                    errors.append({
                        "field": field_path,
                        "message": "Valore deve essere un numero decimale",
                        "rule": "decimal",
                        "value": value_str
                    })
            
            # Date format
            elif rule_name == 'date_format':
                try:
                    datetime.strptime(value_str, rule_value.replace('Y', '%Y').replace('m', '%m').replace('d', '%d'))
                except (ValueError, TypeError):
                    errors.append({
                        "field": field_path,
                        "message": f"Data non valida: formato atteso {rule_value} (ricevuto: '{value_str}')",
                        "rule": "date_format",
                        "value": value_str
                    })
            
            # Alfanumerico
            elif rule_name == 'alfanumerico':
                if not value_str.replace(' ', '').isalnum():
                    errors.append({
                        "field": field_path,
                        "message": "Valore deve essere alfanumerico",
                        "rule": "alfanumerico",
                        "value": value_str
                    })
            
            # Email
            elif rule_name == 'email':
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, value_str):
                    errors.append({
                        "field": field_path,
                        "message": f"Email non valida: '{value_str}'",
                        "rule": "email",
                        "value": value_str
                    })
            
            # Controlli personalizzati
            elif rule_name == 'partita_iva':
                is_valid, error_msg = self._validate_partita_iva(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "P.IVA non valida",
                        "rule": "partita_iva",
                        "value": value_str
                    })
            
            elif rule_name == 'partita_iva_estera':
                country_code = context.get('country_iso', 'IT')
                is_valid, error_msg = self._validate_partita_iva_estera(value_str, country_code)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "P.IVA estera non valida",
                        "rule": "partita_iva_estera",
                        "value": value_str
                    })
            
            elif rule_name == 'codice_fiscale':
                is_valid, error_msg = self._validate_codice_fiscale(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Codice Fiscale non valido",
                        "rule": "codice_fiscale",
                        "value": value_str
                    })
            
            elif rule_name == 'cap_italiano':
                is_valid, error_msg = self._validate_cap_italiano(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "CAP italiano non valido",
                        "rule": "cap_italiano",
                        "value": value_str
                    })
            
            elif rule_name == 'cap_internazionale':
                country_code = context.get('country_iso', 'IT')
                is_valid, error_msg = self._validate_cap_internazionale(value_str, country_code)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "CAP non valido",
                        "rule": "cap_internazionale",
                        "value": value_str
                    })
            
            elif rule_name == 'provincia_italiana':
                is_valid, error_msg = self._validate_provincia_italiana(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Provincia italiana non valida",
                        "rule": "provincia_italiana",
                        "value": value_str
                    })
            
            elif rule_name == 'provincia_internazionale':
                country_code = context.get('country_iso', 'IT')
                is_valid, error_msg = self._validate_provincia_internazionale(value_str, country_code)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Provincia non valida",
                        "rule": "provincia_internazionale",
                        "value": value_str
                    })
            
            elif rule_name == 'codice_destinatario':
                formato_trasmissione = context.get('FormatoTrasmissione', 'FPR12')
                is_valid, error_msg = self._validate_codice_destinatario(value_str, formato_trasmissione)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "CodiceDestinatario non valido",
                        "rule": "codice_destinatario",
                        "value": value_str
                    })
            
            elif rule_name == 'email_pec':
                is_valid, error_msg = self._validate_email_pec(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Email PEC non valida",
                        "rule": "email_pec",
                        "value": value_str
                    })
            
            elif rule_name == 'regime_fiscale':
                is_valid, error_msg = self._validate_regime_fiscale(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "RegimeFiscale non valido",
                        "rule": "regime_fiscale",
                        "value": value_str
                    })
            
            elif rule_name == 'tipo_documento':
                is_valid, error_msg = self._validate_tipo_documento(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "TipoDocumento non valido",
                        "rule": "tipo_documento",
                        "value": value_str
                    })
            
            elif rule_name == 'data_fattura':
                is_valid, error_msg = self._validate_data_fattura(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Data fattura non valida",
                        "rule": "data_fattura",
                        "value": value_str
                    })
            
            elif rule_name == 'numero_documento':
                is_valid, error_msg = self._validate_numero_documento(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Numero documento non valido",
                        "rule": "numero_documento",
                        "value": value_str
                    })
            
            elif rule_name == 'tipo_ritenuta':
                is_valid, error_msg = self._validate_tipo_ritenuta(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "TipoRitenuta non valido",
                        "rule": "tipo_ritenuta",
                        "value": value_str
                    })
            
            elif rule_name == 'causale_pagamento':
                is_valid, error_msg = self._validate_causale_pagamento(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "CausalePagamento non valida",
                        "rule": "causale_pagamento",
                        "value": value_str
                    })
            
            elif rule_name == 'tipo_cassa':
                is_valid, error_msg = self._validate_tipo_cassa(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "TipoCassa non valido",
                        "rule": "tipo_cassa",
                        "value": value_str
                    })
            
            elif rule_name == 'aliquota_iva':
                is_valid, error_msg = self._validate_aliquota_iva(value)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "AliquotaIVA non valida",
                        "rule": "aliquota_iva",
                        "value": value_str
                    })
            
            elif rule_name == 'natura_iva' or rule_name == 'natura_iva_linea' or rule_name == 'natura_iva_riepilogo':
                is_valid, error_msg = self._validate_natura_iva(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Natura non valida",
                        "rule": rule_name,
                        "value": value_str
                    })
            
            elif rule_name == 'modalita_pagamento':
                is_valid, error_msg = self._validate_modalita_pagamento(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "ModalitaPagamento non valida",
                        "rule": "modalita_pagamento",
                        "value": value_str
                    })
            
            elif rule_name == 'iban':
                is_valid, error_msg = self._validate_iban(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "IBAN non valido",
                        "rule": "iban",
                        "value": value_str
                    })
            
            elif rule_name == 'bic':
                is_valid, error_msg = self._validate_bic(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "BIC non valido",
                        "rule": "bic",
                        "value": value_str
                    })
            
            elif rule_name == 'base64':
                is_valid, error_msg = self._validate_base64(value_str)
                if not is_valid:
                    errors.append({
                        "field": field_path,
                        "message": error_msg or "Attachment Base64 non valido",
                        "rule": "base64",
                        "value": value_str[:50] + "..." if len(value_str) > 50 else value_str
                    })
        
        return errors
    
    # ==================== CONTROLLI DI COERENZA ====================
    
    def _check_formato_codice_destinatario(
        self, 
        formato_trasmissione: str, 
        codice_destinatario: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla coerenza tra FormatoTrasmissione e CodiceDestinatario"""
        if not formato_trasmissione or not codice_destinatario:
            return
        
        if formato_trasmissione == 'FPA12':
            if len(codice_destinatario) != 6 and codice_destinatario != "XXXXXXX":
                errors.append({
                    "field": "CodiceDestinatario",
                    "message": f"Per FormatoTrasmissione FPA12, CodiceDestinatario deve essere esattamente 6 caratteri (ricevuto: {len(codice_destinatario)})",
                    "rule": "formato_codice_destinatario",
                    "value": codice_destinatario
                })
        elif formato_trasmissione == 'FPR12':
            if len(codice_destinatario) != 7 and codice_destinatario != "XXXXXXX":
                errors.append({
                    "field": "CodiceDestinatario",
                    "message": f"Per FormatoTrasmissione FPR12, CodiceDestinatario deve essere esattamente 7 caratteri o XXXXXXX (ricevuto: {len(codice_destinatario)})",
                    "rule": "formato_codice_destinatario",
                    "value": codice_destinatario
                })
    
    def _check_pec_obbligatoria(
        self, 
        codice_destinatario: str, 
        pec_destinatario: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che PEC sia obbligatoria se CodiceDestinatario = XXXXXXX"""
        if codice_destinatario == "XXXXXXX" and not pec_destinatario:
            errors.append({
                "field": "PECDestinatario",
                "message": "PECDestinatario è obbligatorio quando CodiceDestinatario = XXXXXXX",
                "rule": "pec_obbligatoria",
                "value": None
            })
    
    def _check_fiscale_coerenza(
        self, 
        id_fiscale_iva: Optional[str], 
        codice_fiscale: Optional[str],
        field_prefix: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che IdFiscaleIVA o CodiceFiscale sia presente"""
        if not id_fiscale_iva and not codice_fiscale:
            errors.append({
                "field": f"{field_prefix}/DatiAnagrafici",
                "message": "IdFiscaleIVA o CodiceFiscale deve essere presente",
                "rule": "fiscale_coerenza",
                "value": None
            })
    
    def _check_provincia_italia(
        self, 
        nazione: str, 
        provincia: Optional[str],
        field_prefix: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che Provincia sia obbligatoria se Nazione = IT"""
        if nazione == 'IT' and not provincia:
            errors.append({
                "field": f"{field_prefix}/Sede/Provincia",
                "message": "Provincia è obbligatoria quando Nazione = IT",
                "rule": "provincia_italia",
                "value": None
            })
        elif nazione == 'IT' and provincia and len(provincia) != 2:
            errors.append({
                "field": f"{field_prefix}/Sede/Provincia",
                "message": "Provincia deve essere esattamente 2 caratteri quando Nazione = IT",
                "rule": "provincia_italia",
                "value": provincia
            })
    
    def _check_cap_italia(
        self, 
        nazione: str, 
        cap: Optional[str],
        field_prefix: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che CAP sia 5 cifre se Nazione = IT"""
        if nazione == 'IT' and cap:
            cap_clean = ''.join(filter(str.isdigit, cap))
            if len(cap_clean) != 5:
                errors.append({
                    "field": f"{field_prefix}/Sede/CAP",
                    "message": "CAP deve essere esattamente 5 cifre quando Nazione = IT",
                    "rule": "cap_italia",
                    "value": cap
                })
    
    def _check_natura_zero_iva(
        self, 
        aliquota_iva: Any, 
        natura: Optional[str],
        field_prefix: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che Natura sia obbligatoria se AliquotaIVA = 0.00"""
        try:
            aliquota = float(aliquota_iva) if aliquota_iva is not None else None
            if aliquota == 0.0 and not natura:
                errors.append({
                    "field": f"{field_prefix}/Natura",
                    "message": "Natura è obbligatoria quando AliquotaIVA = 0.00",
                    "rule": "natura_zero_iva",
                    "value": None
                })
        except (ValueError, TypeError):
            pass
    
    def _check_ritenuta_coerenza(
        self, 
        ritenuta: Optional[str], 
        dati_ritenuta: Optional[Dict[str, Any]],
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che DatiRitenuta sia presente se Ritenuta = SI"""
        if ritenuta == 'SI' and not dati_ritenuta:
            errors.append({
                "field": "DatiGeneraliDocumento/DatiRitenuta",
                "message": "DatiRitenuta è obbligatorio quando Ritenuta = SI",
                "rule": "ritenuta_coerenza",
                "value": None
            })
    
    def _check_totali_coerenza(
        self, 
        line_items: List[Dict[str, Any]], 
        riepiloghi: List[Dict[str, Any]],
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla coerenza tra totali linee e riepiloghi IVA"""
        # Calcola totali dalle linee
        totale_imponibile_linee = Decimal('0')
        totale_imposta_linee = Decimal('0')
        
        for line in line_items:
            prezzo_totale = Decimal(str(line.get('PrezzoTotale', 0)))
            aliquota_iva = Decimal(str(line.get('AliquotaIVA', 0)))
            
            totale_imponibile_linee += prezzo_totale
            imposta_linea = prezzo_totale * (aliquota_iva / 100)
            totale_imposta_linee += imposta_linea
        
        # Calcola totali dai riepiloghi
        totale_imponibile_riepilogo = Decimal('0')
        totale_imposta_riepilogo = Decimal('0')
        
        for riepilogo in riepiloghi:
            imponibile = Decimal(str(riepilogo.get('ImponibileImporto', 0)))
            imposta = Decimal(str(riepilogo.get('Imposta', 0)))
            
            totale_imponibile_riepilogo += imponibile
            totale_imposta_riepilogo += imposta
        
        # Tolleranza per arrotondamenti (0.01)
        tolleranza = Decimal('0.01')
        
        if abs(totale_imponibile_linee - totale_imponibile_riepilogo) > tolleranza:
            errors.append({
                "field": "DatiRiepilogo/ImponibileImporto",
                "message": f"Totale imponibile linee ({totale_imponibile_linee:.2f}) non corrisponde a totale riepilogo ({totale_imponibile_riepilogo:.2f})",
                "rule": "totali_coerenza",
                "value": str(totale_imponibile_riepilogo)
            })
        
        if abs(totale_imposta_linee - totale_imposta_riepilogo) > tolleranza:
            errors.append({
                "field": "DatiRiepilogo/Imposta",
                "message": f"Totale imposta linee ({totale_imposta_linee:.2f}) non corrisponde a totale riepilogo ({totale_imposta_riepilogo:.2f})",
                "rule": "totali_coerenza",
                "value": str(totale_imposta_riepilogo)
            })
    
    def _check_data_non_futura(
        self, 
        data_documento: str,
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che data documento non sia futura"""
        try:
            data = datetime.strptime(data_documento, '%Y-%m-%d').date()
            oggi = date.today()
            
            if data > oggi:
                errors.append({
                    "field": "DatiGeneraliDocumento/Data",
                    "message": f"Data documento non può essere futura (data: {data_documento}, oggi: {oggi})",
                    "rule": "data_non_futura",
                    "value": data_documento
                })
        except (ValueError, TypeError):
            pass  # Errore già gestito in validazione campo
    
    def _check_scadenza_coerenza(
        self, 
        data_documento: str, 
        data_scadenza: Optional[str],
        errors: List[Dict[str, Any]]
    ) -> None:
        """Controlla che DataScadenzaPagamento >= Data documento"""
        if not data_scadenza:
            return
        
        try:
            data_doc = datetime.strptime(data_documento, '%Y-%m-%d').date()
            data_scad = datetime.strptime(data_scadenza, '%Y-%m-%d').date()
            
            if data_scad < data_doc:
                errors.append({
                    "field": "DatiPagamento/DettaglioPagamento/DataScadenzaPagamento",
                    "message": f"DataScadenzaPagamento ({data_scadenza}) deve essere >= Data documento ({data_documento})",
                    "rule": "scadenza_coerenza",
                    "value": data_scadenza
                })
        except (ValueError, TypeError):
            pass  # Errore già gestito in validazione campo
    
    # ==================== METODI HELPER PER CONVERSIONE DATI ====================
    
    def _convert_line_items_to_xml_format(self, line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Converte line_items dal formato servizio al formato XML
        
        Args:
            line_items: Lista di dict con chiavi tipo 'product_name', 'product_qty', etc.
            
        Returns:
            Lista di dict con chiavi tipo 'Descrizione', 'Quantita', etc.
        """
        xml_line_items = []
        
        for idx, item in enumerate(line_items, start=1):
            xml_item = {
                'NumeroLinea': idx,
                'Descrizione': item.get('product_name', ''),
                'Quantita': item.get('product_qty', 0),
                'UnitaMisura': item.get('product_unit', ''),
                'PrezzoUnitario': item.get('product_price', 0),
                'PrezzoTotale': item.get('total_price_with_tax', 0),
                'AliquotaIVA': item.get('tax_percentage', 0),
                'Natura': item.get('tax_nature', None),
                'Ritenuta': item.get('withholding', None)
            }
            
            # Codice articolo (se presente)
            if item.get('product_reference'):
                xml_item['CodiceArticolo'] = {
                    'CodiceTipo': 'ART',
                    'CodiceValore': item.get('product_reference', '')
                }
            
            xml_line_items.append(xml_item)
        
        return xml_line_items
    
    # ==================== METODO PRINCIPALE DI VALIDAZIONE ====================
    
    def _build_xml_data_structure(
        self, 
        order_data: Dict[str, Any], 
        line_items: List[Dict[str, Any]], 
        company_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Costruisce struttura dati XML da order_data, line_items e company_data
        
        Args:
            order_data: Dati ordine/documento
            line_items: Lista dettagli articoli
            company_data: Dati azienda
            
        Returns:
            Dict con struttura dati XML per validazione
        """
        # Estrai dati cliente
        customer_name = (order_data.get('invoice_firstname', '') + ' ' + order_data.get('invoice_lastname', '')).strip()
        customer_company = order_data.get('invoice_company', '') or None  # Converti stringa vuota in None
        customer_cf = order_data.get('customer_fiscal_code', '')
        customer_vat_raw = order_data.get('invoice_vat', '')
        customer_vat = ''.join(filter(str.isdigit, customer_vat_raw)) if customer_vat_raw else ''
        customer_pec = order_data.get('invoice_pec', '')
        customer_sdi = order_data.get('invoice_sdi', '')
        
        # Costruisci struttura XML
        xml_data = {
            # Dati Trasmissione
            'IdTrasmittente': {
                'IdPaese': 'IT',
                'IdCodice': company_data.get('vat_number', '')
            },
            'ProgressivoInvio': order_data.get('document_number', ''),
            'FormatoTrasmissione': 'FPR12',  # Default, potrebbe essere FPA12
            'CodiceDestinatario': customer_sdi or '0000000',
            'PECDestinatario': customer_pec,
            'ContattiTrasmittente': {
                'Telefono': company_data.get('phone', ''),
                'Email': company_data.get('email', '')
            },
            
            # Cedente Prestatore
            'CedentePrestatore': {
                'DatiAnagrafici': {
                    'IdFiscaleIVA': {
                        'IdPaese': 'IT',
                        'IdCodice': company_data.get('vat_number', '')
                    },
                    'CodiceFiscale': company_data.get('fiscal_code', ''),
                    'Anagrafica': {
                        'Denominazione': company_data.get('company_name', ''),
                        'Nome': None,
                        'Cognome': None
                    },
                    'RegimeFiscale': company_data.get('tax_regime', 'RF01')
                },
                'Sede': {
                    'Indirizzo': company_data.get('address', ''),
                    'NumeroCivico': company_data.get('civic_number', ''),
                    'CAP': company_data.get('postal_code', ''),
                    'Comune': company_data.get('city', ''),
                    'Provincia': company_data.get('province', ''),
                    'Nazione': 'IT'
                },
                'Contatti': {
                    'Telefono': company_data.get('phone', ''),
                    'Email': company_data.get('email', ''),
                    'Fax': company_data.get('fax', '')
                },
                'RiferimentoAmministrazione': company_data.get('account_holder', '')
            },
            
            # Cessionario Committente
            'CessionarioCommittente': {
                'DatiAnagrafici': {
                    'IdFiscaleIVA': {
                        'IdPaese': order_data.get('country_iso', 'IT'),
                        'IdCodice': customer_vat
                    } if customer_vat else None,
                    'CodiceFiscale': customer_cf,
                    'Anagrafica': {
                        'Denominazione': customer_company,
                        'Nome': customer_name.split(' ', 1)[0] if customer_name and not customer_company else None,
                        'Cognome': customer_name.split(' ', 1)[1] if customer_name and len(customer_name.split(' ', 1)) > 1 and not customer_company else None
                    }
                },
                'Sede': {
                    'Indirizzo': order_data.get('invoice_address1', ''),
                    'NumeroCivico': order_data.get('invoice_address2', ''),
                    'CAP': order_data.get('invoice_postcode', ''),
                    'Comune': order_data.get('invoice_city', ''),
                    'Provincia': order_data.get('invoice_state', ''),
                    'Nazione': order_data.get('country_iso', 'IT')
                }
            },
            
            # Dati Generali Documento
            'DatiGeneraliDocumento': {
                'TipoDocumento': order_data.get('tipo_documento_fe', 'TD01'),
                'Divisa': 'EUR',
                'Data': date.today().strftime('%Y-%m-%d'),
                'Numero': order_data.get('document_number', '')
            },
            
            # Dettaglio Linee (converti formato)
            'DettaglioLinee': self._convert_line_items_to_xml_format(line_items),
            
            # Dati Riepilogo (da calcolare)
            'DatiRiepilogo': []
        }
        
        return xml_data
    
    def validate(
        self, 
        order_data: Dict[str, Any], 
        line_items: List[Dict[str, Any]], 
        company_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Valida tutti i campi dell'XML FatturaPA prima della generazione
        
        Args:
            order_data: Dati dell'ordine/documento
            line_items: Lista di dettagli articoli
            company_data: Dati azienda (cedente)
            
        Returns:
            Dict con:
            - valid: bool - True se validazione OK
            - errors: List[Dict] - Lista errori se validazione fallisce
        """
        errors: List[Dict[str, Any]] = []
        
        # Costruisci struttura dati XML
        xml_data = self._build_xml_data_structure(order_data, line_items, company_data)
        
        # Contesto per validazioni condizionali
        context = {
            'country_iso': order_data.get('country_iso', 'IT'),
            'FormatoTrasmissione': xml_data.get('FormatoTrasmissione', 'FPR12'),
            '_xml_data': xml_data  # HYPOTHESIS C FIX: Aggiungi xml_data al context per required_without
        }
        
        # Valida campi singoli secondo VALIDATION_RULES
        for field_path, rule_str in self.VALIDATION_RULES.items():
            # CORREZIONE 2: Skip validazione se il nodo padre non esiste
            # Blocchi opzionali che devono essere presenti per validare i figli
            optional_blocks = {
                'TerzoIntermediarioOSoggettoEmittente': 'TerzoIntermediarioOSoggettoEmittente',
                'Allegati': 'Allegati',
                'DatiRitenuta': 'DatiGeneraliDocumento/DatiRitenuta',
                'DatiBollo': 'DatiGeneraliDocumento/DatiBollo',
                'DatiCassaPrevidenziale': 'DatiGeneraliDocumento/DatiCassaPrevidenziale',
                'ScontoMaggiorazione': 'DatiGeneraliDocumento/ScontoMaggiorazione',
                'DatiRiepilogo': 'DatiRiepilogo',  # HYPOTHESIS A: Aggiunto
                'DatiPagamento': 'DatiPagamento',  # HYPOTHESIS A: Aggiunto
            }
            
            
            # Controlla se il campo appartiene a un blocco opzionale
            path_parts = field_path.split('/')
            first_part = path_parts[0]
            
            if first_part in optional_blocks:
                # Blocco opzionale: controlla se il padre esiste
                parent_path = optional_blocks[first_part]
                parent_value = self._get_field_value(xml_data, parent_path)
                # HYPOTHESIS A: Per array (DatiRiepilogo), controlla se esiste e non è vuoto
                if first_part == 'DatiRiepilogo':
                    if not parent_value or (isinstance(parent_value, list) and len(parent_value) == 0):
                        parent_value = None
                # HYPOTHESIS A: Per DatiPagamento, controlla se DettaglioPagamento esiste
                elif first_part == 'DatiPagamento':
                    dettaglio_pagamento = self._get_field_value(xml_data, 'DatiPagamento/DettaglioPagamento')
                    if not dettaglio_pagamento or (isinstance(dettaglio_pagamento, list) and len(dettaglio_pagamento) == 0):
                        parent_value = None
                if parent_value is None:
                    # Il blocco padre non esiste, skip validazione di tutti i figli
                    continue
            
            # Controlla anche per sottoblocchi opzionali (es. DatiRitenuta dentro DatiGeneraliDocumento)
            if len(path_parts) > 1:
                second_part = path_parts[1]
                if second_part in optional_blocks:
                    parent_path = '/'.join(path_parts[:2])
                    parent_value = self._get_field_value(xml_data, parent_path)
                    if parent_value is None:
                        continue
            
            # Gestione speciale per DettaglioLinee (array)
            if field_path.startswith('DettaglioLinee/'):
                # Valida ogni elemento dell'array
                dettaglio_linee = xml_data.get('DettaglioLinee', [])
                if isinstance(dettaglio_linee, list):
                    for idx, line_item in enumerate(dettaglio_linee):
                        # Estrai il nome del campo (es. "Descrizione" da "DettaglioLinee/Descrizione")
                        field_name = field_path.replace('DettaglioLinee/', '')
                        value = line_item.get(field_name)
                        
                        # CORREZIONE 1: Converti "" in None
                        if value == "":
                            value = None
                        
                        # Costruisci field_path completo con indice
                        indexed_field_path = f"DettaglioLinee[{idx}]/{field_name}"
                        
                        # Skip validazione se campo non presente e non richiesto
                        if value is None and 'required' not in rule_str and 'required_without' not in rule_str and 'required_with' not in rule_str:
                            continue
                        
                        # Crea contesto con dati della linea corrente
                        line_context = {**context, **line_item}
                        field_errors = self._validate_field(indexed_field_path, value, rule_str, line_context)
                        errors.extend(field_errors)
                continue
            
            # Validazione normale per campi non-array
            value = self._get_field_value(xml_data, field_path)
            
            # CORREZIONE 1: Converti "" in None
            if value == "":
                value = None
            
            # Skip validazione se campo non presente e non richiesto
            if value is None and 'required' not in rule_str and 'required_without' not in rule_str and 'required_with' not in rule_str:
                continue
            
            field_errors = self._validate_field(field_path, value, rule_str, context)
            errors.extend(field_errors)
        
        # Esegui controlli di coerenza
        formato_trasmissione = xml_data.get('FormatoTrasmissione', 'FPR12')
        codice_destinatario = xml_data.get('CodiceDestinatario', '')
        pec_destinatario = xml_data.get('PECDestinatario', '')
        
        self._check_formato_codice_destinatario(formato_trasmissione, codice_destinatario, errors)
        self._check_pec_obbligatoria(codice_destinatario, pec_destinatario, errors)
        
        # Controlli fiscali
        cedente_id_fiscale = self._get_field_value(xml_data, 'CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdCodice')
        cedente_cf = self._get_field_value(xml_data, 'CedentePrestatore/DatiAnagrafici/CodiceFiscale')
        self._check_fiscale_coerenza(cedente_id_fiscale, cedente_cf, 'CedentePrestatore', errors)
        
        cessionario_id_fiscale = self._get_field_value(xml_data, 'CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice')
        cessionario_cf = self._get_field_value(xml_data, 'CessionarioCommittente/DatiAnagrafici/CodiceFiscale')
        # HYPOTHESIS D FIX: Controlla se esiste già un errore required_without per CodiceFiscale prima di aggiungere fiscale_coerenza
        has_required_without_error = any(
            e.get('field', '').endswith('/CodiceFiscale') and e.get('rule') == 'required_without'
            for e in errors
        )
        if not has_required_without_error:
            self._check_fiscale_coerenza(cessionario_id_fiscale, cessionario_cf, 'CessionarioCommittente', errors)
        
        # Controlli provincia e CAP
        cedente_nazione = self._get_field_value(xml_data, 'CedentePrestatore/Sede/Nazione')
        cedente_provincia = self._get_field_value(xml_data, 'CedentePrestatore/Sede/Provincia')
        cedente_cap = self._get_field_value(xml_data, 'CedentePrestatore/Sede/CAP')
        self._check_provincia_italia(cedente_nazione or 'IT', cedente_provincia, 'CedentePrestatore', errors)
        self._check_cap_italia(cedente_nazione or 'IT', cedente_cap, 'CedentePrestatore', errors)
        
        cessionario_nazione = self._get_field_value(xml_data, 'CessionarioCommittente/Sede/Nazione')
        cessionario_provincia = self._get_field_value(xml_data, 'CessionarioCommittente/Sede/Provincia')
        cessionario_cap = self._get_field_value(xml_data, 'CessionarioCommittente/Sede/CAP')
        self._check_provincia_italia(cessionario_nazione or 'IT', cessionario_provincia, 'CessionarioCommittente', errors)
        self._check_cap_italia(cessionario_nazione or 'IT', cessionario_cap, 'CessionarioCommittente', errors)
        
        # Controlli natura IVA (da implementare quando abbiamo riepiloghi)
        # self._check_natura_zero_iva(...)
        
        # Controlli data
        data_documento = self._get_field_value(xml_data, 'DatiGeneraliDocumento/Data')
        if data_documento:
            self._check_data_non_futura(data_documento, errors)
        
        data_scadenza = self._get_field_value(xml_data, 'DatiPagamento/DettaglioPagamento/DataScadenzaPagamento')
        if data_documento and data_scadenza:
            self._check_scadenza_coerenza(data_documento, data_scadenza, errors)
        
        # CORREZIONE 3: Deduplica errori per (field + value + ruleCategory)
        # #region agent log
        with open(r'c:\Users\webmarke22\Documents\progetti\ECommerceManagerAPI\.cursor\debug.log', 'a', encoding='utf-8') as f:
            import json
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"fatturapa_validator.py:1745","message":"Before deduplication","data":{"error_count":len(errors),"errors":[{"field":e.get("field"),"rule":e.get("rule"),"value":str(e.get("value")) if e.get("value") is not None else None} for e in errors]},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        errors = self._deduplicate_errors(errors)
        # #region agent log
        with open(r'c:\Users\webmarke22\Documents\progetti\ECommerceManagerAPI\.cursor\debug.log', 'a', encoding='utf-8') as f:
            import json
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"fatturapa_validator.py:1746","message":"After deduplication","data":{"error_count":len(errors),"errors":[{"field":e.get("field"),"rule":e.get("rule"),"value":str(e.get("value")) if e.get("value") is not None else None} for e in errors]},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _deduplicate_errors(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rimuove errori duplicati basandosi su (field + value + ruleCategory)
        
        CORREZIONE 3: Deduplica errori per evitare segnalazioni multiple dello stesso problema
        
        Args:
            errors: Lista di errori
            
        Returns:
            Lista di errori deduplicati
        """
        seen = set()
        deduplicated = []
        
        # Categorie di regole che sono equivalenti (sub-check della stessa validazione)
        # Se due regole sono nella stessa categoria, mantieni solo una
        rule_categories = {
            'codice_destinatario': 'codice_destinatario',
            'formato_codice_destinatario': 'codice_destinatario',  # Sub-check di codice_destinatario
        }
        
        for error in errors:
            field = error.get('field', '')
            value = error.get('value')
            rule = error.get('rule', '')
            
            # Normalizza rule usando le categorie
            rule_category = rule_categories.get(rule, rule)
            
            # Crea chiave univoca: (field, value, ruleCategory)
            # Normalizza value: None -> "None", stringa -> valore normalizzato
            if value is None:
                value_key = "None"
            elif isinstance(value, str):
                value_key = value.strip()
            else:
                value_key = str(value)
            
            # HYPOTHESIS B FIX: Per P.IVA, deduplica se stesso valore e stessa regola (anche se campi diversi)
            # Questo gestisce il caso di IdTrasmittente/IdCodice e CedentePrestatore/.../IdCodice con stessa P.IVA
            if rule == 'partita_iva' and value_key != "None":
                # Usa solo (value, rule) come chiave per P.IVA, ignorando il campo
                key = (value_key, rule_category)
            else:
                key = (field, value_key, rule_category)
            
            if key not in seen:
                seen.add(key)
                # Se ci sono più regole nella stessa categoria, preferisci quella più specifica
                # (formato_codice_destinatario è più specifico di codice_destinatario)
                if rule_category in rule_categories.values():
                    # Cerca se esiste già un errore con la stessa chiave ma regola diversa
                    existing_idx = None
                    for idx, existing_error in enumerate(deduplicated):
                        existing_field = existing_error.get('field', '')
                        existing_value = existing_error.get('value')
                        existing_rule = existing_error.get('rule', '')
                        existing_rule_category = rule_categories.get(existing_rule, existing_rule)
                        
                        if existing_value is None:
                            existing_value_key = "None"
                        elif isinstance(existing_value, str):
                            existing_value_key = existing_value.strip()
                        else:
                            existing_value_key = str(existing_value)
                        
                        if (existing_field, existing_value_key, existing_rule_category) == key:
                            existing_idx = idx
                            break
                    
                    if existing_idx is not None:
                        # Sostituisci con quello più specifico (formato_codice_destinatario > codice_destinatario)
                        existing_rule = deduplicated[existing_idx].get('rule', '')
                        if rule == 'formato_codice_destinatario' and existing_rule == 'codice_destinatario':
                            deduplicated[existing_idx] = error
                        # Altrimenti mantieni quello esistente
                        continue
                
                deduplicated.append(error)
        
        return deduplicated
