from typing import Optional
from pydantic import BaseModel, Field


class PlatformSchema(BaseModel):
    name: str = Field(..., max_length=200)
    is_default: bool = False


class PlatformResponseSchema(BaseModel):
    id_platform: int
    name: str
    is_default: bool


class AllPlatformsResponseSchema(BaseModel):
    platforms: list[PlatformResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
