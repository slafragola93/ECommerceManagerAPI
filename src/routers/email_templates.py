from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.email_template_schema import (
    EmailPreviewResponseSchema,
    EmailPreviewSchema,
    EmailSendResultSchema,
    EmailSendTestSchema,
    EmailTemplateCreateSchema,
    EmailTemplateListResponseSchema,
    EmailTemplateResponseSchema,
    EmailTemplateTranslationBodySchema,
    EmailTemplateTranslationSchema,
    EmailTemplateUpdateSchema,
    EmailVariableSchema,
)
from src.services.core.wrap import check_authentication
from src.services.email.template_service import EmailTemplateService
from src.services.routers.auth_service import get_current_user, require_permission

router = APIRouter(prefix="/api/v1/email-templates", tags=["Email Templates"])


def get_email_template_service(db: Session = Depends(get_db)) -> EmailTemplateService:
    return EmailTemplateService(db)


@router.get("/", response_model=EmailTemplateListResponseSchema)
@check_authentication
async def list_email_templates(
    purpose: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "read")),
):
    templates = service.list_templates(purpose)
    return {"templates": templates, "total": len(templates)}


@router.get("/variables", response_model=List[EmailVariableSchema])
@check_authentication
async def list_email_variables(
    purpose: str = Query(...),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "read")),
):
    return service.variables(purpose)


@router.get("/{template_id}", response_model=EmailTemplateResponseSchema)
@check_authentication
async def get_email_template(
    template_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "read")),
):
    return service.get_template(template_id)


@router.post("/", response_model=EmailTemplateResponseSchema, status_code=status.HTTP_201_CREATED)
@check_authentication
async def create_email_template(
    payload: EmailTemplateCreateSchema,
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "create")),
):
    return service.create_template(payload)


@router.put("/{template_id}", response_model=EmailTemplateResponseSchema)
@check_authentication
async def update_email_template(
    payload: EmailTemplateUpdateSchema,
    template_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "update")),
):
    return service.update_template(template_id, payload)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
async def delete_email_template(
    template_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "delete")),
):
    service.delete_template(template_id)


@router.put("/{template_id}/translations/{locale}", response_model=EmailTemplateResponseSchema)
@check_authentication
async def upsert_email_template_translation(
    payload: EmailTemplateTranslationBodySchema,
    template_id: int = Path(gt=0),
    locale: str = Path(min_length=2, max_length=10),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "update")),
):
    data = EmailTemplateTranslationSchema(
        locale=locale,
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
    )
    return service.upsert_translation(template_id, data)


@router.post("/{template_id}/preview", response_model=EmailPreviewResponseSchema)
@check_authentication
async def preview_email_template(
    payload: EmailPreviewSchema,
    template_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "read")),
):
    return service.preview(
        template_id,
        payload.locale,
        payload.context,
        payload.subject,
        payload.body_html,
        payload.body_text,
    )


@router.post("/{template_id}/send-test", response_model=EmailSendResultSchema)
@check_authentication
async def send_test_email_template(
    payload: EmailSendTestSchema,
    template_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    service: EmailTemplateService = Depends(get_email_template_service),
    _: None = Depends(require_permission("settings", "update")),
):
    return await service.send_test(
        template_id,
        payload.to,
        payload.locale,
        payload.context,
        payload.subject,
        payload.body_html,
        payload.body_text,
    )
