from datetime import date, datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
import logging

from src.models.purchase_invoice_sync import PurchaseInvoiceSync
from src.models.purchase_invoice_sync_detail import PurchaseInvoiceSyncDetail
from src.services.core.query_utils import QueryUtils

logger = logging.getLogger(__name__)


class PurchaseInvoiceSyncRepository:
    """Repository per la gestione delle fatture di acquisto sincronizzate dal POOL FatturaPA"""

    def __init__(self, session: Session):
        self.session = session

    def _apply_filters(
        self,
        query,
        *,
        is_paid: Optional[bool] = None,
        tipo_documento: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        q: Optional[str] = None,
    ):
        if is_paid is not None:
            query = query.filter(PurchaseInvoiceSync.is_paid == is_paid)
        if tipo_documento:
            query = query.filter(PurchaseInvoiceSync.tipo_documento == tipo_documento)
        if date_from is not None:
            query = query.filter(PurchaseInvoiceSync.data_documento >= date_from)
        if date_to is not None:
            query = query.filter(PurchaseInvoiceSync.data_documento <= date_to)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    PurchaseInvoiceSync.fornitore_denominazione.ilike(like),
                    PurchaseInvoiceSync.fornitore_piva.ilike(like),
                    PurchaseInvoiceSync.numero_documento.ilike(like),
                    PurchaseInvoiceSync.identificativo_sdi.ilike(like),
                    PurchaseInvoiceSync.nome_file.ilike(like),
                )
            )
        return query

    def list_filtered(
        self,
        page: int = 1,
        limit: int = 20,
        *,
        is_paid: Optional[bool] = None,
        tipo_documento: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        q: Optional[str] = None,
    ) -> List[PurchaseInvoiceSync]:
        query = self.session.query(PurchaseInvoiceSync).options(
            joinedload(PurchaseInvoiceSync.payment)
        )
        query = self._apply_filters(
            query,
            is_paid=is_paid,
            tipo_documento=tipo_documento,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        return (
            query.order_by(
                desc(PurchaseInvoiceSync.data_documento),
                desc(PurchaseInvoiceSync.created_at),
            )
            .offset(QueryUtils.get_offset(limit, page))
            .limit(limit)
            .all()
        )

    def count_filtered(
        self,
        *,
        is_paid: Optional[bool] = None,
        tipo_documento: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        q: Optional[str] = None,
    ) -> int:
        query = self.session.query(func.count(PurchaseInvoiceSync.id))
        query = self._apply_filters(
            query,
            is_paid=is_paid,
            tipo_documento=tipo_documento,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        return query.scalar() or 0

    def get_all(self, page: int = 1, limit: int = 10) -> List[PurchaseInvoiceSync]:
        return self.list_filtered(page=page, limit=limit)

    def get_count(self) -> int:
        return self.count_filtered()

    def get_by_id(
        self, _id: int, *, with_details: bool = False
    ) -> Optional[PurchaseInvoiceSync]:
        query = self.session.query(PurchaseInvoiceSync).options(
            joinedload(PurchaseInvoiceSync.payment)
        )
        if with_details:
            query = query.options(joinedload(PurchaseInvoiceSync.details))
        return query.filter(PurchaseInvoiceSync.id == _id).first()

    def get_by_sdi_and_filename(
        self,
        identificativo_sdi: str,
        nome_file: str,
    ) -> Optional[PurchaseInvoiceSync]:
        return (
            self.session.query(PurchaseInvoiceSync)
            .filter(
                and_(
                    PurchaseInvoiceSync.identificativo_sdi == identificativo_sdi,
                    PurchaseInvoiceSync.nome_file == nome_file,
                )
            )
            .first()
        )

    def exists(self, identificativo_sdi: str, nome_file: str) -> bool:
        return self.session.query(
            self.session.query(PurchaseInvoiceSync)
            .filter(
                and_(
                    PurchaseInvoiceSync.identificativo_sdi == identificativo_sdi,
                    PurchaseInvoiceSync.nome_file == nome_file,
                )
            )
            .exists()
        ).scalar()

    def create(
        self,
        data: Dict[str, Any],
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[PurchaseInvoiceSync]:
        payload = dict(data)
        details_data = details if details is not None else payload.pop("details", None)
        try:
            invoice = PurchaseInvoiceSync(**payload)
            self.session.add(invoice)
            self.session.flush()
            if details_data:
                for line in details_data:
                    self.session.add(
                        PurchaseInvoiceSyncDetail(
                            id_purchase_invoice_sync=invoice.id,
                            **line,
                        )
                    )
            self.session.commit()
            self.session.refresh(invoice)
            logger.info(
                "Creata fattura acquisto: SDI=%s, File=%s",
                invoice.identificativo_sdi,
                invoice.nome_file,
            )
            return invoice
        except IntegrityError:
            self.session.rollback()
            logger.warning(
                "Fattura già esistente (skip duplicato): SDI=%s, File=%s",
                data.get("identificativo_sdi"),
                data.get("nome_file"),
            )
            return None
        except Exception as e:
            self.session.rollback()
            logger.error("Errore creazione fattura: %s", e)
            raise

    def replace_details(
        self, invoice: PurchaseInvoiceSync, details: List[Dict[str, Any]]
    ) -> PurchaseInvoiceSync:
        invoice.details.clear()
        self.session.flush()
        for line in details:
            invoice.details.append(PurchaseInvoiceSyncDetail(**line))
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        return invoice

    def update(
        self, invoice: PurchaseInvoiceSync, data: Dict[str, Any]
    ) -> PurchaseInvoiceSync:
        for key, value in data.items():
            if hasattr(invoice, key):
                setattr(invoice, key, value)
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        return invoice

    def update_payment(
        self,
        invoice: PurchaseInvoiceSync,
        *,
        is_paid: bool,
        id_payment: Optional[int],
        paid_at: Optional[datetime],
    ) -> PurchaseInvoiceSync:
        invoice.is_paid = is_paid
        invoice.id_payment = id_payment
        invoice.paid_at = paid_at
        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        return invoice

    def delete(self, invoice: PurchaseInvoiceSync) -> bool:
        try:
            self.session.delete(invoice)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error("Errore eliminazione fattura: %s", e)
            return False

    def list_needing_backfill(self, limit: int = 100) -> List[PurchaseInvoiceSync]:
        return (
            self.session.query(PurchaseInvoiceSync)
            .filter(
                PurchaseInvoiceSync.xml_content.isnot(None),
                or_(
                    PurchaseInvoiceSync.tipo_documento.is_(None),
                    PurchaseInvoiceSync.numero_documento.is_(None),
                ),
            )
            .limit(limit)
            .all()
        )

    def get_statistics(self) -> Dict[str, Any]:
        total = self.get_count()
        by_direzione = (
            self.session.query(
                PurchaseInvoiceSync.direzione,
                func.count(PurchaseInvoiceSync.id).label("count"),
            )
            .group_by(PurchaseInvoiceSync.direzione)
            .all()
        )
        by_tipo = (
            self.session.query(
                PurchaseInvoiceSync.tipo,
                func.count(PurchaseInvoiceSync.id).label("count"),
            )
            .group_by(PurchaseInvoiceSync.tipo)
            .all()
        )
        return {
            "total": total,
            "by_direzione": {row.direzione: row.count for row in by_direzione},
            "by_tipo": {row.tipo: row.count for row in by_tipo},
        }
