from pydantic import BaseModel, Field


class TagSchema(BaseModel):
    name: str = Field(..., max_length=100)


class TagResponseSchema(BaseModel):
    id_tag: int
    name: str


class AllTagsResponseSchema(BaseModel):
    tags: list[TagResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
