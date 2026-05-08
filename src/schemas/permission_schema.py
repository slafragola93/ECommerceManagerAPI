# src/schemas/permission_schema.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


# ── Schema INPUT (PUT) — mantiene "module_name" ─────────────────────
class ModulePermissionSchema(BaseModel):
    """
    Schema di INPUT per il salvataggio di un singolo permesso.
    Usato dai PUT /users/{id}/permissions e /roles/{id}/permissions.

    NOTA: usa "module_name" per coerenza con il contratto di scrittura.
    """
    module_name: str
    can_read:    bool = False
    can_create:  bool = False
    can_update:  bool = False
    can_delete:  bool = False

    class Config:
        from_attributes = True


# ── Schema OUTPUT (GET) — usa "module" ──────────────────────────────
class ModulePermissionResponseSchema(BaseModel):
    """
    Schema di OUTPUT per la lettura dei permessi.
    Usato dai GET /init/permissions, /users/{id}/permissions,
    /roles/{id}/permissions.

    NOTA: il campo Python si chiama "module_name" (compatibile col codice
    interno che costruisce questi oggetti) ma viene serializzato in JSON
    come "module" tramite l'alias Pydantic.
    """
    model_config = ConfigDict(populate_by_name=True)

    module_name: str = Field(..., serialization_alias="module")
    label:       str
    can_read:    bool = False
    can_create:  bool = False
    can_update:  bool = False
    can_delete:  bool = False
    source:      str = 'role'


# ── Schema per la matrice completa di un utente ─────────────────────
class UserPermissionsResponseSchema(BaseModel):
    """
    Matrice completa dei permessi di un utente.
    Restituita da GET /api/v1/users/{id}/permissions
    """
    id_user:     int
    username:    str
    role_name:   str
    role_type:   str
    permissions: list[ModulePermissionResponseSchema]

    class Config:
        from_attributes = True


class SaveUserPermissionsSchema(BaseModel):
    """
    Payload per salvare i permessi di un utente.
    Usato da PUT /api/v1/users/{id}/permissions
    Richiede la password dell'admin per conferma.
    """
    permissions:    list[ModulePermissionSchema]
    admin_password: str


# ── Schema per la matrice di un ruolo ───────────────────────────────
class RolePermissionsResponseSchema(BaseModel):
    """
    Matrice completa dei permessi di un ruolo.
    Restituita da GET /api/v1/roles/{id}/permissions
    """
    id_role:     int
    role_name:   str
    role_type:   str
    permissions: list[ModulePermissionResponseSchema]

    class Config:
        from_attributes = True


class SaveRolePermissionsSchema(BaseModel):
    """
    Payload per salvare i permessi di un ruolo.
    Usato da PUT /api/v1/roles/{id}/permissions
    """
    permissions: list[ModulePermissionSchema]