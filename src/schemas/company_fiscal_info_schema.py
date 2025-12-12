from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CompanyFiscalInfoSchema(BaseModel):
    """Schema per creazione informazioni fiscali aziendali"""
    id_store: int = Field(..., gt=0, description="ID dello store")
    company_name: str = Field(..., max_length=200, description="Ragione sociale")
    vat_number: str = Field(..., max_length=50, description="Partita IVA")
    fiscal_code: Optional[str] = Field(None, max_length=50, description="Codice Fiscale")
    rea_number: Optional[str] = Field(None, max_length=50, description="Numero REA")
    address: Optional[str] = Field(None, max_length=255, description="Indirizzo")
    postal_code: Optional[str] = Field(None, max_length=20, description="CAP")
    city: Optional[str] = Field(None, max_length=100, description="Città")
    province: Optional[str] = Field(None, max_length=10, description="Provincia")
    country: Optional[str] = Field(None, max_length=5, description="Codice paese ISO")
    phone: Optional[str] = Field(None, max_length=50, description="Telefono")
    fax: Optional[str] = Field(None, max_length=50, description="FAX")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    pec: Optional[str] = Field(None, max_length=255, description="PEC")
    sdi_code: Optional[str] = Field(None, max_length=50, description="Codice SDI")
    bank_name: Optional[str] = Field(None, max_length=200, description="Nome banca")
    iban: Optional[str] = Field(None, max_length=50, description="IBAN")
    bic_swift: Optional[str] = Field(None, max_length=20, description="BIC/SWIFT")
    abi: Optional[str] = Field(None, max_length=10, description="ABI")
    cab: Optional[str] = Field(None, max_length=10, description="CAB")
    account_holder: Optional[str] = Field(None, max_length=200, description="Intestatario conto")
    account_number: Optional[str] = Field(None, max_length=50, description="Numero conto")
    is_default: bool = Field(False, description="P.IVA principale")


class CompanyFiscalInfoUpdateSchema(BaseModel):
    """Schema per aggiornamento informazioni fiscali aziendali"""
    id_store: Optional[int] = Field(None, gt=0, description="ID dello store")
    company_name: Optional[str] = Field(None, max_length=200, description="Ragione sociale")
    vat_number: Optional[str] = Field(None, max_length=50, description="Partita IVA")
    fiscal_code: Optional[str] = Field(None, max_length=50, description="Codice Fiscale")
    rea_number: Optional[str] = Field(None, max_length=50, description="Numero REA")
    address: Optional[str] = Field(None, max_length=255, description="Indirizzo")
    postal_code: Optional[str] = Field(None, max_length=20, description="CAP")
    city: Optional[str] = Field(None, max_length=100, description="Città")
    province: Optional[str] = Field(None, max_length=10, description="Provincia")
    country: Optional[str] = Field(None, max_length=5, description="Codice paese ISO")
    phone: Optional[str] = Field(None, max_length=50, description="Telefono")
    fax: Optional[str] = Field(None, max_length=50, description="FAX")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    pec: Optional[str] = Field(None, max_length=255, description="PEC")
    sdi_code: Optional[str] = Field(None, max_length=50, description="Codice SDI")
    bank_name: Optional[str] = Field(None, max_length=200, description="Nome banca")
    iban: Optional[str] = Field(None, max_length=50, description="IBAN")
    bic_swift: Optional[str] = Field(None, max_length=20, description="BIC/SWIFT")
    abi: Optional[str] = Field(None, max_length=10, description="ABI")
    cab: Optional[str] = Field(None, max_length=10, description="CAB")
    account_holder: Optional[str] = Field(None, max_length=200, description="Intestatario conto")
    account_number: Optional[str] = Field(None, max_length=50, description="Numero conto")
    is_default: Optional[bool] = Field(None, description="P.IVA principale")


class CompanyFiscalInfoResponseSchema(BaseModel):
    """Schema per risposta informazioni fiscali aziendali"""
    id_company_fiscal_info: int
    id_store: int
    company_name: str
    vat_number: str
    fiscal_code: Optional[str]
    rea_number: Optional[str]
    address: Optional[str]
    postal_code: Optional[str]
    city: Optional[str]
    province: Optional[str]
    country: Optional[str]
    phone: Optional[str]
    fax: Optional[str]
    email: Optional[str]
    pec: Optional[str]
    sdi_code: Optional[str]
    bank_name: Optional[str]
    iban: Optional[str]
    bic_swift: Optional[str]
    abi: Optional[str]
    cab: Optional[str]
    account_holder: Optional[str]
    account_number: Optional[str]
    is_default: bool
    date_add: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

