"""
Enums per FatturaPA - Domini validi secondo specifiche tecniche
"""

from enum import Enum


class RegimeFiscale(str, Enum):
    """Regime Fiscale - RFxx"""
    RF01 = "RF01"  # Ordinario
    RF02 = "RF02"  # Contribuenti minimi
    RF04 = "RF04"  # Agricoltura e attività connesse e pesca
    RF05 = "RF05"  # Vendita sali e tabacchi
    RF06 = "RF06"  # Commercio fiammiferi
    RF07 = "RF07"  # Agenzie di viaggi e turismo
    RF08 = "RF08"  # Agriturismo
    RF09 = "RF09"  # Vendita a distanza di commercio elettronico
    RF10 = "RF10"  # Rivendita di sali e tabacchi
    RF11 = "RF11"  # Commercio ambulante di sali e tabacchi
    RF12 = "RF12"  # Rivendita di prodotti petroliferi
    RF13 = "RF13"  # Agenzie di viaggi e turismo
    RF14 = "RF14"  # Rivendita di prodotti petroliferi
    RF15 = "RF15"  # Agenzie di viaggi e turismo
    RF16 = "RF16"  # Rivendita di prodotti petroliferi
    RF17 = "RF17"  # Agenzie di viaggi e turismo
    RF18 = "RF18"  # Rivendita di prodotti petroliferi
    RF19 = "RF19"  # Agenzie di viaggi e turismo
    RF20 = "RF20"  # Rivendita di prodotti petroliferi


class TipoCassa(str, Enum):
    """Tipo Cassa - TCxx"""
    TC01 = "TC01"  # Cassa Nazionale Previdenza e Assistenza Avvocati
    TC02 = "TC02"  # Cassa Previdenza Dottori Commercialisti
    TC03 = "TC03"  # Cassa Previdenza e Assistenza Geometri
    TC04 = "TC04"  # Cassa Nazionale Previdenza e Assistenza Ingegneri e Architetti liberi professionisti
    TC05 = "TC05"  # Cassa Nazionale del Notariato
    TC06 = "TC06"  # Cassa Nazionale Previdenza e Assistenza Ragionieri e Periti Commerciali
    TC07 = "TC07"  # Ente Nazionale Assistenza Agenti e Rappresentanti di Commercio (ENASARCO)
    TC08 = "TC08"  # Ente Nazionale Previdenza e Assistenza Consulenti del Lavoro (ENPACL)
    TC09 = "TC09"  # Ente Nazionale Previdenza e Assistenza Medici (ENPAM)
    TC10 = "TC10"  # Ente Nazionale Previdenza e Assistenza Farmacisti (ENPAF)
    TC11 = "TC11"  # Ente Nazionale Previdenza e Assistenza Veterinari (ENPAV)
    TC12 = "TC12"  # Ente Nazionale Previdenza e Assistenza Impiegati dell'Agricoltura (ENPAIA)
    TC13 = "TC13"  # Fondo Previdenza Impiegati Imprese di Spedizione e Agenzie Marittime
    TC14 = "TC14"  # Istituto Nazionale Previdenza Giornalisti Italiani (INPGI)
    TC15 = "TC15"  # Opera Nazionale Assistenza Orfani Sanitari Italiani (ONAOSI)
    TC16 = "TC16"  # Cassa Autonoma Assistenza Integrativa Giornalisti Italiani (CASAGIT)
    TC17 = "TC17"  # Ente Previdenza e Assistenza Pluricategoriale (EPAP)
    TC18 = "TC18"  # Ente Nazionale Previdenza e Assistenza Biologi (ENPAB)
    TC19 = "TC19"  # Ente Nazionale Previdenza e Assistenza Professionale Infermieristica (ENPAPI)
    TC20 = "TC20"  # Ente Nazionale Previdenza e Assistenza Psicologi (ENPAP)
    TC21 = "TC21"  # INPS
    TC22 = "TC22"  # Altri enti previdenziali


class ModalitaPagamento(str, Enum):
    """Modalità Pagamento - MPxx"""
    MP01 = "MP01"  # Contanti
    MP02 = "MP02"  # Assegno
    MP03 = "MP03"  # Assegno circolare
    MP04 = "MP04"  # Contanti presso Tesoreria
    MP05 = "MP05"  # Bonifico
    MP06 = "MP06"  # Vaglia cambiario
    MP07 = "MP07"  # Bollettino bancario
    MP08 = "MP08"  # Carta di pagamento
    MP09 = "MP09"  # Ritenuta su somme già riscosse
    MP10 = "MP10"  # Ritenuta su somme già riscosse
    MP11 = "MP11"  # Altro
    MP12 = "MP12"  # Banca Sella
    MP13 = "MP13"  # Quota adesione SOGEI
    MP14 = "MP14"  # PayPal
    MP15 = "MP15"  # Amazon Pay
    MP16 = "MP16"  # Apple Pay
    MP17 = "MP17"  # Google Pay
    MP18 = "MP18"  # Satispay
    MP19 = "MP19"  # Altro
    MP20 = "MP20"  # Altro
    MP21 = "MP21"  # Altro
    MP22 = "MP22"  # Altro
    MP23 = "MP23"  # Altro


class TipoDocumento(str, Enum):
    """Tipo Documento - TDxx"""
    TD01 = "TD01"  # Fattura
    TD02 = "TD02"  # Acconto/Anticipo su fattura
    TD03 = "TD03"  # Acconto/Anticipo su parcella
    TD04 = "TD04"  # Nota di credito
    TD05 = "TD05"  # Nota di debito
    TD06 = "TD06"  # Parcella
    TD16 = "TD16"  # Integrazione fattura reverse charge interno
    TD17 = "TD17"  # Integrazione/autofattura per acquisti servizi dall'estero
    TD18 = "TD18"  # Integrazione per acquisti in sanatoria
    TD19 = "TD19"  # Regolarizzazione e integrazione delle fatture (art.6 c.8 d.lgs 471/97)
    TD20 = "TD20"  # Autofattura per regolarizzazione e integrazione (art.6 c.8 d.lgs 471/97)
    TD21 = "TD21"  # Autofattura per splafonamento
    TD22 = "TD22"  # Estrazione beni da Deposito IVA
    TD23 = "TD23"  # Estrazione beni da Deposito IVA con versamento dell'IVA
    TD24 = "TD24"  # Fattura differita di cui all'art.21, comma 4, lett. a)
    TD25 = "TD25"  # Fattura differita di cui all'art.21, comma 4, terzo periodo lett. a)
    TD26 = "TD26"  # Cessione di beni ammortizzabili e per passaggi interni (art.36 DPR 633/72)
    TD27 = "TD27"  # Autofattura per regolarizzazione e integrazione (art.6 c.8 d.lgs 471/97)
    TD28 = "TD28"  # Autofattura per splafonamento (art.6 c.8 d.lgs 471/97)
    TD29 = "TD29"  # Autofattura per regolarizzazione e integrazione (art.6 c.8 d.lgs 471/97)


class Natura(str, Enum):
    """Natura - Nxx"""
    N1 = "N1"      # Escluse ex art. 15
    N2_1 = "N2.1"  # Non soggette - altri casi
    N2_2 = "N2.2"  # Non soggette - artt. da 7 a 7-septies del DPR 633/72
    N3_1 = "N3.1"  # Non soggette - D.L. 50/2017, art. 3, c. 3
    N3_2 = "N3.2"  # Non soggette - D.L. 50/2017, art. 3, c. 4
    N3_3 = "N3.3"  # Non soggette - D.L. 50/2017, art. 3, c. 5
    N3_4 = "N3.4"  # Non soggette - D.L. 50/2017, art. 3, c. 6
    N3_5 = "N3.5"  # Non soggette - D.L. 50/2017, art. 3, c. 7
    N3_6 = "N3.6"  # Non soggette - D.L. 50/2017, art. 3, c. 8
    N4 = "N4"      # Esenti
    N5 = "N5"      # Regime del margine / IVA non esposta in fattura
    N6_1 = "N6.1"  # Inversione contabile - cessione di rottami e altri materiali di recupero
    N6_2 = "N6.2"  # Inversione contabile - cessione di oro e argento ai sensi della legge 7/2000
    N6_3 = "N6.3"  # Inversione contabile - subappalto nel settore edile
    N6_4 = "N6.4"  # Inversione contabile - cessione di fabbricati
    N6_5 = "N6.5"  # Inversione contabile - cessione di telefoni cellulari
    N6_6 = "N6.6"  # Inversione contabile - cessione di prodotti elettronici
    N6_7 = "N6.7"  # Inversione contabile - prestazioni comparto edile
    N6_8 = "N6.8"  # Inversione contabile - operazioni settore energetico
    N6_9 = "N6.9"  # Inversione contabile - altri casi
    N7 = "N7"      # IVA assolta in altro stato UE


class TipoRitenuta(str, Enum):
    """Tipo Ritenuta - RTxx"""
    RT01 = "RT01"  # Ritenuta su somme già riscosse
    RT02 = "RT02"  # Ritenuta su somme già riscosse
    RT03 = "RT03"  # Ritenuta su somme già riscosse
    RT04 = "RT04"  # Ritenuta su somme già riscosse
    RT05 = "RT05"  # Ritenuta su somme già riscosse
    RT06 = "RT06"  # Ritenuta su somme già riscosse


class FormatoTrasmissione(str, Enum):
    """Formato Trasmissione"""
    FPR12 = "FPR12"  # Fattura verso privati
    FPA12 = "FPA12"  # Fattura verso PA


class TipoCessionePrestazione(str, Enum):
    """Tipo Cessione Prestazione"""
    SC = "SC"  # Sconto
    PR = "PR"  # Premio
    AB = "AB"  # Abbuono
    AC = "AC"  # Spesa accessoria


class CondizioniPagamento(str, Enum):
    """Condizioni Pagamento"""
    TP01 = "TP01"  # Contanti
    TP02 = "TP02"  # A scadenza fissa
    TP03 = "TP03"  # A scadenza variabile


class EsigibilitaIVA(str, Enum):
    """Esigibilità IVA"""
    I = "I"  # Immediata
    D = "D"  # Differita
    S = "S"  # Scissione pagamenti


class TipoScontoMaggiorazione(str, Enum):
    """Tipo Sconto/Maggiorazione"""
    SC = "SC"  # Sconto
    MG = "MG"  # Maggiorazione
