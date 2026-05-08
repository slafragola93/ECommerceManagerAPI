from pydantic import BaseModel, Field
from typing import Optional
from src.models.role import PermissionType


class RoleSchema(BaseModel):
    """Schema per creazione e aggiornamento ruolo"""
    name:            str = Field(..., max_length=50)
    description:     Optional[str] = Field(None, max_length=255)
    permission_type: PermissionType = PermissionType.custom

    class Config:
        from_attributes = True
        use_enum_values = True


class RoleResponseSchema(BaseModel):
    """Schema risposta singolo ruolo"""
    id_role:         int
    name:            str
    description:     Optional[str] = None
    permission_type: str
    is_system:       bool

    class Config:
        from_attributes = True


class AllRolesResponseSchema(BaseModel):
    """Schema risposta lista ruoli"""
    roles: list[RoleResponseSchema]
    total: int
    page:  int
    limit: int

    class Config:
        from_attributes = True