from pydantic import BaseModel, Field, ConfigDict
from typing import List


class BulkShipmentCreateRequestSchema(BaseModel):
    """Schema per richiesta creazione massiva spedizioni"""
    order_ids: List[int] = Field(
        ...,
        min_items=1,
        description="Lista di ID ordini per cui creare le spedizioni"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_ids": [1, 2, 3, 4, 5]
            }
        }
    )


class BulkShipmentCreateSuccess(BaseModel):
    """Risultato di una creazione spedizione riuscita"""
    order_id: int = Field(..., description="ID dell'ordine")
    awb: str = Field(..., description="Air Waybill number o tracking number")

    model_config = ConfigDict(from_attributes=True, extra='ignore')


class BulkShipmentCreateError(BaseModel):
    """Errore di una creazione spedizione fallita"""
    order_id: int = Field(..., description="ID dell'ordine")
    error_type: str = Field(..., description="Tipo di errore (NOT_FOUND, NO_CARRIER_API, SHIPMENT_ERROR, UNKNOWN_ERROR)")
    error_message: str = Field(..., description="Messaggio di errore dettagliato")

    model_config = ConfigDict(from_attributes=True, extra='ignore')


class BulkShipmentCreateResponseSchema(BaseModel):
    """Schema per risposta creazione massiva spedizioni"""
    successful: List[BulkShipmentCreateSuccess] = Field(
        default_factory=list,
        description="Lista di spedizioni create con successo"
    )
    failed: List[BulkShipmentCreateError] = Field(
        default_factory=list,
        description="Lista di creazioni fallite"
    )
    summary: dict = Field(
        description="Riepilogo operazione: total, successful_count, failed_count"
    )

    model_config = ConfigDict(from_attributes=True, extra='ignore')

