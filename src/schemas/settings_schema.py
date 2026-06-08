"""Schema Pydantic per /api/v1/settings/."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdateSchema(BaseModel):
    reverse_charge_id_tax: Optional[int] = Field(
        None,
        description="ID Tax 0% reverse charge VIES (null = non configurato)",
    )

    model_config = ConfigDict(extra="ignore")


class SettingsResponseSchema(BaseModel):
    reverse_charge_id_tax: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
