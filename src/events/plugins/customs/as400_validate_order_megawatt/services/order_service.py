"""Servizio per recuperare dati ordine e configurazione applicazione."""

from typing import Optional
from sqlalchemy.orm import Session
from src.models.order import Order
from src.models.app_configuration import AppConfiguration
from ..repositories.order_data_repository import OrderDataRepository
from src.repository.tax_repository import TaxRepository


class OrderDataService:
    """Servizio per recuperare dati ordine e configurazioni correlate."""

    def __init__(self, session: Session):
        """Inizializza il servizio con la sessione database."""
        self.repository = OrderDataRepository(session)
        self.tax_repository = TaxRepository(session)
        self.session = session

    def get_order_for_validation(self, order_id: int) -> Optional[Order]:
        """
        Recupera ordine con tutti i dati necessari per validazione AS400.
        
        Args:
            order_id: ID dell'ordine
            
        Returns:
            Oggetto Order con tutte le relazioni caricate, o None se non trovato
        """
        return self.repository.get_order_with_relations(order_id)

    def get_vat_number(self) -> str:
        """
        Recupera partita IVA da AppConfiguration.
        
        Returns:
            Stringa partita IVA, o stringa vuota se non trovata
        """
        config = (
            self.session.query(AppConfiguration)
            .filter(
                AppConfiguration.category == "company_info",
                AppConfiguration.name == "vat_number"
            )
            .first()
        )
        
        return config.value if config and config.value else ""
    
    def get_tax_percentage(self, id_tax: Optional[int]) -> float:
        """
        Recupera percentuale tassa tramite ID.
        
        Args:
            id_tax: ID della tassa
            
        Returns:
            Percentuale tassa, o 0.0 se id_tax è None o non trovato
        """
        if not id_tax:
            return 0.0
        return self.tax_repository.get_percentage_by_id(id_tax)

