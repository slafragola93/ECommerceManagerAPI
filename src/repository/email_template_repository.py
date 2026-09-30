from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.models.email_template import EmailTemplate, EmailTemplateTranslation


class EmailTemplateRepository(BaseRepository[EmailTemplate, int]):
    def __init__(self, session: Session):
        super().__init__(session, EmailTemplate)

    def get_by_id(self, id: int) -> Optional[EmailTemplate]:
        try:
            return (
                self._session.query(EmailTemplate)
                .options(joinedload(EmailTemplate.translations))
                .filter(EmailTemplate.id_email_template == id)
                .first()
            )
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving email template: {str(e)}")

    def get_by_code(self, code: str) -> Optional[EmailTemplate]:
        return (
            self._session.query(EmailTemplate)
            .options(joinedload(EmailTemplate.translations))
            .filter(EmailTemplate.code == code)
            .first()
        )

    def list_templates(self, purpose: Optional[str] = None) -> List[EmailTemplate]:
        query = self._session.query(EmailTemplate).options(joinedload(EmailTemplate.translations))
        if purpose:
            query = query.filter(EmailTemplate.purpose == purpose)
        return query.order_by(EmailTemplate.id_email_template.desc()).all()

    def get_default_for_purpose(self, purpose: str) -> Optional[EmailTemplate]:
        return (
            self._session.query(EmailTemplate)
            .options(joinedload(EmailTemplate.translations))
            .filter(
                EmailTemplate.purpose == purpose,
                EmailTemplate.is_default.is_(True),
                EmailTemplate.is_active.is_(True),
            )
            .first()
        )

    def clear_default_for_purpose(self, purpose: str, except_id: Optional[int] = None) -> None:
        query = self._session.query(EmailTemplate).filter(
            EmailTemplate.purpose == purpose,
            EmailTemplate.is_default.is_(True),
        )
        if except_id is not None:
            query = query.filter(EmailTemplate.id_email_template != except_id)
        query.update({"is_default": False}, synchronize_session=False)

    def upsert_translation(self, template: EmailTemplate, locale: str, subject: str, body_html: str, body_text: Optional[str]) -> EmailTemplateTranslation:
        existing = next((item for item in template.translations if item.locale == locale), None)
        if existing:
            existing.subject = subject
            existing.body_html = body_html
            existing.body_text = body_text
            self._session.commit()
            self._session.refresh(existing)
            return existing
        translation = EmailTemplateTranslation(
            id_email_template=template.id_email_template,
            locale=locale,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )
        self._session.add(translation)
        self._session.commit()
        self._session.refresh(translation)
        return translation
