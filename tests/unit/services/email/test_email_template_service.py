import pytest

from src.core.exceptions import BusinessRuleException
from src.models.app_configuration import AppConfiguration
from src.models.lang import Lang
from src.schemas.email_template_schema import (
    EmailTemplateCreateSchema,
    EmailTemplateTranslationSchema,
    EmailTemplateUpdateSchema,
)
from src.services.email.template_service import EmailTemplateService


def _enable_locale(db_session, locale="en"):
    db_session.add(
        AppConfiguration(
            category="email_settings",
            name="default_locale",
            value=locale,
        )
    )
    db_session.commit()


def test_create_and_preview_template(db_session):
    _enable_locale(db_session)
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(
            code="order_shipped_default",
            name="Ordine spedito",
            purpose="order_shipped",
            is_default=True,
            translations=[
                EmailTemplateTranslationSchema(
                    locale="it",
                    subject="Ordine {{ reference }} spedito",
                    body_html="<p>Ciao {{ firstname }} tracking {{ tracking }}</p>",
                )
            ],
        )
    )
    assert created.purpose == "order_shipped"
    assert created.id == created.id_email_template
    assert "firstname" in created.allowed_variables

    preview = service.preview(
        created.id_email_template,
        "it",
        {"firstname": "Anna", "reference": "R1", "tracking": "TRK"},
    )
    assert "Anna" in preview.body_html
    assert "R1" in preview.subject
    assert "TRK" in preview.body_html


def test_locale_fallback_to_default(db_session):
    _enable_locale(db_session, "en")
    db_session.add(Lang(id_lang=1, name="Italiano", iso_code="it"))
    db_session.commit()
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(
            code="invoice_default",
            name="Fattura",
            purpose="invoice",
            is_default=True,
            translations=[
                EmailTemplateTranslationSchema(
                    locale="en",
                    subject="Invoice {{ document_number }}",
                    body_html="<p>Hello {{ firstname }}</p>",
                )
            ],
        )
    )
    preview = service.preview(created.id_email_template, "fr", {"firstname": "Luc", "document_number": "12"})
    assert preview.locale == "en"
    assert "Hello Luc" in preview.body_html


@pytest.mark.asyncio
async def test_smtp_off_send_test_raises(db_session):
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(
            code="receipt_default",
            name="Ricevuta",
            purpose="receipt",
            translations=[
                EmailTemplateTranslationSchema(
                    locale="it",
                    subject="Ricevuta",
                    body_html="<p>ok</p>",
                )
            ],
        )
    )
    with pytest.raises(BusinessRuleException):
        await service.send_test(created.id_email_template, "a@b.c", "it", {})


def test_preview_without_translation_returns_empty(db_session):
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(code="empty_preview", name="Vuoto", purpose="invoice")
    )
    preview = service.preview(created.id_email_template, "it", {})
    assert preview.locale == "it"
    assert preview.subject == ""
    assert preview.body_html == ""


def test_preview_uses_draft_when_no_translation(db_session):
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(code="draft_preview", name="Bozza", purpose="invoice")
    )
    preview = service.preview(
        created.id_email_template,
        "it",
        {"firstname": "Ada"},
        subject="Ciao {{ firstname }}",
        body_html="<p>{{ firstname }}</p>",
    )
    assert preview.subject == "Ciao Ada"
    assert "Ada" in preview.body_html


def test_update_persists_top_level_subject_body(db_session):
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(code="flat_save", name="Piatto", purpose="invoice")
    )
    updated = service.update_template(
        created.id_email_template,
        EmailTemplateUpdateSchema(locale="it", subject="Oggetto {{ firstname }}", body_html="<p>Ciao</p>"),
    )
    assert updated.subject == "Oggetto {{ firstname }}"
    assert updated.body_html == "<p>Ciao</p>"
    assert updated.locale == "it"
    assert updated.translations[0].subject == "Oggetto {{ firstname }}"


def test_update_persists_translations(db_session):
    _enable_locale(db_session)
    service = EmailTemplateService(db_session)
    created = service.create_template(
        EmailTemplateCreateSchema(code="upd_tr", name="Aggiorna", purpose="receipt")
    )
    service.update_template(
        created.id_email_template,
        EmailTemplateUpdateSchema(
            translations=[
                EmailTemplateTranslationSchema(
                    locale="it",
                    subject="Ricevuta {{ document_number }}",
                    body_html="<p>Ciao {{ firstname }}</p>",
                )
            ]
        ),
    )
    preview = service.preview(created.id_email_template, "it", {"firstname": "Eva", "document_number": "9"})
    assert "9" in preview.subject
    assert "Eva" in preview.body_html
