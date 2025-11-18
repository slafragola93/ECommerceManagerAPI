from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class DhlTrackingEventSchema(BaseModel):
    """DHL Tracking event schema"""
    date: str = Field(..., description="Event date")
    time: str = Field(..., description="Event time")
    gmt_offset: str = Field(..., alias="GMTOffset", description="GMT offset")
    type_code: str = Field(..., description="Event type code (PU, OK, etc.)")
    description: str = Field(..., description="Event description")
    service_area: Optional[List[Dict[str, str]]] = Field(None, description="Service area details")
    signed_by: Optional[str] = Field(None, description="Signed by person")


class DhlTrackingPieceSchema(BaseModel):
    """DHL Tracking piece schema"""
    number: int = Field(..., description="Piece number")
    type_code: str = Field(..., description="Piece type code")
    shipment_tracking_number: str = Field(..., description="Shipment tracking number")
    tracking_number: str = Field(..., description="Piece tracking number")
    description: str = Field(..., description="Piece description")
    weight: float = Field(..., description="Piece weight")
    dimensional_weight: float = Field(..., description="Dimensional weight")
    actual_weight: float = Field(..., description="Actual weight")
    dimensions: Dict[str, float] = Field(..., description="Piece dimensions")
    actual_dimensions: Dict[str, float] = Field(..., description="Actual dimensions")
    unit_of_measurements: str = Field(..., description="Unit of measurement")
    shipper_references: Optional[List[Dict[str, str]]] = Field(None, description="Shipper references")
    events: List[DhlTrackingEventSchema] = Field(..., description="Piece events")


class DhlTrackingShipmentSchema(BaseModel):
    """DHL Tracking shipment schema"""
    shipment_tracking_number: str = Field(..., description="Shipment tracking number")
    status: str = Field(..., description="Shipment status")
    shipment_timestamp: str = Field(..., description="Shipment timestamp")
    product_code: str = Field(..., description="Product code")
    description: str = Field(..., description="Shipment description")
    shipper_details: Optional[Dict[str, Any]] = Field(None, description="Shipper details")
    receiver_details: Optional[Dict[str, Any]] = Field(None, description="Receiver details")
    total_weight: float = Field(..., description="Total weight")
    unit_of_measurements: str = Field(..., description="Unit of measurement")
    shipper_references: Optional[List[Dict[str, str]]] = Field(None, description="Shipper references")
    events: List[DhlTrackingEventSchema] = Field(..., description="Tracking events")
    number_of_pieces: int = Field(..., description="Number of pieces")
    pieces: List[DhlTrackingPieceSchema] = Field(..., description="Piece details")
    estimated_delivery_date: Optional[str] = Field(None, description="Estimated delivery date")
    children_shipment_identification_numbers: Optional[List[str]] = Field(None, description="Child shipment numbers")
    controlled_access_data_codes: Optional[List[str]] = Field(None, description="Controlled access codes")


class DhlTrackingResponseSchema(BaseModel):
    """DHL Tracking response schema"""
    shipments: List[DhlTrackingShipmentSchema] = Field(..., description="List of tracked shipments")


# Normalized schemas for internal use
class NormalizedTrackingEventSchema(BaseModel):
    """Normalized tracking event schema"""
    date: str = Field(..., description="Event date")
    description: str = Field(..., description="Event description")
    location: Optional[str] = Field(None, description="Event location")


class NormalizedTrackingResponseSchema(BaseModel):
    """Normalized tracking response schema"""
    tracking_number: str = Field(..., description="Tracking number")
    status: str = Field(..., description="Current status")
    events: List[NormalizedTrackingEventSchema] = Field(..., description="Tracking events")
    estimated_delivery_date: Optional[str] = Field(None, description="Estimated delivery date")
    current_internal_state_id: int = Field(..., description="Internal shipping state ID")


# Request/Response schemas for API endpoints
class DhlTrackingRequest(BaseModel):
    """Request schema for DHL tracking"""
    tracking_numbers: List[str] = Field(..., description="List of tracking numbers to track")
    carrier_api_id: int = Field(..., description="Carrier API ID for authentication")


class DhlTrackingResponse(BaseModel):
    """Response schema for DHL tracking"""
    tracking_data: List[NormalizedTrackingResponseSchema] = Field(..., description="Normalized tracking data")
