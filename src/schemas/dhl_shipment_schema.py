from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DhlAddressSchema(BaseModel):
    """DHL Address schema for shipper/receiver details"""
    address_line1: str = Field(..., description="Street address")
    postal_code: str = Field(..., description="Postal/ZIP code")
    city_name: str = Field(..., description="City name")
    country_code: str = Field(..., description="2-letter country code")
    province_code: Optional[str] = Field(None, description="Province/state code")


class DhlContactSchema(BaseModel):
    """DHL Contact information schema"""
    company_name: Optional[str] = Field(None, description="Company name")
    full_name: str = Field(..., description="Full contact name")
    phone: str = Field(..., description="Phone number")
    email: str = Field(..., description="Email address")


class DhlPackageSchema(BaseModel):
    """DHL Package schema"""
    weight: float = Field(..., description="Package weight")
    dimensions: Dict[str, float] = Field(..., description="Package dimensions (length, width, height)")
    description: Optional[str] = Field(None, description="Package description")


class DhlShipmentRequestSchema(BaseModel):
    """DHL Shipment creation request schema"""
    planned_shipping_date_and_time: str = Field(..., description="Planned shipping date in GMT format")
    product_code: str = Field(..., description="DHL product code")
    accounts: List[Dict[str, str]] = Field(..., description="Account numbers")
    customer_references: Optional[List[Dict[str, str]]] = Field(None, description="Customer references")
    pickup: Optional[Dict[str, Any]] = Field(None, description="Pickup details")
    output_image_properties: Optional[Dict[str, Any]] = Field(None, description="Label output properties")
    get_rate_estimates: bool = Field(default=False, description="Whether to get rate estimates")
    customer_details: Dict[str, Any] = Field(..., description="Shipper and receiver details")
    content: Dict[str, Any] = Field(..., description="Shipment content details")


class DhlDocumentSchema(BaseModel):
    """DHL Document schema for PDF labels"""
    image_format: str = Field(..., description="Document format (PDF)")
    content: str = Field(..., description="Base64 encoded document content")
    type_code: str = Field(..., description="Document type (label, invoice, etc.)")


class DhlPickupDetailsSchema(BaseModel):
    """DHL Pickup details schema"""
    local_cutoff_date_and_time: Optional[str] = Field(None, description="Local cutoff time")
    cutoff_time_offset: Optional[str] = Field(None, description="Cutoff time offset")
    pickup_earliest: Optional[str] = Field(None, description="Earliest pickup time")
    pickup_latest: Optional[str] = Field(None, description="Latest pickup time")
    pickup_cutoff_same_day_outbound_processing: Optional[str] = Field(None, description="Same day processing cutoff")
    total_transit_days: Optional[str] = Field(None, description="Total transit days")
    pickup_additional_days: Optional[str] = Field(None, description="Additional pickup days")
    delivery_additional_days: Optional[str] = Field(None, description="Additional delivery days")
    pickup_day_of_week: Optional[str] = Field(None, description="Pickup day of week")
    delivery_day_of_week: Optional[str] = Field(None, description="Delivery day of week")


class DhlEstimatedDeliverySchema(BaseModel):
    """DHL Estimated delivery schema"""
    estimated_delivery_date: Optional[str] = Field(None, description="Estimated delivery date")
    estimated_delivery_type: Optional[str] = Field(None, description="Delivery type")


class DhlShipmentResponseSchema(BaseModel):
    """DHL Shipment creation response schema"""
    shipment_tracking_number: str = Field(..., description="DHL tracking number (AWB)")
    tracking_url: Optional[str] = Field(None, description="Tracking URL")
    packages: Optional[List[Dict[str, Any]]] = Field(None, description="Package details")
    documents: Optional[List[DhlDocumentSchema]] = Field(None, description="Generated documents (labels, invoices)")
    shipment_details: Optional[List[Dict[str, Any]]] = Field(None, description="Shipment details")
    estimated_delivery_date: Optional[DhlEstimatedDeliverySchema] = Field(None, description="Estimated delivery")


class DhlErrorResponseSchema(BaseModel):
    """DHL Error response schema"""
    instance: str = Field(..., description="Error instance path")
    detail: str = Field(..., description="Error detail message")
    title: str = Field(..., description="Error title")
    message: str = Field(..., description="Error message")
    status: str = Field(..., description="HTTP status")
    code: Optional[str] = Field(None, description="Error code")


# Request schemas for API endpoints
class DhlCreateShipmentRequest(BaseModel):
    """Request schema for creating DHL shipment"""
    order_id: int = Field(..., description="Order ID to create shipment for")


class DhlCreateShipmentResponse(BaseModel):
    """Response schema for DHL shipment creation"""
    awb: str = Field(..., description="Air Waybill number")
    label_path: Optional[str] = Field(None, description="Path to saved label file")
    estimated_delivery: Optional[str] = Field(None, description="Estimated delivery date")
    pickup_details: Optional[Dict[str, Any]] = Field(None, description="Pickup details")
    tracking_url: Optional[str] = Field(None, description="DHL tracking URL")
