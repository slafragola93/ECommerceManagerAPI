from pydantic import BaseModel, Field


class SectionalSchema(BaseModel):
    name: str = Field(..., max_length=128)


class SectionalResponseSchema(BaseModel):
    id_sectional: int
    name: str


class AllSectionalsResponseSchema(BaseModel):
    sectionals: list[SectionalResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
