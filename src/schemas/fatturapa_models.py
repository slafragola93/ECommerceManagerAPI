"""
Modelli Pydantic per FatturaPA con validazioni complete
"""

from decimal import Decimal
from typing import Optional, List, Union
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator
from src.models.fatturapa_enums import (
    RegimeFiscale, TipoCassa, ModalitaPagamento, TipoDocumento, 
    Natura, TipoRitenuta, FormatoTrasmissione, TipoCessionePrestazione,
    CondizioniPagamento, EsigibilitaIVA, TipoScontoMaggiorazione
)


class IdFiscaleIVA(BaseModel):
    """IdFiscaleIVA - 1.1"""
    id_paese: str = Field(..., min_length=2, max_length=2, description="ISO CODE PAESE")
    id_codice: str = Field(..., min_length=1, max_length=28, description="CODICE IDENTIFICATIVO FISCALE")

    @field_validator('id_paese')
    @classmethod
    def validate_id_paese(cls, v):
        if not v.isalpha() or not v.isupper():
            raise ValueError('IdPaese deve essere un codice ISO a 2 caratteri maiuscoli')
        return v

    @field_validator('id_codice')
    @classmethod
    def validate_id_codice(cls, v):
        if not v.replace(' ', '').replace('.', '').replace('-', '').isalnum():
            raise ValueError('IdCodice deve contenere solo caratteri alfanumerici, spazi, punti e trattini')
        return v


class ContattiTrasmittente(BaseModel):
    """ContattiTrasmittente - 0.1"""
    telefono: Optional[str] = Field(None, min_length=5, max_length=12)
    email: Optional[str] = Field(None, min_length=7, max_length=256)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Email non valida')
        return v


class DatiTrasmissione(BaseModel):
    """DatiTrasmissione - 1.1"""
    id_trasmittente: IdFiscaleIVA
    progressivo_invio: str = Field(..., min_length=1, max_length=10)
    formato_trasmissione: FormatoTrasmissione
    codice_destinatario: str = Field(..., min_length=6, max_length=7)
    contatti_trasmittente: Optional[ContattiTrasmittente] = None
    pec_destinatario: Optional[str] = Field(None, min_length=7, max_length=256)

    @field_validator('progressivo_invio')
    @classmethod
    def validate_progressivo_invio(cls, v):
        if not v.isalnum():
            raise ValueError('ProgressivoInvio deve contenere solo caratteri alfanumerici')
        return v

    @field_validator('codice_destinatario')
    @classmethod
    def validate_codice_destinatario(cls, v):
        if not v.isalnum() and v != 'XXXXXXX':
            raise ValueError('CodiceDestinatario deve essere alfanumerico o XXXXXXX')
        return v


class Anagrafica(BaseModel):
    """Anagrafica - 1.1"""
    denominazione: Optional[str] = Field(None, min_length=1, max_length=80)
    nome: Optional[str] = Field(None, min_length=1, max_length=60)
    cognome: Optional[str] = Field(None, min_length=1, max_length=60)

    @model_validator(mode='after')
    def validate_anagrafica(self):
        # Almeno uno tra denominazione o (nome e cognome) deve essere presente
        if not self.denominazione and not (self.nome and self.cognome):
            raise ValueError('Deve essere presente Denominazione oppure Nome e Cognome')
        
        # Non possono essere presenti sia denominazione che nome/cognome
        if self.denominazione and (self.nome or self.cognome):
            raise ValueError('Non possono essere presenti sia Denominazione che Nome/Cognome')
        
        return self


class DatiAnagrafici(BaseModel):
    """DatiAnagrafici - 1.1"""
    id_fiscale_iva: IdFiscaleIVA
    codice_fiscale: Optional[str] = Field(None, min_length=11, max_length=16)
    anagrafica: Anagrafica
    regime_fiscale: RegimeFiscale


class Sede(BaseModel):
    """Sede - 1.1"""
    indirizzo: str = Field(..., min_length=1, max_length=60)
    cap: str = Field(..., min_length=5, max_length=5)
    comune: str = Field(..., min_length=1, max_length=60)
    provincia: Optional[str] = Field(None, min_length=2, max_length=2)
    nazione: str = Field(..., min_length=2, max_length=2)

    @field_validator('cap')
    @classmethod
    def validate_cap(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError('CAP deve essere di 5 cifre')
        return v

    @field_validator('provincia')
    @classmethod
    def validate_provincia(cls, v):
        if v and not v.isalpha() or not v.isupper():
            raise ValueError('Provincia deve essere un codice a 2 caratteri maiuscoli')
        return v


class Contatti(BaseModel):
    """Contatti - 1.1"""
    telefono: str = Field(..., min_length=5, max_length=12)
    email: str = Field(..., min_length=7, max_length=256)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Email non valida')
        return v


class CedentePrestatore(BaseModel):
    """CedentePrestatore - 1.1"""
    dati_anagrafici: DatiAnagrafici
    sede: Sede
    contatti: Contatti


class CessionarioCommittente(BaseModel):
    """CessionarioCommittente - 1.1"""
    dati_anagrafici: DatiAnagrafici
    sede: Sede


class DatiRitenuta(BaseModel):
    """DatiRitenuta - 0.N"""
    tipo_ritenuta: TipoRitenuta
    importo_ritenuta: Decimal = Field(...)
    aliquota_ritenuta: Decimal = Field(...)
    causale_pagamento: str = Field(..., min_length=1, max_length=2)
    
    @field_validator('importo_ritenuta', 'aliquota_ritenuta')
    @classmethod
    def validate_decimal_precision(cls, v):
        """Valida precisione decimali (max 2 decimali)"""
        if v is not None:
            # Arrotonda a 2 decimali se necessario
            return v.quantize(Decimal('0.01'))
        return v


class ScontoMaggiorazione(BaseModel):
    """ScontoMaggiorazione - 0.N"""
    tipo: TipoScontoMaggiorazione
    percentuale: Optional[Decimal] = Field(None)
    importo: Optional[Decimal] = Field(None)
    
    @field_validator('percentuale', 'importo')
    @classmethod
    def validate_decimal_precision(cls, v):
        """Valida precisione decimali (max 2 decimali)"""
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v

    @model_validator(mode='after')
    def validate_sconto_maggiorazione(self):
        if not self.percentuale and not self.importo:
            raise ValueError('Deve essere presente Percentuale o Importo')
        return self


class DatiGeneraliDocumento(BaseModel):
    """DatiGeneraliDocumento - 1.1"""
    tipo_documento: TipoDocumento
    divisa: str = Field(..., min_length=3, max_length=3)
    data: date
    numero: str = Field(..., min_length=1, max_length=20)
    dati_ritenuta: Optional[List[DatiRitenuta]] = None
    sconto_maggiorazione: Optional[List[ScontoMaggiorazione]] = None
    importo_totale_documento: Optional[Decimal] = Field(None)
    causale: Optional[List[str]] = Field(None, min_length=1, max_length=20)
    
    @field_validator('importo_totale_documento')
    @classmethod
    def validate_decimal_precision(cls, v):
        """Valida precisione decimali (max 2 decimali)"""
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v

    @field_validator('divisa')
    @classmethod
    def validate_divisa(cls, v):
        if not v.isalpha() or not v.isupper():
            raise ValueError('Divisa deve essere un codice ISO 4217 a 3 caratteri maiuscoli')
        return v

    @field_validator('numero')
    @classmethod
    def validate_numero(cls, v):
        if not v.replace('/', '').replace('-', '').replace('.', '').isalnum():
            raise ValueError('Numero deve contenere solo caratteri alfanumerici, /, - e .')
        return v


class DatiGenerali(BaseModel):
    """DatiGenerali - 1.1"""
    dati_generali_documento: DatiGeneraliDocumento


class CodiceArticolo(BaseModel):
    """CodiceArticolo - 0.N"""
    codice_tipo: str = Field(..., min_length=1, max_length=35)
    codice_valore: str = Field(..., min_length=1, max_length=35)


class DettaglioLinee(BaseModel):
    """DettaglioLinee - 1.N"""
    numero_linea: int = Field(..., ge=1, le=9999)
    tipo_cessione_prestazione: Optional[TipoCessionePrestazione] = None
    codice_articolo: Optional[List[CodiceArticolo]] = None
    descrizione: str = Field(..., min_length=1, max_length=1000)
    quantita: Optional[Decimal] = Field(None)
    prezzo_unitario: Decimal = Field(...)
    prezzo_totale: Decimal = Field(...)
    aliquota_iva: Decimal = Field(...)
    natura: Optional[Natura] = None
    ritenuta: Optional[str] = Field(None, pattern='^(SI|NO)$')
    
    @field_validator('quantita', 'prezzo_unitario', 'prezzo_totale', 'aliquota_iva')
    @classmethod
    def validate_decimal_precision(cls, v):
        """Valida precisione decimali (max 2 decimali)"""
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v

    @model_validator(mode='after')
    def validate_dettaglio_linee(self):
        # Calcolo prezzo totale se non fornito
        if self.quantita and not self.prezzo_totale:
            self.prezzo_totale = self.prezzo_unitario * self.quantita
        
        # Validazione coerenza prezzo
        if self.quantita and self.prezzo_totale:
            expected_total = self.prezzo_unitario * self.quantita
            if abs(self.prezzo_totale - expected_total) > Decimal('0.01'):
                raise ValueError('PrezzoTotale non calcolato correttamente')
        
        return self


class DatiRiepilogo(BaseModel):
    """DatiRiepilogo - 1.1"""
    aliquota_iva: Decimal = Field(...)
    imponibile_importo: Decimal = Field(...)
    imposta: Decimal = Field(...)
    esigibilita_iva: Optional[EsigibilitaIVA] = None
    
    @field_validator('aliquota_iva', 'imponibile_importo', 'imposta')
    @classmethod
    def validate_decimal_precision(cls, v):
        """Valida precisione decimali (max 2 decimali)"""
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v


class DatiBeniServizi(BaseModel):
    """DatiBeniServizi - 1.1"""
    dettaglio_linee: List[DettaglioLinee] = Field(..., min_length=1)
    dati_riepilogo: List[DatiRiepilogo] = Field(..., min_length=1)


class DettaglioPagamento(BaseModel):
    """DettaglioPagamento - 1.N"""
    modalita_pagamento: ModalitaPagamento
    importo_pagamento: Decimal = Field(...)
    data_scadenza: Optional[date] = None
    
    @field_validator('importo_pagamento')
    @classmethod
    def validate_decimal_precision(cls, v):
        """Valida precisione decimali (max 2 decimali)"""
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v


class DatiPagamento(BaseModel):
    """DatiPagamento - 0.N"""
    condizioni_pagamento: CondizioniPagamento
    dettaglio_pagamento: List[DettaglioPagamento] = Field(..., min_length=1)


class FatturaElettronicaHeader(BaseModel):
    """FatturaElettronicaHeader - 1.1"""
    dati_trasmissione: DatiTrasmissione
    cedente_prestatore: CedentePrestatore
    cessionario_committente: CessionarioCommittente


class FatturaElettronicaBody(BaseModel):
    """FatturaElettronicaBody - 1.1"""
    dati_generali: DatiGenerali
    dati_beni_servizi: DatiBeniServizi
    dati_pagamento: Optional[List[DatiPagamento]] = None


class FatturaElettronica(BaseModel):
    """FatturaElettronica - Root element"""
    fattura_elettronica_header: FatturaElettronicaHeader
    fattura_elettronica_body: FatturaElettronicaBody

    @model_validator(mode='after')
    def validate_fattura_elettronica(self):
        # Validazioni incrociate
        header = self.fattura_elettronica_header
        body = self.fattura_elettronica_body
        
        # Validazione regime fiscale
        if header.cedente_prestatore.dati_anagrafici.regime_fiscale != header.cessionario_committente.dati_anagrafici.regime_fiscale:
            # Logica per validazione regime fiscale diverso
            pass
        
        # Validazione tipo documento vs aliquote
        tipo_doc = body.dati_generali.dati_generali_documento.tipo_documento
        if tipo_doc in [TipoDocumento.TD01, TipoDocumento.TD02, TipoDocumento.TD03]:
            for linea in body.dati_beni_servizi.dettaglio_linee:
                if linea.aliquota_iva == 0:
                    raise ValueError(f'TipoDocumento {tipo_doc} non ammette AliquotaIVA zero')
        
        return self


# Modelli per mapping da Order
class OrderToFatturaPAMapper(BaseModel):
    """Mapper per convertire Order in FatturaPA"""
    order_id: int
    formato_trasmissione: FormatoTrasmissione = FormatoTrasmissione.FPR12
    progressivo_invio: str
    codice_destinatario: str
    pec_destinatario: Optional[str] = None
    
    class Config:
        from_attributes = True
