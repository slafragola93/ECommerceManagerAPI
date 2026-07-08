"""Repository ricevute."""
from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.repository.interfaces.ricevuta_repository_interface import IRicevutaRepository


class RicevutaRepository(BaseRepository[Ricevuta, int], IRicevutaRepository):
    def __init__(self, session: Session):
        super().__init__(session, Ricevuta)

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
        try:
            query = self._session.query(Ricevuta)

            if id_order is not None:
                query = query.filter(Ricevuta.id_order == id_order)
            if id_customer is not None:
                query = query.filter(Ricevuta.id_customer == id_customer)
            if stato is not None:
                query = query.filter(Ricevuta.stato == stato)
            if data_emissione_from is not None:
                query = query.filter(Ricevuta.data_emissione >= data_emissione_from)
            if data_emissione_to is not None:
                query = query.filter(Ricevuta.data_emissione <= data_emissione_to)

            total = query.count()
            offset = self.get_offset(limit, page)
            rows = (
                query.order_by(
                    desc(Ricevuta.data_emissione),
                    desc(Ricevuta.numero),
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            return rows, total
        except Exception as exc:
            raise InfrastructureException(
                f"Database error listing Ricevuta: {exc}"
            ) from exc

    def get_next_numero(self, anno: int) -> int:
        """Numerazione annuale con SELECT FOR UPDATE sul max dell'anno."""
        try:
            current_max = (
                self._session.query(func.max(Ricevuta.numero))
                .filter(Ricevuta.anno == anno)
                .with_for_update()
                .scalar()
            )
            return (current_max or 0) + 1
        except Exception as exc:
            raise InfrastructureException(
                f"Database error retrieving next ricevuta numero: {exc}"
            ) from exc

    def get_by_order_id(self, id_order: int) -> Optional[Ricevuta]:
        try:
            return (
                self._session.query(Ricevuta)
                .filter(
                    Ricevuta.id_order == id_order,
                    Ricevuta.stato == RicevutaStato.EMESSA,
                )
                .order_by(desc(Ricevuta.id_ricevuta))
                .first()
            )
        except Exception as exc:
            raise InfrastructureException(
                f"Database error retrieving ricevuta by order: {exc}"
            ) from exc
