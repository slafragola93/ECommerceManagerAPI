from typing import Optional
from pydantic import BaseModel, Field


class PlatformSchema(BaseModel):
    name: str = Field(..., max_length=200)
    url: Optional[str] = None
    api_key: Optional[str] = None


class PlatformResponseSchema(BaseModel):
    id_platform: int
    name: str
    url: str
    api_key: str


class AllPlatformsResponseSchema(BaseModel):
    platforms: list[PlatformResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
