from pydantic import BaseModel, Field


class LangSchema(BaseModel):
    name: str = Field(..., max_length=20)
    iso_code: str = Field(..., max_length=5)


class LangResponseSchema(BaseModel):
    id_lang: int
    name: str
    iso_code: str


class AllLangsResponseSchema(BaseModel):
    languages: list[LangResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
