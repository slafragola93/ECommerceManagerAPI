from typing import Optional
from pydantic import BaseModel


class MessageSchema(BaseModel):
    message: str
    id_user: Optional[int] = None


class MessageResponseSchema(BaseModel):
    id_message: int
    id_user: int | None
    message: str


class AllMessagesResponseSchema(BaseModel):
    messages: list[MessageResponseSchema]
    total: int
    page: int
    limit: int


class CurrentMessagesResponseSchema(BaseModel):
    messages: list[MessageResponseSchema]
    total: int


class ConfigDict:
    from_attributes = True
