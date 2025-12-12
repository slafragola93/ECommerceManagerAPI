from sqlalchemy import Integer, Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from src.database import Base


class CompanyFiscalInfo(Base):
    """
    Modello per le informazioni fiscali aziendali associate a uno store.
    Permette di gestire più P.IVA per lo stesso store.
    """
    __tablename__ = "company_fiscal_info"

    id_company_fiscal_info = Column(Integer, primary_key=True, index=True)
    id_store = Column(Integer, ForeignKey('stores.id_store'), nullable=False, index=True)
    
    # Informazioni aziendali
    company_name = Column(String(200), nullable=False)
    vat_number = Column(String(50), nullable=False, index=True)
    fiscal_code = Column(String(50), nullable=True)
    rea_number = Column(String(50), nullable=True)
    
    # Indirizzo
    address = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    province = Column(String(10), nullable=True)
    country = Column(String(5), nullable=True)
    
    # Contatti
    phone = Column(String(50), nullable=True)
    fax = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    pec = Column(String(255), nullable=True)
    sdi_code = Column(String(50), nullable=True)
    
    # Dati bancari
    bank_name = Column(String(200), nullable=True)
    iban = Column(String(50), nullable=True)
    bic_swift = Column(String(20), nullable=True)
    abi = Column(String(10), nullable=True)
    cab = Column(String(10), nullable=True)
    account_holder = Column(String(200), nullable=True)
    account_number = Column(String(50), nullable=True)
    
    # Flag per identificare la P.IVA principale
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    date_add = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="company_fiscal_infos")

