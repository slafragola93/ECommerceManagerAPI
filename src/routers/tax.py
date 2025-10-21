"""
Tax Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.tax_service_interface import ITaxService
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.schemas.tax_schema import TaxSchema, TaxResponseSchema, AllTaxesResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/taxes",
    tags=["Tax"],
)

def get_tax_service(db: db_dependency) -> ITaxService:
    """Dependency injection per Tax Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    tax_repo = configured_container.resolve_with_session(ITaxRepository, db)
    tax_service = configured_container.resolve(ITaxService)
    
    if hasattr(tax_service, '_tax_repository'):
        tax_service._tax_repository = tax_repo
    
    return tax_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllTaxesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_taxes(
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutte le tax con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    taxes = await tax_service.get_taxes(page=page, limit=limit)
    if not taxes:
        raise NotFoundException("Taxes", None)

    total_count = await tax_service.get_taxes_count()

    return {"taxes": taxes, "total": total_count, "page": page, "limit": limit}

@router.get("/{tax_id}", status_code=status.HTTP_200_OK, response_model=TaxResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_tax_by_id(
    tax_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service)
):
    """
    Restituisce una singola tax basata sull'ID specificato.

    - **tax_id**: Identificativo della tax da ricercare.
    """
    tax = await tax_service.get_tax(tax_id)
    return tax

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Tax creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_tax(
    tax_data: TaxSchema,
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service)
):
    """
    Crea una nuova tax con i dati forniti.
    """
    return await tax_service.create_tax(tax_data)

@router.put("/{tax_id}", status_code=status.HTTP_200_OK, response_description="Tax aggiornata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_tax(
    tax_data: TaxSchema,
    tax_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service)
):
    """
    Aggiorna i dati di una tax esistente basata sull'ID specificato.

    - **tax_id**: Identificativo della tax da aggiornare.
    """
    return await tax_service.update_tax(tax_id, tax_data)

@router.delete("/{tax_id}", status_code=status.HTTP_200_OK, response_description="Tax eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_tax(
    tax_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service)
):
    """
    Elimina una tax basata sull'ID specificato.

    - **tax_id**: Identificativo della tax da eliminare.
    """
    await tax_service.delete_tax(tax_id)