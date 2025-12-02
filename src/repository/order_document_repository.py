from typing import List, Type

from sqlalchemy import func, asc
from sqlalchemy.orm import Session
from .. import AllOrderDocumentResponseSchema, OrderDocumentResponseSchema, OrderDocumentSchema, OrderDocument
from src.services import QueryUtils


class OrderDocumentRepository:

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session
 
