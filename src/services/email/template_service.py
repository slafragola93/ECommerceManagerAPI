from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.exceptions import BusinessRuleException, ErrorCode, NotFoundException, ValidationException
from src.models.email_template import EMAIL_PURPOSES, EmailTemplate, EmailTemplateTranslation
from src.models.lang import Lang
from src.repository.email_template_repository import EmailTemplateRepository
from src.schemas.email_template_schema import (
    EmailPreviewResponseSchema,
    EmailSendResultSchema,
    EmailTemplateCreateSchema,
    EmailTemplateResponseSchema,
    EmailTemplateTranslationResponseSchema,
    EmailTemplateTranslationSchema,
    EmailTemplateUpdateSchema,
)
from src.services.email.renderer import render_template_string
from src.services.email.sender import EmailSendError, EmailSender
from src.services.email.settings import default_locale, is_email_enabled, load_email_settings, smtp_ready
from src.services.email.variables import PURPOSE_VARIABLES, keys_for_purpose

logger = logging.getLogger(__name__)


class EmailTemplateService:
    def __init__(self, session: Session):
        self._session = session
        self._repo = EmailTemplateRepository(session)

    def list_templates(self, purpose: Optional[str] = None) -> List[EmailTemplateResponseSchema]:
        if purpose and purpose not in EMAIL_PURPOSES:
            raise ValidationException("purpose non valido")
        return [self._to_response(item) for item in self._repo.list_templates(purpose)]

    def get_template(self, template_id: int) -> EmailTemplateResponseSchema:
        return self._to_response(self._require(template_id))

    def create_template(self, data: EmailTemplateCreateSchema) -> EmailTemplateResponseSchema:
        if self._repo.get_by_code(data.code):
            raise BusinessRuleException(
                f"Template con code '{data.code}' già esistente",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"code": data.code},
            )
        allowed = keys_for_purpose(data.purpose)
        if data.is_default:
            self._repo.clear_default_for_purpose(data.purpose)
        template = EmailTemplate(
            code=data.code,
            name=data.name,
            purpose=data.purpose,
            is_default=data.is_default,
            is_active=data.is_active,
            allowed_variables=json.dumps(allowed),
        )
        created = self._repo.create(template)
        for translation in data.translations:
            self._repo.upsert_translation(
                created,
                translation.locale,
                translation.subject,
                translation.body_html,
                translation.body_text,
            )
        return self._to_response(self._require(created.id_email_template))

    def update_template(self, template_id: int, data: EmailTemplateUpdateSchema) -> EmailTemplateResponseSchema:
        template = self._require(template_id)
        payload = data.model_dump(
            exclude_unset=True,
            exclude={"translations", "locale", "subject", "body_html", "body_text"},
        )
        if payload.get("is_default") is True:
            self._repo.clear_default_for_purpose(template.purpose, except_id=template_id)
        for field, value in payload.items():
            setattr(template, field, value)
        self._repo.update(template)
        if data.translations:
            for translation in data.translations:
                if not translation.subject and not translation.body_html:
                    continue
                self._repo.upsert_translation(
                    template,
                    translation.locale,
                    translation.subject,
                    translation.body_html,
                    translation.body_text,
                )
        if data.subject is not None or data.body_html is not None:
            self._repo.upsert_translation(
                template,
                data.locale or "it",
                data.subject or "",
                data.body_html or "",
                data.body_text,
            )
        return self._to_response(self._require(template_id))

    def delete_template(self, template_id: int) -> None:
        self._require(template_id)
        self._repo.delete(template_id)

    def upsert_translation(self, template_id: int, data: EmailTemplateTranslationSchema) -> EmailTemplateResponseSchema:
        template = self._require(template_id)
        self._repo.upsert_translation(template, data.locale, data.subject, data.body_html, data.body_text)
        return self._to_response(self._require(template_id))

    def variables(self, purpose: str) -> List[Dict[str, str]]:
        if purpose not in EMAIL_PURPOSES:
            raise ValidationException("purpose non valido")
        return PURPOSE_VARIABLES[purpose]

    def preview(
        self,
        template_id: int,
        locale: str,
        context: Dict[str, Any],
        subject: Optional[str] = None,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
    ) -> EmailPreviewResponseSchema:
        template = self._require(template_id)
        allowed = self._allowed(template)
        resolved_locale = (locale or "it").strip().lower()
        source_subject = subject
        source_html = body_html
        source_text = body_text
        if source_subject is None and source_html is None:
            try:
                translation, resolved_locale = self.resolve_translation(template, locale)
                source_subject = translation.subject
                source_html = translation.body_html
                source_text = translation.body_text
            except NotFoundException:
                source_subject = ""
                source_html = ""
                source_text = ""
        return EmailPreviewResponseSchema(
            locale=resolved_locale,
            subject=render_template_string(source_subject or "", context, allowed),
            body_html=render_template_string(source_html or "", context, allowed),
            body_text=render_template_string(source_text or "", context, allowed) or None,
        )

    async def send_test(
        self,
        template_id: int,
        to: str,
        locale: str,
        context: Dict[str, Any],
        subject: Optional[str] = None,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
    ) -> EmailSendResultSchema:
        settings = load_email_settings(self._session)
        if not is_email_enabled(settings) or not smtp_ready(settings):
            raise BusinessRuleException(
                "SMTP disabilitato o incompleto",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"enabled": is_email_enabled(settings)},
            )
        preview = self.preview(template_id, locale, context, subject, body_html, body_text)
        try:
            await EmailSender(settings).send(
                to=to,
                subject=preview.subject,
                body_html=preview.body_html,
                body_text=preview.body_text,
            )
        except EmailSendError as exc:
            return EmailSendResultSchema(success=False, mail_status="error", mail_error_message=str(exc)[:255])
        return EmailSendResultSchema(
            success=True,
            mail_status="sent",
            locale=preview.locale,
            id_email_template=template_id,
        )

    def get_default_template(self, purpose: str) -> EmailTemplate:
        template = self._repo.get_default_for_purpose(purpose)
        if not template:
            raise NotFoundException("EmailTemplate", None, {"purpose": purpose, "is_default": True})
        return template

    def get_template_entity(self, template_id: int) -> EmailTemplate:
        return self._require(template_id)

    def resolve_translation(
        self,
        template: EmailTemplate,
        preferred_locale: Optional[str],
    ) -> Tuple[EmailTemplateTranslation, str]:
        settings = load_email_settings(self._session)
        fallback = default_locale(settings)
        preferred = (preferred_locale or fallback).lower()
        by_locale = {item.locale.lower(): item for item in template.translations}
        for candidate in (preferred, fallback, "en", "it"):
            if candidate in by_locale:
                return by_locale[candidate], candidate
        if template.translations:
            first = template.translations[0]
            return first, first.locale
        raise NotFoundException("EmailTemplateTranslation", None, {"id_email_template": template.id_email_template})

    def locale_from_customer_lang(self, id_lang: Optional[int]) -> Optional[str]:
        if not id_lang:
            return None
        lang = self._session.query(Lang).filter(Lang.id_lang == id_lang).first()
        if not lang or not lang.iso_code:
            return None
        return str(lang.iso_code).strip().lower()

    def render(self, template: EmailTemplate, translation: EmailTemplateTranslation, context: Dict[str, Any]) -> EmailPreviewResponseSchema:
        allowed = self._allowed(template)
        return EmailPreviewResponseSchema(
            locale=translation.locale,
            subject=render_template_string(translation.subject, context, allowed),
            body_html=render_template_string(translation.body_html, context, allowed),
            body_text=render_template_string(translation.body_text or "", context, allowed) or None,
        )

    def _require(self, template_id: int) -> EmailTemplate:
        template = self._repo.get_by_id(template_id)
        if not template:
            raise NotFoundException("EmailTemplate", template_id)
        return template

    def _allowed(self, template: EmailTemplate) -> List[str]:
        if template.allowed_variables:
            try:
                parsed = json.loads(template.allowed_variables)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return keys_for_purpose(template.purpose)

    def _primary_translation(self, template: EmailTemplate) -> Optional[EmailTemplateTranslation]:
        if not template.translations:
            return None
        by_locale = {item.locale.lower(): item for item in template.translations}
        return by_locale.get("it") or by_locale.get("en") or template.translations[0]

    def _to_response(self, template: EmailTemplate) -> EmailTemplateResponseSchema:
        primary = self._primary_translation(template)
        return EmailTemplateResponseSchema(
            id_email_template=template.id_email_template,
            id=template.id_email_template,
            code=template.code,
            name=template.name,
            purpose=template.purpose,
            is_default=bool(template.is_default),
            is_active=bool(template.is_active),
            locale=primary.locale if primary else None,
            subject=primary.subject if primary else None,
            body_html=primary.body_html if primary else None,
            body_text=primary.body_text if primary else None,
            allowed_variables=self._allowed(template),
            translations=[
                EmailTemplateTranslationResponseSchema(
                    locale=item.locale,
                    subject=item.subject,
                    body_html=item.body_html,
                    body_text=item.body_text,
                )
                for item in template.translations
            ],
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
