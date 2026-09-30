from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.email_template import EMAIL_PURPOSES, SUPPORTED_LOCALES


class EmailTemplateTranslationSchema(BaseModel):
    locale: str = Field(..., min_length=2, max_length=10)
    subject: str = Field(..., min_length=1, max_length=255)
    body_html: str = Field(..., min_length=1)
    body_text: Optional[str] = None

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        locale = value.strip().lower()
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(f"locale deve essere uno di: {', '.join(SUPPORTED_LOCALES)}")
        return locale


class EmailTemplateTranslationBodySchema(BaseModel):
    """Body di PUT /translations/{locale}: il locale sta nel path."""

    subject: str = Field(..., min_length=1, max_length=255)
    body_html: str = Field(..., min_length=1)
    body_text: Optional[str] = None
    locale: Optional[str] = Field(None, min_length=2, max_length=10)


class EmailTemplateCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=200)
    purpose: str
    is_default: bool = False
    is_active: bool = True
    translations: List[EmailTemplateTranslationSchema] = Field(default_factory=list)

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: str) -> str:
        purpose = value.strip().lower()
        if purpose not in EMAIL_PURPOSES:
            raise ValueError(f"purpose deve essere uno di: {', '.join(EMAIL_PURPOSES)}")
        return purpose

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip()


class EmailTemplateUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    locale: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    translations: Optional[List[EmailTemplateTranslationSchema]] = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("locale")
    @classmethod
    def validate_optional_locale(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        locale = value.strip().lower()
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(f"locale deve essere uno di: {', '.join(SUPPORTED_LOCALES)}")
        return locale

    @field_validator("translations", mode="before")
    @classmethod
    def normalize_translations(cls, value):
        if value is None:
            return None
        if isinstance(value, dict):
            items = []
            for loc, payload in value.items():
                if not isinstance(payload, dict):
                    continue
                items.append(
                    {
                        "locale": loc,
                        "subject": payload.get("subject") or "",
                        "body_html": payload.get("body_html") or "",
                        "body_text": payload.get("body_text"),
                    }
                )
            return [item for item in items if item["subject"] or item["body_html"]]
        return value


class EmailTemplateTranslationResponseSchema(BaseModel):
    locale: str
    subject: str
    body_html: str
    body_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EmailTemplateResponseSchema(BaseModel):
    id_email_template: int
    id: int = Field(..., description="Alias di id_email_template per il FE")
    code: str
    name: str
    purpose: str
    is_default: bool
    is_active: bool
    locale: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    allowed_variables: List[str] = Field(default_factory=list)
    translations: List[EmailTemplateTranslationResponseSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmailTemplateListResponseSchema(BaseModel):
    templates: List[EmailTemplateResponseSchema]
    total: int


class EmailVariableSchema(BaseModel):
    key: str
    description: str


class EmailPreviewSchema(BaseModel):
    locale: str
    context: Dict[str, Any] = Field(default_factory=dict)
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None


class EmailPreviewResponseSchema(BaseModel):
    locale: str
    subject: str
    body_html: str
    body_text: Optional[str] = None


class EmailSendTestSchema(BaseModel):
    to: str = Field(..., min_length=3)
    locale: str
    context: Dict[str, Any] = Field(default_factory=dict)
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None


class EmailSendDocumentSchema(BaseModel):
    id_email_template: Optional[int] = Field(None, gt=0)


class EmailSendResultSchema(BaseModel):
    success: bool
    mail_status: Optional[str] = None
    mail_error_message: Optional[str] = None
    locale: Optional[str] = None
    id_email_template: Optional[int] = None
