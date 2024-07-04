from pydantic import BaseModel, Field


class RoleSchema(BaseModel):
    name: str = Field(..., max_length=15)
    permissions: str = Field(max_length=4, default='R', pattern=r'^[CRUD]{1,4}$')


class RoleResponseSchema(BaseModel):
    id_role: int
    name: str
    permissions: str


class AllRolesResponseSchema(BaseModel):
    roles: list[RoleResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
    orm_mode = True
