from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_sdi_notification import FiscalDocumentSdiNotification


class FiscalDocumentSdiNotificationRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_by_document(
        self, id_fiscal_document: int
    ) -> List[FiscalDocumentSdiNotification]:
        return (
            self._session.query(FiscalDocumentSdiNotification)
            .filter(
                FiscalDocumentSdiNotification.id_fiscal_document == id_fiscal_document
            )
            .order_by(FiscalDocumentSdiNotification.date_add.asc())
            .all()
        )

    def exists(
        self,
        id_fiscal_document: int,
        notification_type: str,
        nome_file: Optional[str],
    ) -> bool:
        query = self._session.query(FiscalDocumentSdiNotification).filter(
            FiscalDocumentSdiNotification.id_fiscal_document == id_fiscal_document,
            FiscalDocumentSdiNotification.notification_type == notification_type,
        )
        if nome_file:
            query = query.filter(FiscalDocumentSdiNotification.nome_file == nome_file)
        return query.first() is not None

    def find_document_by_progressivo(
        self, progressivo_invio: str
    ) -> Optional[FiscalDocument]:
        return (
            self._session.query(FiscalDocument)
            .filter(
                FiscalDocument.is_electronic.is_(True),
                FiscalDocument.progressivo_invio == progressivo_invio,
            )
            .first()
        )

    def create(self, **kwargs) -> FiscalDocumentSdiNotification:
        row = FiscalDocumentSdiNotification(**kwargs)
        self._session.add(row)
        self._session.flush()
        return row

    def update_document_sdi(
        self,
        doc: FiscalDocument,
        *,
        sdi_status: Optional[str],
        identificativo_sdi: Optional[str],
    ) -> None:
        if sdi_status:
            doc.sdi_status = sdi_status
        if identificativo_sdi and not doc.identificativo_sdi:
            doc.identificativo_sdi = identificativo_sdi
        self._session.flush()
