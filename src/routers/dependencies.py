"""
Dipendenze per i router
"""
import os
from fastapi import Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.core.container import container
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.services.auth import get_current_user

# Costanti per paginazione
LIMIT_DEFAULT = 10
MAX_LIMIT = int(os.environ.get("MAX_LIMIT", 500))

# Dipendenze per database e autenticazione
db_dependency = Depends(get_db)
user_dependency = Depends(get_current_user)


def get_fiscal_document_service(db: Session = Depends(get_db)) -> IFiscalDocumentService:
    """Dependency per ottenere il servizio dei documenti fiscali"""
    return container.resolve_with_session(IFiscalDocumentService, db)