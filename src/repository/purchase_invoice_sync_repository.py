from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Dict, Any
import logging

from src.models.purchase_invoice_sync import PurchaseInvoiceSync
from src.services.query_utils import QueryUtils

logger = logging.getLogger(__name__)


class PurchaseInvoiceSyncRepository:
    """Repository per la gestione delle fatture di acquisto sincronizzate dal POOL FatturaPA"""

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self, page: int = 1, limit: int = 10) -> List[PurchaseInvoiceSync]:
        """
        Recupera tutte le fatture di acquisto sincronizzate

        Args:
            page (int): Numero di pagina
            limit (int): Limite di risultati per pagina

        Returns:
            List[PurchaseInvoiceSync]: Lista delle fatture
        """
        return self.session.query(PurchaseInvoiceSync).order_by(
            desc(PurchaseInvoiceSync.created_at)
        ).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_count(self) -> int:
        """
        Conta il numero totale di fatture sincronizzate

        Returns:
            int: Numero totale di fatture
        """
        return self.session.query(func.count(PurchaseInvoiceSync.id)).scalar()

    def get_by_id(self, _id: int) -> Optional[PurchaseInvoiceSync]:
        """
        Ottieni fattura per ID

        Args:
            _id (int): ID della fattura

        Returns:
            Optional[PurchaseInvoiceSync]: Istanza fattura o None
        """
        return self.session.query(PurchaseInvoiceSync).filter(
            PurchaseInvoiceSync.id == _id
        ).first()

    def get_by_sdi_and_filename(
        self, 
        identificativo_sdi: str, 
        nome_file: str
    ) -> Optional[PurchaseInvoiceSync]:
        """
        Recupera una fattura per IdentificativoSdI e NomeFile (per controllo idempotenza)

        Args:
            identificativo_sdi (str): Identificativo SdI
            nome_file (str): Nome del file

        Returns:
            Optional[PurchaseInvoiceSync]: Fattura trovata o None
        """
        return self.session.query(PurchaseInvoiceSync).filter(
            and_(
                PurchaseInvoiceSync.identificativo_sdi == identificativo_sdi,
                PurchaseInvoiceSync.nome_file == nome_file
            )
        ).first()

    def get_by_sdi(self, identificativo_sdi: str) -> List[PurchaseInvoiceSync]:
        """
        Recupera tutte le fatture con uno specifico IdentificativoSdI

        Args:
            identificativo_sdi (str): Identificativo SdI

        Returns:
            List[PurchaseInvoiceSync]: Lista delle fatture
        """
        return self.session.query(PurchaseInvoiceSync).filter(
            PurchaseInvoiceSync.identificativo_sdi == identificativo_sdi
        ).all()

    def get_by_tipo(self, tipo: str, page: int = 1, limit: int = 10) -> List[PurchaseInvoiceSync]:
        """
        Recupera fatture filtrate per tipo (es. 'Ricezione', 'Notifica')

        Args:
            tipo (str): Tipo di documento
            page (int): Numero di pagina
            limit (int): Limite di risultati per pagina

        Returns:
            List[PurchaseInvoiceSync]: Lista delle fatture
        """
        return self.session.query(PurchaseInvoiceSync).filter(
            PurchaseInvoiceSync.tipo == tipo
        ).order_by(
            desc(PurchaseInvoiceSync.created_at)
        ).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def get_by_direzione(self, direzione: str, page: int = 1, limit: int = 10) -> List[PurchaseInvoiceSync]:
        """
        Recupera fatture filtrate per direzione (es. 'Acquisto', 'Vendita')

        Args:
            direzione (str): Direzione del documento
            page (int): Numero di pagina
            limit (int): Limite di risultati per pagina

        Returns:
            List[PurchaseInvoiceSync]: Lista delle fatture
        """
        return self.session.query(PurchaseInvoiceSync).filter(
            PurchaseInvoiceSync.direzione == direzione
        ).order_by(
            desc(PurchaseInvoiceSync.created_at)
        ).offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

    def exists(self, identificativo_sdi: str, nome_file: str) -> bool:
        """
        Verifica se una fattura esiste già (per controllo duplicati)

        Args:
            identificativo_sdi (str): Identificativo SdI
            nome_file (str): Nome del file

        Returns:
            bool: True se esiste, False altrimenti
        """
        return self.session.query(
            self.session.query(PurchaseInvoiceSync).filter(
                and_(
                    PurchaseInvoiceSync.identificativo_sdi == identificativo_sdi,
                    PurchaseInvoiceSync.nome_file == nome_file
                )
            ).exists()
        ).scalar()

    def create(self, data: Dict[str, Any]) -> Optional[PurchaseInvoiceSync]:
        """
        Crea una nuova fattura (con gestione idempotenza su duplicati)

        Args:
            data (Dict[str, Any]): Dati della fattura

        Returns:
            Optional[PurchaseInvoiceSync]: Fattura creata o None se già esistente
        """
        try:
            invoice = PurchaseInvoiceSync(**data)
            self.session.add(invoice)
            self.session.commit()
            self.session.refresh(invoice)
            logger.info(
                f"Creata fattura acquisto: SDI={invoice.identificativo_sdi}, "
                f"File={invoice.nome_file}"
            )
            return invoice
        except IntegrityError as e:
            self.session.rollback()
            logger.warning(
                f"Fattura già esistente (skip duplicato): SDI={data.get('identificativo_sdi')}, "
                f"File={data.get('nome_file')}"
            )
            return None
        except Exception as e:
            self.session.rollback()
            logger.error(f"Errore creazione fattura: {e}")
            raise

    def create_bulk(self, invoices_data: List[Dict[str, Any]]) -> List[PurchaseInvoiceSync]:
        """
        Crea multiple fatture in batch (salta duplicati)

        Args:
            invoices_data (List[Dict[str, Any]]): Lista dei dati delle fatture

        Returns:
            List[PurchaseInvoiceSync]: Lista delle fatture create (esclusi duplicati)
        """
        created_invoices = []
        for data in invoices_data:
            try:
                invoice = PurchaseInvoiceSync(**data)
                self.session.add(invoice)
                self.session.flush()  # Flush per verificare constraint prima del commit
                created_invoices.append(invoice)
            except IntegrityError:
                self.session.rollback()
                logger.warning(
                    f"Fattura duplicata saltata: SDI={data.get('identificativo_sdi')}, "
                    f"File={data.get('nome_file')}"
                )
                continue
        
        if created_invoices:
            self.session.commit()
            for invoice in created_invoices:
                self.session.refresh(invoice)
        
        logger.info(f"Create {len(created_invoices)} fatture su {len(invoices_data)} totali")
        return created_invoices

    def update(self, invoice: PurchaseInvoiceSync, data: Dict[str, Any]) -> PurchaseInvoiceSync:
        """
        Aggiorna una fattura esistente

        Args:
            invoice (PurchaseInvoiceSync): Fattura da aggiornare
            data (Dict[str, Any]): Nuovi dati

        Returns:
            PurchaseInvoiceSync: Fattura aggiornata
        """
        for key, value in data.items():
            if hasattr(invoice, key) and value is not None:
                setattr(invoice, key, value)

        self.session.add(invoice)
        self.session.commit()
        self.session.refresh(invoice)
        return invoice

    def delete(self, invoice: PurchaseInvoiceSync) -> bool:
        """
        Elimina una fattura

        Args:
            invoice (PurchaseInvoiceSync): Fattura da eliminare

        Returns:
            bool: True se eliminata con successo
        """
        try:
            self.session.delete(invoice)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Errore eliminazione fattura: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Recupera statistiche sulle fatture sincronizzate

        Returns:
            Dict[str, Any]: Statistiche (totali, per direzione, per tipo, ecc.)
        """
        total = self.get_count()
        
        # Conta per direzione
        by_direzione = self.session.query(
            PurchaseInvoiceSync.direzione,
            func.count(PurchaseInvoiceSync.id).label('count')
        ).group_by(PurchaseInvoiceSync.direzione).all()
        
        # Conta per tipo
        by_tipo = self.session.query(
            PurchaseInvoiceSync.tipo,
            func.count(PurchaseInvoiceSync.id).label('count')
        ).group_by(PurchaseInvoiceSync.tipo).all()
        
        return {
            'total': total,
            'by_direzione': {row.direzione: row.count for row in by_direzione},
            'by_tipo': {row.tipo: row.count for row in by_tipo}
        }

