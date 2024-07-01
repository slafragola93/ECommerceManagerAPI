from pydantic import BaseModel, Field


class ConfigurationSchema(BaseModel):
    id_lang: int = Field(default=0)
    name: str = Field(..., max_length=50)
    value: str = Field(..., max_length=50)

class ConfigurationResponseSchema(BaseModel):
    id_configuration: int
    id_lang: int
    name: str
    value: str


class AllConfigurationsResponseSchema(BaseModel):
    configurations: list[ConfigurationResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
