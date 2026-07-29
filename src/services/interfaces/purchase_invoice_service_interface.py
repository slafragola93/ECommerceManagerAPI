from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from src.schemas.purchase_invoice_schema import (
    PurchaseInvoiceDetailResponseSchema,
    PurchaseInvoiceListItemSchema,
    PurchaseInvoicePaymentUpdateSchema,
)


class IPurchaseInvoiceService(ABC):
    @abstractmethod
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
        pass

    @abstractmethod
    async def get_invoice(self, invoice_id: int) -> PurchaseInvoiceDetailResponseSchema:
        pass

    @abstractmethod
    async def get_xml_content(self, invoice_id: int) -> Tuple[str, str]:
        """Returns (filename, xml_content)."""
        pass

    @abstractmethod
    async def update_payment(
        self, invoice_id: int, data: PurchaseInvoicePaymentUpdateSchema
    ) -> PurchaseInvoiceDetailResponseSchema:
        pass

    @abstractmethod
    async def sync_pool(self) -> Dict[str, Any]:
        pass
