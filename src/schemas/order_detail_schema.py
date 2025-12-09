from typing import Optional

from pydantic import BaseModel, Field, validator


class OrderDetailSchema(BaseModel):
    id_order: Optional[int] = 0
    id_order_document: Optional[int] = 0
    id_origin: Optional[int] = 0
    id_tax: Optional[int] = 0
    id_product: Optional[int] = Field(None, ge=0)
    product_name: str = Field(..., max_length=100)
    product_reference: str = Field(..., max_length=100)
    product_qty: int = Field(..., ge=0)
    unit_price_net: Optional[float] = Field(None, ge=0, description="Prezzo unitario senza IVA")
    unit_price_with_tax: float = Field(..., ge=0, description="Prezzo unitario con IVA (obbligatorio)")
    total_price_net: float = Field(..., ge=0, description="Totale senza IVA (obbligatorio)")
    total_price_with_tax: float = Field(..., ge=0, description="Totale con IVA (obbligatorio)")
    product_weight: Optional[float] = 0.0
    reduction_percent: Optional[float] = 0.0
    reduction_amount: Optional[float] = 0.0
    rda_quantity: Optional[int] = Field(None, ge=0, description="Quantità da restituire")
    note: Optional[str] = Field(None, max_length=200)
    
    @validator('rda_quantity')
    def validate_rda_quantity(cls, v, values):
        """Valida che rda_quantity non superi product_qty"""
        if v is not None and 'product_qty' in values:
            if v > values.get('product_qty', 0):
                raise ValueError('rda_quantity non può superare product_qty')
        return v
    
    # Backward compatibility: product_price come alias per unit_price_net
    @property
    def product_price(self):
        return self.unit_price_net
    
    @product_price.setter
    def product_price(self, value):
        self.unit_price_net = value


class OrderDetailResponseSchema(BaseModel):
    id_order_detail: int
    id_order: int
    id_order_document: int
    id_origin: int
    id_tax: int
    id_product: int
    product_name: str
    product_reference: str
    product_qty: int
    unit_price_net: Optional[float] = None
    unit_price_with_tax: float
    total_price_net: float
    total_price_with_tax: float
    product_weight: float
    reduction_percent: float
    reduction_amount: float
    rda_quantity: Optional[int] = None
    note: Optional[str] = None
    img_url: Optional[str] = None  
    
    @validator('unit_price_net', 'unit_price_with_tax', 'total_price_net', 'total_price_with_tax', 
               'product_weight', 'reduction_percent', 'reduction_amount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)
    
    # Backward compatibility: product_price come alias per unit_price_net
    @property
    def product_price(self):
        return self.unit_price_net
    
    @product_price.setter
    def product_price(self, value):
        self.unit_price_net = value


class AllOrderDetailsResponseSchema(BaseModel):
    order_details: list[OrderDetailResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
