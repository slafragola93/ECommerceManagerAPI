from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.core.exceptions import BusinessRuleException, ErrorCode, NotFoundException, ValidationException
from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.models.ricevuta import Ricevuta
from src.schemas.email_template_schema import EmailSendResultSchema
from src.services.email.sender import EmailSendError, EmailSender
from src.services.email.settings import is_email_enabled, load_email_settings, smtp_ready
from src.services.email.template_service import EmailTemplateService
from src.services.pdf.fiscal_document_pdf_builder import build_fiscal_document_pdf
from src.services.routers.ricevuta_service import RicevutaService

logger = logging.getLogger(__name__)

_FISCAL_PURPOSES = {"invoice": "invoice", "credit_note": "credit_note"}


class DocumentMailService:
    def __init__(self, session: Session):
        self._session = session
        self._templates = EmailTemplateService(session)

    async def send_fiscal_document(
        self,
        id_fiscal_document: int,
        id_email_template: Optional[int] = None,
    ) -> EmailSendResultSchema:
        document = (
            self._session.query(FiscalDocument)
            .filter(FiscalDocument.id_fiscal_document == id_fiscal_document)
            .first()
        )
        if not document:
            raise NotFoundException("FiscalDocument", id_fiscal_document)
        purpose = _FISCAL_PURPOSES.get(document.document_type)
        if not purpose:
            raise ValidationException("Invio email previsto solo per fattura e nota di credito")

        order = self._session.query(Order).filter(Order.id_order == document.id_order).first()
        if not order:
            raise NotFoundException("Order", document.id_order)
        customer = self._customer(order.id_customer)
        context = {
            "firstname": customer.firstname or "",
            "lastname": customer.lastname or "",
            "document_number": document.document_number or document.internal_number or str(document.id_fiscal_document),
            "document_date": document.date_add.strftime("%d/%m/%Y") if document.date_add else "",
            "order_reference": order.reference or "",
            "total": f"{float(document.total_price_with_tax or 0):.2f}",
        }
        pdf_bytes, filename = build_fiscal_document_pdf(self._session, id_fiscal_document)
        return await self._send_and_persist(
            entity=document,
            purpose=purpose,
            customer=customer,
            context=context,
            id_email_template=id_email_template,
            attachments=[(filename, pdf_bytes, "application/pdf")],
        )

    async def send_ricevuta(
        self,
        id_ricevuta: int,
        id_email_template: Optional[int] = None,
        ricevuta_service: Optional[RicevutaService] = None,
    ) -> EmailSendResultSchema:
        ricevuta = self._session.query(Ricevuta).filter(Ricevuta.id_ricevuta == id_ricevuta).first()
        if not ricevuta:
            raise NotFoundException("Ricevuta", id_ricevuta)
        order = self._session.query(Order).filter(Order.id_order == ricevuta.id_order).first()
        if not order:
            raise NotFoundException("Order", ricevuta.id_order)
        customer = self._customer(ricevuta.id_customer or order.id_customer)
        context = {
            "firstname": customer.firstname or "",
            "lastname": customer.lastname or "",
            "document_number": f"{ricevuta.numero}/{ricevuta.anno}",
            "document_date": ricevuta.data_emissione.strftime("%d/%m/%Y") if ricevuta.data_emissione else "",
            "order_reference": order.reference or "",
            "total": f"{float(getattr(order, 'total_price_with_tax', 0) or 0):.2f}",
        }
        if ricevuta_service is None:
            raise ValidationException("RicevutaService richiesto per generare il PDF")
        pdf_bytes = ricevuta_service.get_ricevuta_pdf_bytes(id_ricevuta)
        filename = f"ricevuta-{ricevuta.numero}-{ricevuta.anno}.pdf"
        return await self._send_and_persist(
            entity=ricevuta,
            purpose="receipt",
            customer=customer,
            context=context,
            id_email_template=id_email_template,
            attachments=[(filename, pdf_bytes, "application/pdf")],
        )

    async def send_order_shipped(self, order_id: int) -> EmailSendResultSchema:
        from src.models.carrier import Carrier
        from src.models.shipping import Shipping

        order = self._session.query(Order).filter(Order.id_order == order_id).first()
        if not order:
            raise NotFoundException("Order", order_id)
        customer = self._customer(order.id_customer)
        tracking = ""
        carrier_name = ""
        if order.id_shipping:
            shipping = self._session.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
            if shipping and shipping.tracking:
                tracking = shipping.tracking
        if order.id_carrier:
            carrier = self._session.query(Carrier).filter(Carrier.id_carrier == order.id_carrier).first()
            if carrier and carrier.name:
                carrier_name = carrier.name
        context = {
            "firstname": customer.firstname or "",
            "lastname": customer.lastname or "",
            "reference": order.reference or "",
            "tracking": tracking,
            "carrier_name": carrier_name,
        }
        return await self._send_and_persist(
            entity=None,
            purpose="order_shipped",
            customer=customer,
            context=context,
            persist_status=False,
        )

    def _customer(self, id_customer: Optional[int]) -> Customer:
        if not id_customer:
            raise BusinessRuleException(
                "Ordine senza cliente",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {},
            )
        customer = self._session.query(Customer).filter(Customer.id_customer == id_customer).first()
        if not customer:
            raise NotFoundException("Customer", id_customer)
        if not customer.email:
            raise BusinessRuleException(
                "Cliente senza email",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"id_customer": id_customer},
            )
        return customer

    async def _send_and_persist(
        self,
        *,
        entity: Any,
        purpose: str,
        customer: Customer,
        context: Dict[str, Any],
        id_email_template: Optional[int] = None,
        attachments: Optional[list] = None,
        persist_status: bool = True,
    ) -> EmailSendResultSchema:
        settings = load_email_settings(self._session)
        if persist_status and entity is not None:
            entity.mail_status = "pending"
            entity.mail_error_message = None
            self._session.commit()

        if not is_email_enabled(settings) or not smtp_ready(settings):
            message = "SMTP disabilitato o incompleto"
            if persist_status and entity is not None:
                entity.mail_status = "error"
                entity.mail_error_message = message
                self._session.commit()
            return EmailSendResultSchema(success=False, mail_status="error", mail_error_message=message)

        template = (
            self._templates.get_template_entity(id_email_template)
            if id_email_template
            else self._templates.get_default_template(purpose)
        )
        if template.purpose != purpose:
            raise ValidationException("Il template non è valido per questo documento")
        if not template.is_active:
            raise ValidationException("Template non attivo")

        preferred = self._templates.locale_from_customer_lang(customer.id_lang)
        translation, locale = self._templates.resolve_translation(template, preferred)
        rendered = self._templates.render(template, translation, context)

        try:
            await EmailSender(settings).send(
                to=customer.email,
                subject=rendered.subject,
                body_html=rendered.body_html,
                body_text=rendered.body_text,
                attachments=attachments or [],
            )
        except EmailSendError as exc:
            message = str(exc)[:255]
            if persist_status and entity is not None:
                entity.mail_status = "error"
                entity.mail_error_message = message
                self._session.commit()
            return EmailSendResultSchema(
                success=False,
                mail_status="error",
                mail_error_message=message,
                locale=locale,
                id_email_template=template.id_email_template,
            )

        if persist_status and entity is not None:
            entity.mail_status = "sent"
            entity.mail_error_message = None
            self._session.commit()
        return EmailSendResultSchema(
            success=True,
            mail_status="sent",
            locale=locale,
            id_email_template=template.id_email_template,
        )
