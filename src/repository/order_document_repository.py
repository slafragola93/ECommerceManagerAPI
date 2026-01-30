from typing import List
from sqlalchemy.orm import Session
from src.models.order_document import OrderDocument


class OrderDocumentRepository:

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session
    
    def get_shipping_documents_by_order_id(self, order_id: int) -> List[OrderDocument]:
        """
        Recupera tutti gli OrderDocument di tipo "shipping" per un ordine
        
        Args:
            order_id: ID dell'ordine
            
        Returns:
            Lista di OrderDocument di tipo "shipping"
        """
        return self.session.query(OrderDocument).filter(
            OrderDocument.id_order == order_id,
            OrderDocument.type_document == "shipping"
        ).all()
 
