"""Interfaccia service ricevute."""
from abc import ABC, abstractmethod
from typing import Optional

from src.schemas.ricevuta_schema import (
    RicevutaCreateSchema,
    RicevutaFiltersSchema,
    RicevutaListResponseSchema,
    RicevutaResponseSchema,
    RicevutaUpdateSchema,
)


class IRicevutaService(ABC):
    @abstractmethod
    def get_ricevuta(self, id_ricevuta: int) -> RicevutaResponseSchema:
        pass

    @abstractmethod
    def list_ricevute(self, filters: RicevutaFiltersSchema) -> RicevutaListResponseSchema:
        pass

    @abstractmethod
    def create_ricevuta(
        self, data: RicevutaCreateSchema, user_id: Optional[int] = None
    ) -> RicevutaResponseSchema:
        pass

    @abstractmethod
    def update_ricevuta(
        self,
        id_ricevuta: int,
        data: RicevutaUpdateSchema,
        user_id: Optional[int] = None,
    ) -> RicevutaResponseSchema:
        pass

    @abstractmethod
    def annulla_ricevuta(
        self, id_ricevuta: int, user_id: Optional[int] = None
    ) -> RicevutaResponseSchema:
        pass

    @abstractmethod
    def regenerate_pdf(self, id_ricevuta: int) -> bytes:
        pass

    @abstractmethod
    def get_ricevuta_pdf_bytes(
        self, id_ricevuta: int, *, regenerate: bool = False
    ) -> bytes:
        pass

    @abstractmethod
    def export_ricevuta(self, id_ricevuta: int, fmt: str) -> tuple[bytes, str, str]:
        """Restituisce (content, media_type, filename)."""
        pass

    @abstractmethod
    def export_ricevute(
        self, filters: RicevutaFiltersSchema, fmt: str
    ) -> tuple[bytes, str, str]:
        """Export massivo (lista filtrata)."""
        pass
