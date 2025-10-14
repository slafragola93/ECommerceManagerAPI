from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime
from src.models.order_document import OrderDocument
from src.models.app_configuration import AppConfiguration
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order


class OrderDocumentService:
    """Service centralizzato per funzioni comuni tra Preventivi e DDT"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_next_document_number(self, type_document: str) -> str:
        """
        Genera il prossimo numero sequenziale per un tipo di documento
        
        Args:
            type_document: Tipo di documento ("preventivo", "DDT", "fattura", etc.)
            
        Returns:
            str: Prossimo numero sequenziale
        """
        current_year = datetime.now().year
        
        # Trova il numero più alto per il tipo di documento nell'anno corrente
        max_number = self.db.query(func.max(OrderDocument.document_number)).filter(
            and_(
                OrderDocument.type_document == type_document,
                func.year(OrderDocument.date_add) == current_year
            )
        ).scalar()
        
        if max_number is None:
            return "1"
        
        try:
            next_number = int(max_number) + 1
            return str(next_number)
        except (ValueError, TypeError):
            return "1"
    
    def get_sender_config(self) -> Dict[str, Any]:
        """
        Recupera la configurazione del mittente per DDT da AppConfiguration
        
        Returns:
            Dict con i dati del mittente
        """
        configs = self.db.query(AppConfiguration).filter(
            AppConfiguration.category == "ddt_sender"
        ).all()
        
        sender_config = {}
        for config in configs:
            sender_config[config.name] = config.value
        
        return sender_config
    
    def check_order_invoiced(self, id_order: int) -> bool:
        """
        Verifica se un ordine è stato fatturato
        
        Args:
            id_order: ID dell'ordine
            
        Returns:
            bool: True se l'ordine è stato fatturato
        """
        invoice_exists = self.db.query(FiscalDocument).filter(
            and_(
                FiscalDocument.id_order == id_order,
                FiscalDocument.document_type == "invoice"
            )
        ).first()
        
        return invoice_exists is not None
    
    def check_order_shipped(self, id_order: int) -> bool:
        """
        Verifica se un ordine è stato spedito controllando la cronologia
        
        Args:
            id_order: ID dell'ordine
            
        Returns:
            bool: True se l'ordine è stato spedito
        """
        # Recupera l'ID dello stato "spedito" dalla configurazione
        shipped_state_config = self.db.query(AppConfiguration).filter(
            and_(
                AppConfiguration.category == "order_states",
                AppConfiguration.name == "is_delivered"
            )
        ).first()
        
        if not shipped_state_config:
            # Fallback: usa ID 2 se non configurato
            shipped_state_id = 2
        else:
            try:
                shipped_state_id = int(shipped_state_config.value)
            except (ValueError, TypeError):
                shipped_state_id = 2
        
        # Verifica se l'ordine ha avuto lo stato "spedito" nella cronologia
        from src.models.relations.relations import orders_history
        shipped_history = self.db.query(orders_history).filter(
            and_(
                orders_history.c.id_order == id_order,
                orders_history.c.id_order_state == shipped_state_id
            )
        ).first()
        
        return shipped_history is not None
    
    def is_ddt_modifiable(self, id_order: int) -> bool:
        """
        Verifica se un DDT può essere modificato per un ordine
        
        Args:
            id_order: ID dell'ordine
            
        Returns:
            bool: True se il DDT può essere modificato
        """
        # Un DDT è modificabile solo se:
        # 1. L'ordine non è stato fatturato
        # 2. L'ordine non è stato spedito
        
        is_invoiced = self.check_order_invoiced(id_order)
        is_shipped = self.check_order_shipped(id_order)
        
        return not is_invoiced and not is_shipped
