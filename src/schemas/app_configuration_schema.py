from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AppConfigurationSchema(BaseModel):
    """Schema per la creazione e aggiornamento di configurazioni app"""
    id_lang: int = Field(default=0)
    category: str = Field(..., max_length=50, description="Categoria della configurazione")
    name: str = Field(..., max_length=100, description="Nome della configurazione")
    value: Optional[str] = Field(default=None, description="Valore della configurazione")
    description: Optional[str] = Field(default=None, max_length=255, description="Descrizione della configurazione")
    is_encrypted: bool = Field(default=False, description="Indica se il valore è criptato")


class AppConfigurationResponseSchema(BaseModel):
    """Schema per la risposta delle configurazioni app"""
    id_app_configuration: int
    id_lang: int
    category: str
    name: str
    value: Optional[str]
    description: Optional[str]
    is_encrypted: bool
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None

    class Config:
        from_attributes = True


class AppConfigurationUpdateSchema(BaseModel):
    """Schema per l'aggiornamento parziale delle configurazioni app"""
    value: Optional[str] = Field(default=None, description="Valore della configurazione")
    description: Optional[str] = Field(default=None, max_length=255, description="Descrizione della configurazione")
    is_encrypted: Optional[bool] = Field(default=None, description="Indica se il valore è criptato")


class AllAppConfigurationsResponseSchema(BaseModel):
    """Schema per la risposta di tutte le configurazioni app"""
    configurations: list[AppConfigurationResponseSchema]
    total: int
    page: int
    limit: int


class AppConfigurationByCategoryResponseSchema(BaseModel):
    """Schema per la risposta delle configurazioni raggruppate per categoria"""
    category: str
    configurations: list[AppConfigurationResponseSchema]
    total: int


class AllAppConfigurationsByCategoryResponseSchema(BaseModel):
    """Schema per la risposta di tutte le configurazioni raggruppate per categoria"""
    categories: list[AppConfigurationByCategoryResponseSchema]
    total_categories: int
    total_configurations: int


# Schemi specifici per le categorie di configurazione
class CompanyInfoSchema(BaseModel):
    """Schema per le configurazioni di anagrafica azienda"""
    company_logo: Optional[str] = Field(default=None, description="Logo azienda")
    company_name: Optional[str] = Field(default=None, description="Ragione sociale")
    vat_number: Optional[str] = Field(default=None, description="Partita IVA")
    fiscal_code: Optional[str] = Field(default=None, description="Codice Fiscale")
    share_capital: Optional[str] = Field(default=None, description="Capitale sociale")
    rea_number: Optional[str] = Field(default=None, description="Numero REA")
    address: Optional[str] = Field(default=None, description="Indirizzo")
    postal_code: Optional[str] = Field(default=None, description="CAP")
    city: Optional[str] = Field(default=None, description="Città")
    province: Optional[str] = Field(default=None, description="Provincia")
    country: Optional[str] = Field(default=None, description="Nazione")
    phone: Optional[str] = Field(default=None, description="Telefono")
    fax: Optional[str] = Field(default=None, description="FAX")
    email: Optional[str] = Field(default=None, description="Email")
    website: Optional[str] = Field(default=None, description="Sito web")
    bank_name: Optional[str] = Field(default=None, description="Banca")
    iban: Optional[str] = Field(default=None, description="IBAN")
    bic_swift: Optional[str] = Field(default=None, description="BIC/SWIFT")
    account_holder: Optional[str] = Field(default=None, description="Intestazione")
    account_number: Optional[str] = Field(default=None, description="Numero conto")
    abi: Optional[str] = Field(default=None, description="ABI")
    cab: Optional[str] = Field(default=None, description="CAB")


class ElectronicInvoicingSchema(BaseModel):
    """Schema per le configurazioni di fatturazione elettronica"""
    tax_regime: Optional[str] = Field(default=None, description="Regime fiscale")
    transmitter_fiscal_code: Optional[str] = Field(default=None, description="Codice fiscale trasmittente")
    send_progressive: Optional[str] = Field(default=None, description="Progressivo Invio")
    register_number: Optional[str] = Field(default=None, description="Iscrizione Albo")
    rea_registration: Optional[str] = Field(default=None, description="Iscrizione REA")
    cash_type: Optional[str] = Field(default=None, description="Tipo Cassa")
    withholding_type: Optional[str] = Field(default=None, description="Tipo Ritenuta")
    vat_exigibility: Optional[str] = Field(default=None, description="Esigibilità IVA")
    intermediary_name: Optional[str] = Field(default=None, description="Intermediario - Denominazione")
    intermediary_vat: Optional[str] = Field(default=None, description="Intermediario - Partita IVA")
    intermediary_fiscal_code: Optional[str] = Field(default=None, description="Intermediario - Codice Fiscale")


class ExemptRatesSchema(BaseModel):
    """Schema per le configurazioni di aliquote esenti"""
    exempt_rate_standard: Optional[str] = Field(default=None, description="Aliquota esente")
    exempt_rate_no: Optional[str] = Field(default=None, description="Aliquota no")
    exempt_rate_no_x: Optional[str] = Field(default=None, description="Aliquota noX")
    exempt_rate_vat_refund: Optional[str] = Field(default=None, description="Restituzione IVA")
    exempt_rate_spring: Optional[str] = Field(default=None, description="Aliquota spring")
    exempt_rate_san_marino: Optional[str] = Field(default=None, description="Aliquota San Marino")
    exempt_rate_commissions: Optional[str] = Field(default=None, description="Aliquota commissioni")


class FatturapaSchema(BaseModel):
    """Schema per le configurazioni Fatturapa"""
    api_key: Optional[str] = Field(default=None, description="Chiave API Fatturapa")


class EmailSettingsSchema(BaseModel):
    """Schema per le configurazioni email"""
    sender_name: Optional[str] = Field(default=None, description="Nome mittente")
    sender_email: Optional[str] = Field(default=None, description="Email")
    password: Optional[str] = Field(default=None, description="Password")
    ccn: Optional[str] = Field(default=None, description="CCN")
    smtp_server: Optional[str] = Field(default=None, description="Server SMTP")
    smtp_port: Optional[str] = Field(default=None, description="Porta")
    security: Optional[str] = Field(default=None, description="Sicurezza")


class ApiKeysSchema(BaseModel):
    """Schema per le chiavi API dell'app"""
    app_api_key: Optional[str] = Field(default=None, description="Chiave API App")


class EcommerceSchema(BaseModel):
    """Schema per le configurazioni ecommerce"""
    base_url: Optional[str] = Field(default=None, description="URL base della piattaforma ecommerce")
    api_key: Optional[str] = Field(default=None, description="Chiave API della piattaforma ecommerce")