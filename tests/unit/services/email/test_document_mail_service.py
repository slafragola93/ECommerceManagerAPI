import pytest

from src.core.exceptions import ValidationException
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.services.email.document_mail_service import DocumentMailService


@pytest.mark.asyncio
async def test_fiscal_return_cannot_send_email(db_session):
    order = Order(id_order=1, id_customer=1, reference="R1")
    db_session.add(order)
    db_session.add(
        FiscalDocument(
            id_order=1,
            document_type="return",
            status="pending",
        )
    )
    db_session.commit()
    service = DocumentMailService(db_session)
    with pytest.raises(ValidationException):
        await service.send_fiscal_document(1)
