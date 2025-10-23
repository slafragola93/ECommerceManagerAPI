from sqlalchemy import Integer, Column, String, Numeric, Text, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from src.database import Base
import enum


class UnitOfMeasureEnum(str, enum.Enum):
    METRIC = "Metric"
    IMPERIAL = "Imperial"


class LabelFormatEnum(str, enum.Enum):
    PDF = "PDF"
    ZPL = "ZPL"


class DhlConfiguration(Base):
    __tablename__ = "dhl_configurations"
    
    id_dhl_config = Column(Integer, primary_key=True, index=True)
    id_carrier_api = Column(Integer, ForeignKey('carriers_api.id_carrier_api', ondelete='CASCADE'), unique=True, index=True)
    
    # Campi specifici DHL (MyDHL API)
    description = Column(String(255))
    shipper_account_number = Column(String(255))  # renamed from account_number
    company_name = Column(String(255))
    city = Column(String(100))
    address = Column(String(255))
    postal_code = Column(String(20))
    country_code = Column(String(2))  # renamed from country_iso, 2-letter ISO
    reference_person = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    default_weight = Column(Numeric(10, 2))
    package_height = Column(Integer)
    package_width = Column(Integer)
    package_depth = Column(Integer)
    goods_description = Column(Text)
    
    # MyDHL API specific fields
    label_format = Column(Enum(LabelFormatEnum), default=LabelFormatEnum.PDF)  # renamed from layout
    unit_of_measure = Column(Enum(UnitOfMeasureEnum), default=UnitOfMeasureEnum.METRIC)
    default_is_customs_declarable = Column(Boolean, default=False)
    default_incoterm = Column(String(3), nullable=True)
    duties_account_number = Column(String(255), nullable=True)
    payer_account_number = Column(String(255), nullable=True)
    province_code = Column(String(50), nullable=True)
    tax_id = Column(String(255), nullable=True)  # VAT/EORI
    pickup_is_requested = Column(Boolean, default=False)
    pickup_close_time = Column(String(5), nullable=True)  # HH:mm format
    pickup_location = Column(String(255), nullable=True)
    
    # Service codes
    default_product_code_domestic = Column(String(100))  # renamed from national_service
    default_product_code_international = Column(String(100))  # renamed from international_service
    
    # COD fields (replaced cash_on_delivery)
    cod_enabled = Column(Boolean, default=False)
    cod_currency = Column(String(3), nullable=True)
    
    # Relationship 1:1
    carrier_api = relationship("CarrierApi", back_populates="dhl_configuration")
