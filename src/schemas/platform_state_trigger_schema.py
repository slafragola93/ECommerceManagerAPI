"""
Schemas Pydantic per PlatformStateTrigger
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PlatformStateTriggerSchema(BaseModel):
    """Schema per creazione/aggiornamento trigger"""
    event_type: str = Field(..., description="Tipo evento (es. order_status_changed, shipping_status_changed)")
    id_platform: int = Field(..., gt=0, description="ID piattaforma")
    state_type: str = Field(..., description="Tipo stato: 'order_state' o 'shipping_state'")
    id_state_local: int = Field(..., gt=0, description="ID stato locale (OrderState.id_order_state o ShippingState.id_shipping_state)")
    id_state_platform: int = Field(..., gt=0, description="ID stato sulla piattaforma remota")
    is_active: bool = Field(default=True, description="Se il trigger è attivo")
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')


class PlatformStateTriggerUpdateSchema(BaseModel):
    """Schema per aggiornamento parziale trigger"""
    event_type: Optional[str] = Field(None, description="Tipo evento")
    id_platform: Optional[int] = Field(None, gt=0, description="ID piattaforma")
    state_type: Optional[str] = Field(None, description="Tipo stato")
    id_state_local: Optional[int] = Field(None, gt=0, description="ID stato locale")
    id_state_platform: Optional[int] = Field(None, gt=0, description="ID stato piattaforma remota")
    is_active: Optional[bool] = Field(None, description="Se il trigger è attivo")
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')


class PlatformStateTriggerResponseSchema(BaseModel):
    """Schema per risposta trigger"""
    id_trigger: int
    event_type: str
    id_platform: int
    state_type: str
    id_state_local: int
    id_state_platform: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')

