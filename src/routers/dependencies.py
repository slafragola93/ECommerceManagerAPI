"""
Dipendenze per i router
"""
import os
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.core.container import container
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.services.routers.auth_service import get_current_user
from src.models.platform import Platform
from src.services.ecommerce.service_factory import create_ecommerce_service
from src.core.exceptions import BusinessRuleException

# Costanti per paginazione
LIMIT_DEFAULT = 10
MAX_LIMIT = int(os.environ.get("MAX_LIMIT", 500))

# Dipendenze per database e autenticazione
db_dependency = Depends(get_db)
user_dependency = Depends(get_current_user)


def get_fiscal_document_service(db: Session = Depends(get_db)) -> IFiscalDocumentService:
    """Dependency per ottenere il servizio dei documenti fiscali"""
    return container.resolve_with_session(IFiscalDocumentService, db)


def get_ecommerce_service(platform: Platform, db: Session, new_elements: bool = None, **kwargs):
    """
    Seleziona il service e-commerce corretto in base al nome della piattaforma.
    
    Questa funzione centralizzata può essere utilizzata da tutti i router per
    ottenere il service corretto in base alla piattaforma.
    
    Args:
        platform: Oggetto Platform con informazioni sulla piattaforma
        db: Database session
        new_elements: Optional, per PrestaShopService indica se sincronizzare solo nuovi elementi
        **kwargs: Parametri aggiuntivi da passare al costruttore del service
        
    Returns:
        Service instance appropriato (PrestaShopService, etc.)
        
    Raises:
        HTTPException: Se la piattaforma non è supportata
    """
    service_kwargs = dict(kwargs)
    if new_elements is not None:
        service_kwargs["new_elements"] = new_elements

    try:
        return create_ecommerce_service(platform, db, **service_kwargs)
    except BusinessRuleException as exc:
        raise HTTPException(status_code=400, detail=exc.message)