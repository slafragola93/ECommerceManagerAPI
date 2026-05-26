"""Service layer per la generazione del borderò spedizioni.

Orchestratore puro: coordina `OrderRepository` per il recupero spedizioni,
`OrderDocumentService` per i dati mittente e `BorderoPDFService` per la
generazione del PDF. Opzionalmente aggiorna lo stato degli ordini coinvolti
a "Spedizione Confermata" (id_order_state=4) in modalita best-effort,
emettendo l'evento `ORDER_STATUS_CHANGED` per ogni ordine aggiornato.

Note sul caso "0 ordini":
    Per coerenza con il contratto FE (PR 8b) il service NON solleva mai
    eccezioni quando la query non trova ordini idonei. Genera comunque un
    PDF "vuoto" (con riga "Nessuna spedizione idonea") e ritorna count=0
    + lista order_ids vuota. E' il FE che decide cosa fare (alert info,
    no apertura PDF).
"""
import logging
from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.repository.order_repository import OrderRepository
from src.schemas.bordero_schema import BorderoRow
from src.services.pdf.bordero_pdf_service import BorderoPDFService
from src.services.routers.order_document_service import OrderDocumentService
from src.services.routers.order_service import OrderService


logger = logging.getLogger(__name__)

LARGE_BORDERO_THRESHOLD = 500
SPEDIZIONE_CONFERMATA_STATE_ID = 4


class BorderoService:
    """Orchestra la generazione del borderò spedizioni."""

    def __init__(self, db: Session):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.order_service = OrderService(self.order_repo)
        self.order_document_service = OrderDocumentService(db)
        self.pdf_service = BorderoPDFService()

    async def generate_bordero(
        self,
        carrier_id: int,
        update_status: bool,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Tuple[bytes, int, str, List[int]]:
        """Genera il PDF borderò e opzionalmente aggiorna lo stato degli ordini.

        Args:
            carrier_id: ID del corriere selezionato (`carriers_api.id_carrier_api`).
            update_status: Se True, dopo la generazione del PDF gli ordini inclusi
                vengono spostati a stato 4 (Spedizione Confermata) emettendo
                l'evento `ORDER_STATUS_CHANGED`. Operazione best-effort: eventuali
                fallimenti per singolo ordine vengono loggati come warning ma non
                bloccano la restituzione del PDF.
            date_from: Estremo iniziale opzionale per `orders.date_add` (inclusivo).
            date_to: Estremo finale opzionale per `orders.date_add` (inclusivo).

        Returns:
            Tupla `(pdf_bytes, order_count, carrier_name, order_ids)`.
            Quando non ci sono ordini idonei, ritorna comunque un PDF "vuoto"
            con `order_count=0` e `order_ids=[]` (no eccezione).
        """
        date_from_str = date_from.isoformat() if date_from else None
        date_to_str = date_to.isoformat() if date_to else None

        # 1. Query DB: una sola JOIN per recuperare tutte le righe del borderò.
        raw_rows = self.order_repo.find_shipments_for_bordero(
            carrier_id=carrier_id,
            date_from=date_from_str,
            date_to=date_to_str,
        )

        # 2. Resolve carrier_name anche quando 0 righe (per filename/titolo PDF).
        if raw_rows:
            carrier_name = raw_rows[0].carrier_name or ""
        else:
            carrier_name = self._resolve_carrier_name(carrier_id)

        # 3. Soglia diagnostica.
        if len(raw_rows) > LARGE_BORDERO_THRESHOLD:
            logger.warning(
                "Borderò di grandi dimensioni: %d righe per carrier_id=%d",
                len(raw_rows),
                carrier_id,
            )

        # 4. Dati mittente (header PDF).
        try:
            company_info = self.order_document_service.get_company_info() or {}
        except Exception as exc:  # pragma: no cover - fallback difensivo
            logger.warning(
                "Impossibile caricare company_info per borderò: %s", str(exc)
            )
            company_info = {}

        # 5. Articoli per ordine.
        order_ids = [r.id_order for r in raw_rows if r.id_order]
        articles_by_order = (
            self.order_repo.get_product_names_by_order_ids(order_ids)
            if order_ids
            else {}
        )

        # 6. Composizione righe per il PDF.
        bordero_rows: List[BorderoRow] = [
            self._build_row(raw, articles_by_order.get(raw.id_order, []))
            for raw in raw_rows
        ]

        # 7. Generazione PDF (anche quando 0 righe: il PDF service mostra
        #    "Nessuna spedizione idonea").
        pdf_bytes = self.pdf_service.generate_pdf(
            rows=bordero_rows,
            company_info=company_info,
            carrier_name=carrier_name,
            generated_at=datetime.now(),
        )

        # 8. Cambio stato best-effort (solo se ci sono ordini e richiesto).
        if update_status and order_ids:
            await self._update_orders_status_best_effort(order_ids)

        return pdf_bytes, len(bordero_rows), carrier_name, order_ids

    def _resolve_carrier_name(self, carrier_id: int) -> str:
        """Risolve il nome del corriere dal DB (anche se inattivo / 0 ordini).

        Usato per popolare il filename del PDF nel caso "0 ordini" — la query
        principale non ritorna righe da cui leggere il `carrier_name`.
        """
        try:
            carrier = self.order_repo.api_carrier_repository.get_by_id(carrier_id)
            if carrier and getattr(carrier, "name", None):
                return carrier.name
        except Exception as exc:  # pragma: no cover - fallback difensivo
            logger.warning(
                "Impossibile risolvere carrier_name per carrier_id=%d: %s",
                carrier_id,
                str(exc),
            )
        return ""

    @staticmethod
    def _build_row(raw_row, product_names: List[str]) -> BorderoRow:
        """Trasforma una Row SQLAlchemy in un BorderoRow per il PDF service."""
        # Destinatario: company se presente, altrimenti firstname + lastname.
        company = (raw_row.company or "").strip()
        if company:
            recipient = company
        else:
            firstname = (raw_row.firstname or "").strip()
            lastname = (raw_row.lastname or "").strip()
            recipient = f"{firstname} {lastname}".strip()

        # Indirizzo: "via, cap citta".
        addr_parts: List[str] = []
        address1 = (raw_row.address1 or "").strip()
        if address1:
            addr_parts.append(address1)
        postcode = (raw_row.postcode or "").strip()
        city = (raw_row.city or "").strip()
        zone = " ".join(p for p in [postcode, city] if p).strip()
        if zone:
            addr_parts.append(zone)
        address = ", ".join(addr_parts)

        articles = "; ".join(p for p in product_names if p)

        return BorderoRow(
            id_shipping=int(raw_row.id_shipping),
            id_order=int(raw_row.id_order),
            tracking=raw_row.tracking,
            recipient=recipient,
            address=address,
            packages_count=int(raw_row.packages_count or 0),
            weight=float(raw_row.weight or 0.0),
            cash_on_delivery=float(raw_row.cash_on_delivery or 0.0),
            articles=articles,
            carrier_name=raw_row.carrier_name or "",
        )

    async def _update_orders_status_best_effort(self, order_ids: List[int]) -> None:
        """Aggiorna lo stato degli ordini a 'Spedizione Confermata' best-effort.

        Usa `OrderService.update_order_status` (async) per emettere l'evento
        `ORDER_STATUS_CHANGED` per ogni ordine aggiornato. Eventuali errori su
        singoli ordini vengono loggati come warning ma non bloccano
        l'operazione: il PDF e' gia stato generato e va comunque restituito.
        """
        success_count = 0
        failed_count = 0
        for order_id in order_ids:
            try:
                result = await self.order_service.update_order_status(
                    order_id=order_id,
                    new_status_id=SPEDIZIONE_CONFERMATA_STATE_ID,
                )
                if result:
                    success_count += 1
                else:
                    failed_count += 1
                    logger.warning(
                        "Borderò: update_order_status ha ritornato None per order_id=%d",
                        order_id,
                    )
            except Exception as exc:
                failed_count += 1
                logger.warning(
                    "Borderò: errore durante update_order_status per order_id=%d: %s",
                    order_id,
                    str(exc),
                )

        logger.info(
            "Borderò: cambio stato completato (success=%d, failed=%d, total=%d)",
            success_count,
            failed_count,
            len(order_ids),
        )
