from pydantic import BaseModel, Field
from typing import Optional


class BrtCreateShipmentResponse(BaseModel):
    """Response schema for BRT shipment creation"""
    awb: str = Field(..., description="BRT tracking number (parcel ID)")

