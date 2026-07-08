"""Interfaccia repository ricevute."""
from abc import abstractmethod
from datetime import date
from typing import List, Optional, Tuple

from src.core.interfaces import IRepository
from src.models.ricevuta import Ricevuta


class IRicevutaRepository(IRepository[Ricevuta, int]):
    @abstractmethod
    def list_filtered(
        self,
        *,
        id_order: Optional[int] = None,
        id_customer: Optional[int] = None,
        stato: Optional[str] = None,
        data_emissione_from: Optional[date] = None,
        data_emissione_to: Optional[date] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Ricevuta], int]:
        """Lista paginata con filtri."""
        pass

    @abstractmethod
    def get_next_numero(self, anno: int) -> int:
        """Prossimo numero progressivo per l'anno (con lock riga max)."""
        pass

    @abstractmethod
    def get_by_order_id(self, id_order: int) -> Optional[Ricevuta]:
        """Ricevuta emessa collegata all'ordine, se presente."""
        pass
