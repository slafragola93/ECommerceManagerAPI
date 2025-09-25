"""
Test per FatturaPA Serializer
"""

import pytest
from decimal import Decimal
from datetime import date
from src.schemas.fatturapa_models import (
    FatturaElettronica, FatturaElettronicaHeader, FatturaElettronicaBody,
    DatiTrasmissione, IdFiscaleIVA, CedentePrestatore, CessionarioCommittente,
    DatiAnagrafici, Anagrafica, Sede, Contatti, DatiGenerali, DatiGeneraliDocumento,
    DatiBeniServizi, DettaglioLinee, DatiRiepilogo, DatiPagamento, DettaglioPagamento,
    OrderToFatturaPAMapper
)
from src.models.fatturapa_enums import (
    RegimeFiscale, TipoDocumento, ModalitaPagamento, FormatoTrasmissione
)
from src.services.fatturapa_serializer import FatturaPASerializer


class TestFatturaPASerializer:
    """Test per FatturaPASerializer"""
    
    def setup_method(self):
        """Setup per ogni test"""
        self.serializer = FatturaPASerializer()
    
    def create_minimal_fattura(self) -> FatturaElettronica:
        """Crea una fattura minima valida"""
        return FatturaElettronica(
            fattura_elettronica_header=FatturaElettronicaHeader(
                dati_trasmissione=DatiTrasmissione(
                    id_trasmittente=IdFiscaleIVA(
                        id_paese="IT",
                        id_codice="12345678901"
                    ),
                    progressivo_invio="00001",
                    formato_trasmissione=FormatoTrasmissione.FPR12,
                    codice_destinatario="1234567"
                ),
                cedente_prestatore=CedentePrestatore(
                    dati_anagrafici=DatiAnagrafici(
                        id_fiscale_iva=IdFiscaleIVA(id_paese="IT", id_codice="12345678901"),
                        anagrafica=Anagrafica(denominazione="Azienda Test SRL"),
                        regime_fiscale=RegimeFiscale.RF01
                    ),
                    sede=Sede(
                        indirizzo="Via Roma 123",
                        cap="00100",
                        comune="Roma",
                        provincia="RM",
                        nazione="IT"
                    ),
                    contatti=Contatti(
                        telefono="0612345678",
                        email="info@aziendatest.it"
                    )
                ),
                cessionario_committente=CessionarioCommittente(
                    dati_anagrafici=DatiAnagrafici(
                        id_fiscale_iva=IdFiscaleIVA(id_paese="IT", id_codice="98765432109"),
                        anagrafica=Anagrafica(denominazione="Cliente Test SRL"),
                        regime_fiscale=RegimeFiscale.RF01
                    ),
                    sede=Sede(
                        indirizzo="Via Milano 456",
                        cap="20100",
                        comune="Milano",
                        provincia="MI",
                        nazione="IT"
                    )
                )
            ),
            fattura_elettronica_body=FatturaElettronicaBody(
                dati_generali=DatiGenerali(
                    dati_generali_documento=DatiGeneraliDocumento(
                        tipo_documento=TipoDocumento.TD01,
                        divisa="EUR",
                        data=date(2024, 1, 15),
                        numero="FAT-001",
                        importo_totale_documento=Decimal("122.00")
                    )
                ),
                dati_beni_servizi=DatiBeniServizi(
                    dettaglio_linee=[
                        DettaglioLinee(
                            numero_linea=1,
                            descrizione="Prodotto Test",
                            quantita=Decimal("1.00"),
                            prezzo_unitario=Decimal("100.00"),
                            prezzo_totale=Decimal("100.00"),
                            aliquota_iva=Decimal("22.00")
                        )
                    ],
                    dati_riepilogo=[
                        DatiRiepilogo(
                            aliquota_iva=Decimal("22.00"),
                            imponibile_importo=Decimal("100.00"),
                            imposta=Decimal("22.00")
                        )
                    ]
                )
            )
        )
    
    def test_serialize_minimal_fattura(self):
        """Test serializzazione fattura minima"""
        fattura = self.create_minimal_fattura()
        xml = self.serializer.to_xml(fattura)
        
        assert xml is not None
        assert "<?xml version='1.0' encoding='UTF-8'?>" in xml
        assert "<FatturaElettronica" in xml
        assert "<FatturaElettronicaHeader>" in xml
        assert "<FatturaElettronicaBody>" in xml
        assert "<DatiTrasmissione>" in xml
        assert "<CedentePrestatore>" in xml
        assert "<CessionarioCommittente>" in xml
    
    def test_serialize_optional_fields_omitted(self):
        """Test che i campi opzionali non valorizzati non vengano emessi"""
        fattura = self.create_minimal_fattura()
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che i campi opzionali non presenti non vengano emessi
        assert "<PECDestinatario>" not in xml
        assert "<ContattiTrasmittente>" not in xml
        assert "<CodiceFiscale>" not in xml
        assert "<Provincia>" not in xml  # Provincia è opzionale per alcuni paesi
    
    def test_serialize_decimal_formatting(self):
        """Test formattazione decimali"""
        fattura = self.create_minimal_fattura()
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che i decimali siano formattati correttamente
        assert "100.00" in xml
        assert "22.00" in xml
        assert "122.00" in xml
    
    def test_serialize_date_formatting(self):
        """Test formattazione date"""
        fattura = self.create_minimal_fattura()
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che le date siano in formato YYYY-MM-DD
        assert "2024-01-15" in xml
    
    def test_serialize_enum_values(self):
        """Test che gli enum vengano serializzati correttamente"""
        fattura = self.create_minimal_fattura()
        xml = self.serializer.to_xml(fattura)
        
        # Verifica valori enum
        assert "FPR12" in xml
        assert "TD01" in xml
        assert "RF01" in xml
        assert "EUR" in xml
    
    def test_serialize_with_optional_fields(self):
        """Test serializzazione con campi opzionali valorizzati"""
        fattura = self.create_minimal_fattura()
        
        # Aggiungi campi opzionali
        fattura.fattura_elettronica_header.dati_trasmissione.pec_destinatario = "test@pec.it"
        fattura.fattura_elettronica_header.dati_trasmissione.contatti_trasmittente = {
            "telefono": "0612345678",
            "email": "contatti@aziendatest.it"
        }
        
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che i campi opzionali valorizzati vengano emessi
        assert "<PECDestinatario>test@pec.it</PECDestinatario>" in xml
        assert "<ContattiTrasmittente>" in xml
        assert "<Telefono>0612345678</Telefono>" in xml
        assert "<Email>contatti@aziendatest.it</Email>" in xml
    
    def test_serialize_persona_fisica(self):
        """Test serializzazione per persona fisica"""
        fattura = self.create_minimal_fattura()
        
        # Modifica per persona fisica
        fattura.fattura_elettronica_header.cessionario_committente.dati_anagrafici.anagrafica = Anagrafica(
            nome="Mario",
            cognome="Rossi"
        )
        
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che vengano emessi Nome e Cognome invece di Denominazione
        assert "<Nome>Mario</Nome>" in xml
        assert "<Cognome>Rossi</Cognome>" in xml
        assert "<Denominazione>" not in xml
    
    def test_serialize_persona_giuridica(self):
        """Test serializzazione per persona giuridica"""
        fattura = self.create_minimal_fattura()
        
        # Modifica per persona giuridica
        fattura.fattura_elettronica_header.cessionario_committente.dati_anagrafici.anagrafica = Anagrafica(
            denominazione="Azienda Cliente SRL"
        )
        
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che venga emessa Denominazione invece di Nome e Cognome
        assert "<Denominazione>Azienda Cliente SRL</Denominazione>" in xml
        assert "<Nome>" not in xml
        assert "<Cognome>" not in xml
    
    def test_serialize_with_payment(self):
        """Test serializzazione con dati pagamento"""
        fattura = self.create_minimal_fattura()
        
        # Aggiungi dati pagamento
        fattura.fattura_elettronica_body.dati_pagamento = [
            DatiPagamento(
                condizioni_pagamento="TP02",
                dettaglio_pagamento=[
                    DettaglioPagamento(
                        modalita_pagamento=ModalitaPagamento.MP05,
                        importo_pagamento=Decimal("122.00")
                    )
                ]
            )
        ]
        
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che i dati pagamento vengano emessi
        assert "<DatiPagamento>" in xml
        assert "<CondizioniPagamento>TP02</CondizioniPagamento>" in xml
        assert "<DettaglioPagamento>" in xml
        assert "<ModalitaPagamento>MP05</ModalitaPagamento>" in xml
        assert "<ImportoPagamento>122.00</ImportoPagamento>" in xml
    
    def test_serialize_empty_optional_fields(self):
        """Test che i campi opzionali vuoti non vengano emessi"""
        fattura = self.create_minimal_fattura()
        
        # Imposta campi opzionali vuoti
        fattura.fattura_elettronica_header.dati_trasmissione.pec_destinatario = ""
        fattura.fattura_elettronica_header.dati_trasmissione.contatti_trasmittente = {
            "telefono": "",
            "email": ""
        }
        
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che i campi vuoti non vengano emessi
        assert "<PECDestinatario>" not in xml
        assert "<ContattiTrasmittente>" not in xml
    
    def test_serialize_multiple_lines(self):
        """Test serializzazione con più linee"""
        fattura = self.create_minimal_fattura()
        
        # Aggiungi più linee
        fattura.fattura_elettronica_body.dati_beni_servizi.dettaglio_linee.append(
            DettaglioLinee(
                numero_linea=2,
                descrizione="Secondo Prodotto",
                quantita=Decimal("2.00"),
                prezzo_unitario=Decimal("50.00"),
                prezzo_totale=Decimal("100.00"),
                aliquota_iva=Decimal("22.00")
            )
        )
        
        xml = self.serializer.to_xml(fattura)
        
        # Verifica che entrambe le linee vengano emesse
        assert xml.count("<DettaglioLinee>") == 2
        assert "<NumeroLinea>1</NumeroLinea>" in xml
        assert "<NumeroLinea>2</NumeroLinea>" in xml
        assert "Prodotto Test" in xml
        assert "Secondo Prodotto" in xml
