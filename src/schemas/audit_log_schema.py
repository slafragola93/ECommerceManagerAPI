"""Pydantic schemas for AuditLog (read-only API)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuditLogResponseSchema(BaseModel):
    id_audit_log: int
    timestamp: datetime
    actor_id: Optional[int] = None
    actor_username: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    level: str
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    status: str

    model_config = {"from_attributes": True, "extra": "ignore"}


class AllAuditLogResponseSchema(BaseModel):
    """Envelope lista audit — coerente con status/count/data + paginazione."""

    status: str = "success"
    count: int
    data: List[AuditLogResponseSchema]
    page: int = Field(..., ge=1)
    limit: int = Field(..., ge=1)

    model_config = {"from_attributes": True}
