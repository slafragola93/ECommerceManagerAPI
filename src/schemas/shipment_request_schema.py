from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class EnvironmentEnum(str, Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class ShipmentRequestSchema(BaseModel):
    """Shipment request schema for audit"""
    id_order: int = Field(..., description="Order ID")
    id_carrier_api: int = Field(..., description="Carrier API ID")
    awb: Optional[str] = Field(None, description="Air Waybill number")
    message_reference: Optional[str] = Field(None, description="Message reference for idempotency")
    request_json_redacted: Optional[str] = Field(None, description="Redacted request JSON")
    response_json_redacted: Optional[str] = Field(None, description="Redacted response JSON")
    environment: EnvironmentEnum = Field(..., description="Environment (sandbox/production)")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class ShipmentRequestResponseSchema(BaseModel):
    """Shipment request response schema"""
    id: int = Field(..., description="Shipment request ID")
    id_order: int = Field(..., description="Order ID")
    id_carrier_api: int = Field(..., description="Carrier API ID")
    awb: Optional[str] = Field(None, description="Air Waybill number")
    message_reference: Optional[str] = Field(None, description="Message reference")
    environment: EnvironmentEnum = Field(..., description="Environment")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class ShipmentDocumentSchema(BaseModel):
    """Shipment document schema"""
    id: int = Field(..., description="Document ID")
    awb: str = Field(..., description="Air Waybill number")
    type_code: str = Field(..., description="Document type (label, invoice, etc.)")
    file_path: str = Field(..., description="File path on filesystem")
    mime_type: str = Field(..., description="MIME type")
    sha256_hash: str = Field(..., description="SHA256 hash for integrity")
    size_bytes: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class ShipmentDocumentResponseSchema(BaseModel):
    """Shipment document response schema"""
    id: int = Field(..., description="Document ID")
    awb: str = Field(..., description="Air Waybill number")
    type_code: str = Field(..., description="Document type")
    file_path: str = Field(..., description="File path")
    mime_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
