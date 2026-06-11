"""
Interfaccia servizio FastLDV (magazzino).
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from src.schemas.fastldv_schema import (
    FastLdvNotifyPrintRequestSchema,
    FastLdvNotifyPrintResponseSchema,
    FastLdvOrderDataSchema,
)


class IFastLdvOrderService(ABC):
    """Contratto per lookup ordine e notifica stampa FastLDV."""

    @abstractmethod
    def get_order_context(
        self,
        id_origin: int,
        carrier_query: Optional[str] = None,
        printer: Optional[str] = None,
        id_store: Optional[int] = None,
        skip_log: bool = False,
        include_legacy: bool = True,
    ) -> Tuple[FastLdvOrderDataSchema, bool]:
        """
        Carica ordine per id_origin, costruisce payload e validazione.

        Returns:
            (data, printable) — printable=False → il router risponde 422.
        """
        pass

    @abstractmethod
    def notify_print(
        self, request: FastLdvNotifyPrintRequestSchema
    ) -> FastLdvNotifyPrintResponseSchema:
        """Aggiorna tracking su shipping senza cambiare stato ordine."""
        pass
