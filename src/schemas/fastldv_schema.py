"""
Schemi Pydantic per integrazione FastLDV (magazzino).
"""
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


FastLdvSeverity = Literal["ok", "warning", "error"]
FastLdvValidationCode = Literal[
    "OK",
    "LABEL_ALREADY_PRINTED",
    "ORDER_CANCELED",
    "ORDER_LOCKED",
    "ORDER_NOT_PAID",
    "ORDER_NOT_READY",
    "ORDER_ALREADY_SHIPPED",
    "BYPASS",
]


class FastLdvCarrierSchema(BaseModel):
    id_carrier_api: int
    name: str
    layout_type: str = "zebra"


class FastLdvShippingSchema(BaseModel):
    colli: int = 1
    peso: float = 0.0
    contrassegno: str = "0.00"
    tracking: str = ""
    country_iso: str = "IT"


class FastLdvDocumentSchema(BaseModel):
    num_doc: str


class FastLdvLineSchema(BaseModel):
    quantity: int
    sku: str = ""
    name: str = ""


class FastLdvValidationSchema(BaseModel):
    printable: bool
    severity: FastLdvSeverity
    code: FastLdvValidationCode
    message: str


class FastLdvLegacySchema(BaseModel):
    id_doc: int
    corrieri_id_carrier: int
    corrieri_carrier: str
    corrieri_tracking: str
    corrieri_layout_type: str
    intDoc: dict


class FastLdvOrderDataSchema(BaseModel):
    id_origin: int  # orders.id_origin (0 se ordine gestionale; non sostituito con id_order)
    id_order: int
    carrier: FastLdvCarrierSchema
    shipping: FastLdvShippingSchema
    document: FastLdvDocumentSchema
    lines: List[FastLdvLineSchema]
    validation: FastLdvValidationSchema
    legacy: Optional[FastLdvLegacySchema] = None


class FastLdvOrderSuccessResponseSchema(BaseModel):
    status: Literal["success"] = "success"
    data: FastLdvOrderDataSchema


class FastLdvOrderErrorResponseSchema(BaseModel):
    status: Literal["error"] = "error"
    error_code: str
    message: str
    data: FastLdvOrderDataSchema


class FastLdvNotifyPrintRequestSchema(BaseModel):
    id_origin: int = Field(
        ...,
        gt=0,
        description="Codice scansione: id_origin PrestaShop o id_order se ordine gestionale",
    )
    tracking: str = Field(..., min_length=1)
    colli: Optional[int] = Field(None, ge=1)
    carrier: Optional[str] = None
    operatore: Optional[str] = None
    stampante: Optional[str] = None
    id_store: Optional[int] = Field(None, gt=0)


class FastLdvNotifyPrintResponseSchema(BaseModel):
    status: Literal["success"] = "success"
    message: str = "Tracking aggiornato"
    data: dict
