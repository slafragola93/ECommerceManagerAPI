from typing import Optional
from pydantic import BaseModel, Field


class BrtConfigurationSchema(BaseModel):
    description: str = Field(..., max_length=255)
    sender: str = Field(..., max_length=255)
    api_user: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9]+$')
    api_password: str = Field(..., max_length=255)
    departure_line: int = Field(..., gt=0)
    client_code: int = Field(..., gt=0)
    departure_branch: int = Field(..., gt=0)
    rate_code: int = Field(..., gt=0)
    service_type: str = Field(..., max_length=100)
    default_weight: int = Field(..., gt=0)
    notes: Optional[str] = None
    
    # Select values (salvano solo il valore scelto come stringa)
    collection_mode: str = Field(..., max_length=50)
    network: str = Field(..., max_length=50)
    label_format: str = Field(..., max_length=50)
    customer_notification: str = Field(..., max_length=50)
    tracking_type: str = Field(..., max_length=50)


class BrtConfigurationResponseSchema(BaseModel):
    id_brt_config: int
    id_carrier_api: int
    description: str
    sender: str
    api_user: str
    departure_line: int
    client_code: int
    departure_branch: int
    rate_code: int
    service_type: str
    default_weight: int
    notes: Optional[str]
    collection_mode: str
    network: str
    label_format: str
    customer_notification: str
    tracking_type: str
    
    model_config = {"from_attributes": True}


class BrtConfigurationUpdateSchema(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    sender: Optional[str] = Field(None, max_length=255)
    api_user: Optional[str] = Field(None, max_length=100, pattern=r'^[a-zA-Z0-9]+$')
    api_password: Optional[str] = Field(None, max_length=255)
    departure_line: Optional[int] = Field(None, gt=0)
    client_code: Optional[int] = Field(None, gt=0)
    departure_branch: Optional[int] = Field(None, gt=0)
    rate_code: Optional[int] = Field(None, gt=0)
    service_type: Optional[str] = Field(None, max_length=100)
    default_weight: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None
    collection_mode: Optional[str] = Field(None, max_length=50)
    network: Optional[str] = Field(None, max_length=50)
    label_format: Optional[str] = Field(None, max_length=50)
    customer_notification: Optional[str] = Field(None, max_length=50)
    tracking_type: Optional[str] = Field(None, max_length=50)
