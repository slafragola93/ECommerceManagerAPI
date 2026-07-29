from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundException, ValidationException
from src.models.payment import Payment
from src.models.purchase_invoice_sync import PurchaseInvoiceSync
from src.repository.purchase_invoice_sync_repository import PurchaseInvoiceSyncRepository
from src.schemas.purchase_invoice_schema import (
    PurchaseInvoiceDetailResponseSchema,
    PurchaseInvoiceDetailSchema,
    PurchaseInvoiceListItemSchema,
    PurchaseInvoicePaymentUpdateSchema,
)
from src.services.interfaces.purchase_invoice_service_interface import (
    IPurchaseInvoiceService,
)
from src.services.sync.fatturapa_pool_sync_service import FatturaPAPoolSyncService


class PurchaseInvoiceService(IPurchaseInvoiceService):
    def __init__(
        self,
        db: Session,
        repository: Optional[PurchaseInvoiceSyncRepository] = None,
    ):
        self.db = db
        self._repository = repository or PurchaseInvoiceSyncRepository(db)

    def _to_list_item(
        self, invoice: PurchaseInvoiceSync
    ) -> PurchaseInvoiceListItemSchema:
        payment_name = None
        if invoice.payment is not None:
            payment_name = invoice.payment.name
        return PurchaseInvoiceListItemSchema(
            id=invoice.id,
            identificativo_sdi=invoice.identificativo_sdi,
            nome_file=invoice.nome_file,
            tipo_documento=invoice.tipo_documento,
            numero_documento=invoice.numero_documento,
            data_documento=invoice.data_documento,
            fornitore_denominazione=invoice.fornitore_denominazione,
            fornitore_piva=invoice.fornitore_piva,
            importo_totale=invoice.importo_totale,
            fattura_collegata_numero=invoice.fattura_collegata_numero,
            fattura_collegata_data=invoice.fattura_collegata_data,
            is_paid=bool(invoice.is_paid),
            id_payment=invoice.id_payment,
            payment_name=payment_name,
            paid_at=invoice.paid_at,
            direzione=invoice.direzione,
            tipo=invoice.tipo,
            created_at=invoice.created_at,
        )

    def _to_detail(
        self, invoice: PurchaseInvoiceSync
    ) -> PurchaseInvoiceDetailResponseSchema:
        base = self._to_list_item(invoice)
        details = [
            PurchaseInvoiceDetailSchema.model_validate(line)
            for line in (invoice.details or [])
        ]
        return PurchaseInvoiceDetailResponseSchema(
            **base.model_dump(),
            note=invoice.note,
            blob_uri=invoice.blob_uri,
            file_path=invoice.file_path,
            details=details,
        )

    async def list_invoices(
        self,
        page: int = 1,
        limit: int = 20,
        *,
        is_paid: Optional[bool] = None,
        tipo_documento: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        q: Optional[str] = None,
    ) -> Tuple[List[PurchaseInvoiceListItemSchema], int]:
        items = self._repository.list_filtered(
            page=page,
            limit=limit,
            is_paid=is_paid,
            tipo_documento=tipo_documento,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        total = self._repository.count_filtered(
            is_paid=is_paid,
            tipo_documento=tipo_documento,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        return [self._to_list_item(i) for i in items], total

    async def get_invoice(self, invoice_id: int) -> PurchaseInvoiceDetailResponseSchema:
        invoice = self._repository.get_by_id(invoice_id, with_details=True)
        if not invoice:
            raise NotFoundException("PurchaseInvoice", invoice_id)
        return self._to_detail(invoice)

    async def get_xml_content(self, invoice_id: int) -> Tuple[str, str]:
        invoice = self._repository.get_by_id(invoice_id)
        if not invoice:
            raise NotFoundException("PurchaseInvoice", invoice_id)
        if not invoice.xml_content:
            raise NotFoundException("PurchaseInvoiceXML", invoice_id)
        filename = invoice.nome_file or f"purchase-invoice-{invoice_id}.xml"
        return filename, invoice.xml_content

    async def update_payment(
        self, invoice_id: int, data: PurchaseInvoicePaymentUpdateSchema
    ) -> PurchaseInvoiceDetailResponseSchema:
        invoice = self._repository.get_by_id(invoice_id, with_details=True)
        if not invoice:
            raise NotFoundException("PurchaseInvoice", invoice_id)

        if data.is_paid:
            if not data.id_payment:
                raise ValidationException(
                    "id_payment è obbligatorio quando is_paid=true",
                    details={"field": "id_payment"},
                )
            payment = (
                self.db.query(Payment)
                .filter(Payment.id_payment == data.id_payment)
                .first()
            )
            if not payment:
                raise NotFoundException("Payment", data.id_payment)
            self._repository.update_payment(
                invoice,
                is_paid=True,
                id_payment=data.id_payment,
                paid_at=datetime.utcnow(),
            )
        else:
            self._repository.update_payment(
                invoice,
                is_paid=False,
                id_payment=None,
                paid_at=None,
            )

        invoice = self._repository.get_by_id(invoice_id, with_details=True)
        return self._to_detail(invoice)

    async def sync_pool(self) -> Dict[str, Any]:
        try:
            sync_service = FatturaPAPoolSyncService(self.db)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc
        return await sync_service.sync_pool()
