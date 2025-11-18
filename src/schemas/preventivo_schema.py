from operator import ge
from typing import Optional, List, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from .customer_schema import CustomerSchema, CustomerResponseSchema
from .address_schema import AddressResponseSchema, AddressSchema
from .sectional_schema import SectionalSchema, SectionalResponseSchema
from .order_package_schema import OrderPackageResponseSchema


class CustomerField(BaseModel):
    """Campo customer che può essere ID o oggetto completo"""
    id: Optional[int] = Field(None, gt=0)
    data: Optional[CustomerSchema] = None
    
    @validator('id', 'data')
    def validate_customer_field(cls, v, values):
        """Valida che sia presente o id o data"""
        if not v and not values.get('data') and not values.get('id'):
            raise ValueError('Deve essere specificato o id o data per customer')
        return v


class AddressField(BaseModel):
    """Campo address che può essere ID o oggetto completo"""
    id: Optional[int] = Field(None, gt=0)
    data: Optional[AddressSchema] = None
    
    @validator('id', 'data')
    def validate_address_field(cls, v, values):
        """Valida che sia presente o id o data"""
        if not v and not values.get('data') and not values.get('id'):
            # Address è opzionale
            return v
        return v


class SectionalField(BaseModel):
    """Campo sectional che può essere ID o oggetto completo"""
    id: Optional[int] = Field(None, gt=0)
    data: Optional[SectionalSchema] = None
    
    @validator('id', 'data')
    def validate_sectional_field(cls, v, values):
        """Valida che sia presente o id o data"""
        if not v and not values.get('data') and not values.get('id'):
            # Sectional è opzionale
            return v
        return v


class ShippingField(BaseModel):
    """Campo shipping opzionale per preventivi"""
    price_tax_excl: float = Field(..., ge=0, description="Prezzo spedizione senza IVA")
    price_tax_incl: float = Field(..., ge=0, description="Prezzo spedizione con IVA")
    id_carrier_api: int = Field(..., gt=0, description="ID carrier API")
    id_tax: int = Field(..., gt=0, description="ID aliquota IVA per spedizione")
    shipping_message: Optional[str] = Field(None, max_length=200)


class OrderPackagePreventivoSchema(BaseModel):
    """Schema per order_package nella creazione preventivo"""
    height: float = Field(default=10.0, description="Altezza del pacco")
    width: float = Field(default=10.0, description="Larghezza del pacco")
    depth: float = Field(default=10.0, description="Profondità del pacco")
    length: float = Field(default=10.0, description="Lunghezza del pacco")
    weight: float = Field(default=0.0, ge=0, description="Peso del pacco")
    value: float = Field(default=0.0, ge=0, description="Valore del pacco")


class ArticoloPreventivoSchema(BaseModel):
    """Schema per articolo in preventivo (OrderDetail)"""
    id_order_detail: Optional[int]  = None
    id_product: Optional[int] = None  # Se articolo esistente
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(0.0, ge=0)
    product_weight: Optional[float] = Field(0.0, ge=0)
    product_qty: int = Field(1, gt=0)  # Integer come nel modello
    id_tax: int = Field(..., gt=0)  # Sempre obbligatorio
    reduction_percent: Optional[float] = Field(0.0, ge=0)  # Sconto percentuale
    reduction_amount: Optional[float] = Field(0.0, ge=0)  # Sconto importo
    note: Optional[str] = Field(None, max_length=200, description="Note per l'articolo")
    img_url: Optional[str] = None  # Image URL from product
    rda: Optional[str] = Field(None, max_length=10, description="RDA")
    
    @validator('product_name', 'product_reference', 'product_price', 'product_qty')
    def validate_fields_when_no_product(cls, v, values):
        """Valida che i campi siano presenti quando non c'è id_product"""
        # Per product_price, 0.0 è un valore valido, quindi controlliamo solo None
        if not values.get('id_product'):
            if v is None:
                raise ValueError('I campi product_name, product_reference, product_price e product_qty sono obbligatori quando non viene specificato id_product')
            # Per product_name e product_reference, controlla anche stringa vuota
            if isinstance(v, str) and not v.strip():
                raise ValueError('I campi product_name, product_reference, product_price e product_qty sono obbligatori quando non viene specificato id_product')
        return v
    
    @validator('product_price', 'product_weight', 'reduction_percent', 'reduction_amount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class PreventivoCreateSchema(BaseModel):
    """Schema per creazione preventivo"""
    customer: CustomerField = Field(..., description="Customer (ID o oggetto completo)")
    address_delivery: AddressField = Field(..., description="Address delivery (ID o oggetto completo) - obbligatorio")
    address_invoice: AddressField = Field(False, description="Address invoice (ID o oggetto completo) - se non specificato usa address_delivery")
    sectional: SectionalField = Field(..., description="Sezionale (ID o oggetto completo) - se esiste un sectional con lo stesso nome viene riutilizzato")
    shipping: ShippingField = Field(..., escription="Dati spedizione (opzionale)")
    id_payment: int = Field(..., gt=0, description="ID metodo di pagamento (opzionale)")
    is_invoice_requested: Optional[bool] = Field(False, description="Se richiedere fattura")
    is_payed: Optional[bool] = Field(None, description="Indica se il preventivo è pagato. Se non specificato, viene impostato automaticamente a True se il metodo di pagamento ha is_complete_payment=True")
    note: Optional[str] = None
    total_discount: Optional[float] = Field(0.0, ge=0, description="Sconto totale applicato al documento")
    articoli: List[ArticoloPreventivoSchema] = Field(default_factory=list)
    order_packages: List[OrderPackagePreventivoSchema] = Field(default_factory=list, description="Lista dei package del preventivo (opzionale)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer": {"id": 294488},
                "address_delivery": {"id": 470625},
                "note": "Preventivo esempio",
                "articoli": [
                    {
                        "id_product": 123,
                        "product_qty": 2,
                        "id_tax": 9
                    }
                ]
            }
        }


class CustomerUpdateField(BaseModel):
    """Schema per update customer - id null = crea, id presente = aggiorna"""
    id: Optional[int] = Field(None, description="ID customer esistente (null per creare nuovo)")
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    id_lang: Optional[int] = None
    id_origin: Optional[int] = None
    company: Optional[str] = None


class AddressUpdateField(BaseModel):
    """Schema per update address - id null = crea, id presente = aggiorna"""
    id: Optional[int] = Field(None, description="ID address esistente (null per creare nuovo)")
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    id_country: Optional[int] = None
    company: Optional[str] = None
    vat: Optional[str] = None
    dni: Optional[str] = None
    pec: Optional[str] = None
    sdi: Optional[str] = None
    ipa: Optional[str] = None
    id_origin: Optional[int] = None
    id_platform: Optional[int] = None


class SectionalUpdateField(BaseModel):
    """Schema per update sectional - id null = crea, id presente = aggiorna"""
    id: Optional[int] = Field(None, description="ID sectional esistente (null per creare nuovo)")
    name: Optional[str] = None


class ShippingUpdateField(BaseModel):
    """Schema per update shipping - id null = crea, id presente = aggiorna"""
    id: Optional[int] = Field(None, description="ID shipping esistente (null per creare nuovo)")
    price_tax_excl: Optional[float] = Field(None, ge=0)
    price_tax_incl: Optional[float] = Field(None, ge=0)
    id_carrier_api: Optional[int] = Field(None, gt=0)
    id_tax: Optional[int] = Field(None, gt=0)
    shipping_message: Optional[str] = Field(None, max_length=200)


class ArticoloPreventivoUpdateItemSchema(BaseModel):
    """Schema per articolo in update preventivo - id_order_detail null = crea, presente = aggiorna"""
    id_order_detail: Optional[int] = Field(None, description="ID articolo esistente (null per creare nuovo)")
    id_product: Optional[int] = None
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(None, ge=0)
    product_weight: Optional[float] = Field(None, ge=0)
    product_qty: Optional[int] = Field(None, gt=0)
    id_tax: Optional[int] = Field(None, gt=0)
    reduction_percent: Optional[float] = Field(None, ge=0)
    reduction_amount: Optional[float] = Field(None, ge=0)
    note: Optional[str] = Field(None, max_length=200)
    rda: Optional[str] = Field(None, max_length=10)


class OrderPackageUpdateItemSchema(BaseModel):
    """Schema per package in update preventivo - id_order_package null = crea, presente = aggiorna"""
    id_order_package: Optional[int] = Field(None, description="ID package esistente (null per creare nuovo)")
    height: Optional[float] = Field(None, ge=0)
    width: Optional[float] = Field(None, ge=0)
    depth: Optional[float] = Field(None, ge=0)
    length: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    value: Optional[float] = Field(None, ge=0)


class PreventivoUpdateSchema(BaseModel):
    """Schema per modifica preventivo con supporto entità nidificate"""
    # Campi semplici esistenti
    id_payment: Optional[int] = Field(None, ge=0, description="ID metodo di pagamento (opzionale)")
    is_invoice_requested: Optional[bool] = None
    is_payed: Optional[bool] = Field(None, description="Indica se il preventivo è pagato")
    note: Optional[str] = Field(None, max_length=200)
    total_discount: Optional[float] = Field(None, ge=0, description="Sconto totale applicato al documento")
    
    # NUOVI: Entità complesse con struttura unificata (id + campi)
    customer: Optional[CustomerUpdateField] = None
    address_delivery: Optional[AddressUpdateField] = None
    address_invoice: Optional[AddressUpdateField] = None
    sectional: Optional[SectionalUpdateField] = None
    shipping: Optional[ShippingUpdateField] = None
    
    # NUOVI: Liste con smart merge
    articoli: Optional[List[ArticoloPreventivoUpdateItemSchema]] = None
    order_packages: Optional[List[OrderPackageUpdateItemSchema]] = None
    
    # Campi NON modificabili (esclusi dallo schema):
    # - id_order (gestito automaticamente durante la conversione)
    # - document_number (generato automaticamente)
    # - type_document (sempre "preventivo")
    # - total_weight (calcolato automaticamente)
    # - total_price_with_tax (calcolato automaticamente)
    # - date_add (data di creazione, immutabile)


class ArticoloPreventivoUpdateSchema(BaseModel):
    """Schema per modifica articolo in preventivo (OrderDetail)"""
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(None, ge=0)
    product_weight: Optional[float] = Field(None, ge=0)
    product_qty: Optional[int] = Field(None, gt=0)  # Integer come nel modello
    id_tax: Optional[int] = Field(None, gt=0)
    reduction_percent: Optional[float] = Field(None, ge=0)  # Sconto percentuale
    reduction_amount: Optional[float] = Field(None, ge=0)  # Sconto importo
    rda: Optional[str] = Field(None, max_length=10)  # RDA
    note: Optional[str] = Field(None, max_length=200, description="Note per l'articolo")


class PreventivoShipmentSchema(BaseModel):
    id_shipping: int
    id_carrier_api: int
    tax_rate: float
    weight: float
    price_tax_incl: float
    price_tax_excl: float
    shipping_message: Optional[str] = None
    
    @validator('tax_rate', 'weight', 'price_tax_incl', 'price_tax_excl', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class PaymentPreventivoSchema(BaseModel):
    """Schema per metodo di pagamento nei preventivi"""
    id_payment: int = Field(..., description="ID del metodo di pagamento")
    name: str = Field(..., description="Nome del metodo di pagamento")
    is_complete_payment: bool = Field(..., description="Indica se è un pagamento completo")


class PreventivoResponseSchema(BaseModel):
    """Schema per risposta preventivo (lista) - usa ID per gli indirizzi"""
    id_order_document: int
    id_order: Optional[int] = None
    document_number: int
    id_customer: int
    id_address_delivery: Optional[int] = None
    id_address_invoice: Optional[int] = None
    sectional: Optional[SectionalResponseSchema] = None
    shipping: Optional[PreventivoShipmentSchema] = None
    payment: Optional[PaymentPreventivoSchema] = None
    is_invoice_requested: bool
    is_payed: Optional[bool] = None
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    type_document: str
    total_imponibile: float
    total_iva: float
    total_finale: float
    total_discount: float = Field(default=0.0, description="Sconto totale applicato al documento")
    date_add: Optional[datetime] = None
    updated_at: datetime
    articoli: List[ArticoloPreventivoSchema] = Field(default_factory=list)
    order_packages: List[OrderPackageResponseSchema] = Field(default_factory=list, description="Lista dei package del preventivo (solo se show_details=True)")

    @validator('total_imponibile', 'total_iva', 'total_finale', 'total_discount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)

    class Config:
        from_attributes = True


class PreventivoDetailResponseSchema(BaseModel):
    """Schema per risposta preventivo (dettaglio) - usa oggetti Address completi"""
    id_order_document: int
    id_order: Optional[int] = None
    document_number: int
    customer: Optional[CustomerResponseSchema] = None
    address_delivery: Optional[AddressResponseSchema] = None
    address_invoice: Optional[AddressResponseSchema] = None
    sectional: Optional[SectionalResponseSchema] = None
    shipping: Optional[PreventivoShipmentSchema] = None
    payment: Optional[PaymentPreventivoSchema] = None
    is_invoice_requested: bool
    is_payed: Optional[bool] = None
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    type_document: str
    total_imponibile: float
    total_iva: float
    total_finale: float
    total_discount: float = Field(default=0.0, description="Sconto totale applicato al documento")
    total_discounts_applied: float = Field(default=0.0, description="Totale di tutti gli sconti applicati (sconti articoli + sconto totale documento)")
    date_add: Optional[datetime] = None
    updated_at: datetime
    articoli: List[ArticoloPreventivoSchema] = Field(default_factory=list)
    order_packages: List[OrderPackageResponseSchema] = Field(default_factory=list, description="Lista dei package del preventivo")

    @validator('total_imponibile', 'total_iva', 'total_finale', 'total_discount', 'total_discounts_applied', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)

    class Config:
        from_attributes = True


class ConvertiPreventivoSchema(BaseModel):
    """Schema per conversione preventivo in ordine"""
    id_address_delivery: Optional[int] = None
    id_address_invoice: Optional[int] = None
    payment_method: Optional[str] = None
    note: Optional[str] = None


class PreventivoListResponseSchema(BaseModel):
    """Schema per lista preventivi"""
    preventivi: List[PreventivoResponseSchema]
    total: int
    page: int
    limit: int


# Schemi per operazioni bulk

class BulkPreventivoDeleteRequestSchema(BaseModel):
    """Schema per richiesta eliminazione massiva preventivi"""
    ids: List[int] = Field(..., min_items=1, description="Lista di ID preventivi da eliminare")

    class Config:
        json_schema_extra = {
            "example": {
                "ids": [1, 2, 3]
            }
        }


class BulkPreventivoDeleteError(BaseModel):
    """Errore di eliminazione preventivo fallita"""
    id_order_document: int
    error: str
    reason: str


class BulkPreventivoDeleteResponseSchema(BaseModel):
    """Schema per risposta eliminazione massiva preventivi"""
    successful: List[int] = Field(
        default_factory=list,
        description="Lista di ID preventivi eliminati con successo"
    )
    failed: List[BulkPreventivoDeleteError] = Field(
        default_factory=list,
        description="Lista di eliminazioni fallite"
    )
    summary: dict = Field(
        description="Riepilogo operazione: total, successful_count, failed_count"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "successful": [71, 72, 73, 74, 75],
                "failed": [],
                "summary": {
                    "total": 5,
                    "successful_count": 5,
                    "failed_count": 0
                }
            }
        }


class BulkPreventivoConvertRequestSchema(BaseModel):
    """Schema per richiesta conversione massiva preventivi in ordini"""
    ids: List[int] = Field(..., min_items=1, description="Lista di ID preventivi da convertire")

    class Config:
        json_schema_extra = {
            "example": {
                "ids": [1, 2, 3]
            }
        }


class BulkPreventivoConvertResult(BaseModel):
    """Risultato di una conversione preventivo in ordine riuscita"""
    id_order_document: int
    id_order: int
    document_number: int


class BulkPreventivoConvertError(BaseModel):
    """Errore di conversione preventivo fallita"""
    id_order_document: int
    error: str
    reason: str


class BulkPreventivoConvertResponseSchema(BaseModel):
    """Schema per risposta conversione massiva preventivi in ordini"""
    successful: List[BulkPreventivoConvertResult] = Field(
        default_factory=list,
        description="Lista di conversioni riuscite"
    )
    failed: List[BulkPreventivoConvertError] = Field(
        default_factory=list,
        description="Lista di conversioni fallite"
    )
    summary: dict = Field(
        description="Riepilogo operazione: total, successful_count, failed_count"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "successful": [
                    {
                        "id_order_document": 71,
                        "id_order": 101,
                        "document_number": 2024001
                    },
                    {
                        "id_order_document": 72,
                        "id_order": 102,
                        "document_number": 2024002
                    }
                ],
                "failed": [],
                "summary": {
                    "total": 2,
                    "successful_count": 2,
                    "failed_count": 0
                }
            }
        }


# Schemi per operazioni bulk articoli

class BulkRemoveArticoliRequestSchema(BaseModel):
    """Schema per richiesta eliminazione massiva articoli"""
    ids: List[int] = Field(..., min_items=1, description="Lista di ID order_detail da eliminare")

    class Config:
        json_schema_extra = {
            "example": {
                "ids": [101, 102, 103]
            }
        }


class BulkRemoveArticoliError(BaseModel):
    """Errore di eliminazione articolo fallita"""
    id_order_detail: int
    error: str
    reason: str


class BulkRemoveArticoliResponseSchema(BaseModel):
    """Schema per risposta eliminazione massiva articoli"""
    successful: List[int] = Field(
        default_factory=list,
        description="Lista di ID order_detail eliminati con successo"
    )
    failed: List[BulkRemoveArticoliError] = Field(
        default_factory=list,
        description="Lista di eliminazioni fallite"
    )
    summary: dict = Field(
        description="Riepilogo operazione: total, successful_count, failed_count"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "successful": [101, 102, 103],
                "failed": [],
                "summary": {
                    "total": 3,
                    "successful_count": 3,
                    "failed_count": 0
                }
            }
        }


class BulkUpdateArticoliItem(BaseModel):
    """Schema per singolo articolo da aggiornare in operazione bulk"""
    id_order_detail: int = Field(..., gt=0, description="ID dell'articolo da aggiornare")
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(None, ge=0)
    product_weight: Optional[float] = Field(None, ge=0)
    product_qty: Optional[int] = Field(None, gt=0)
    id_tax: Optional[int] = Field(None, gt=0)
    reduction_percent: Optional[float] = Field(None, ge=0)
    reduction_amount: Optional[float] = Field(None, ge=0)
    rda: Optional[str] = Field(None, max_length=10)
    note: Optional[str] = Field(None, max_length=200, description="Note per l'articolo")


class BulkUpdateArticoliError(BaseModel):
    """Errore di aggiornamento articolo fallito"""
    id_order_detail: int
    error: str
    reason: str


class BulkUpdateArticoliResponseSchema(BaseModel):
    """Schema per risposta aggiornamento massivo articoli"""
    successful: List[int] = Field(
        default_factory=list,
        description="Lista di ID order_detail aggiornati con successo"
    )
    failed: List[BulkUpdateArticoliError] = Field(
        default_factory=list,
        description="Lista di aggiornamenti falliti"
    )
    summary: dict = Field(
        description="Riepilogo operazione: total, successful_count, failed_count"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "successful": [101, 102],
                "failed": [],
                "summary": {
                    "total": 2,
                    "successful_count": 2,
                    "failed_count": 0
                }
            }
        }
