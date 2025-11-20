from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FedexShipmentRequestSchema(BaseModel):
    """FedEx Shipment request schema"""
    order_id: int = Field(..., gt=0, description="Order ID to create shipment for")


class FedexShipmentResponseSchema(BaseModel):
    """FedEx Shipment response schema"""
    awb: str = Field(..., description="Air Waybill or tracking number")
    label_path: Optional[str] = Field(None, description="Path to saved label file")
    tracking_numbers: List[str] = Field(default_factory=list, description="List of tracking numbers")
    master_tracking_number: Optional[str] = Field(None, description="Master tracking number for multi-piece shipments")
    transaction_id: Optional[str] = Field(None, description="FedEx transaction ID")
    success: bool = Field(True, description="Whether shipment creation was successful")
    message: Optional[str] = Field(None, description="Response message")


class FedexValidateRequestSchema(BaseModel):
    """FedEx Validation request schema"""
    order_id: int = Field(..., gt=0, description="Order ID to validate shipment for")


class FedexValidateResponseSchema(BaseModel):
    """FedEx Validation response schema"""
    valid: bool = Field(..., description="Whether shipment data is valid")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="List of validation errors if any")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="List of validation warnings if any")


class FedexCancelRequestSchema(BaseModel):
    """FedEx Cancel shipment request schema"""
    tracking_number: str = Field(..., description="Tracking number to cancel")
    deletion_control: Optional[str] = Field(None, description="Deletion control: DELETE_ONE_PACKAGE or DELETE_ALL_PACKAGES")


class FedexCancelResponseSchema(BaseModel):
    """FedEx Cancel shipment response schema"""
    success: bool = Field(..., description="Whether cancellation was successful")
    message: str = Field(..., description="Cancellation result message")
    transaction_id: Optional[str] = Field(None, description="FedEx transaction ID")

