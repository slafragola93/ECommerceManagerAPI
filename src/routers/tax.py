"""
Tax Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
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
from src.services.auth import authorize
from src.services.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/taxes",
    tags=["Tax"]
)

def get_tax_service(db: db_dependency) -> ITaxService:
    """Dependency injection per Tax Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    tax_repo = configured_container.resolve_with_session(ITaxRepository, db)
    
    # Crea il service con il repository
    tax_service = configured_container.resolve(ITaxService)
    # Inietta il repository nel service
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
    Restituisce tutti i tax con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        taxes = await tax_service.get_taxes(page=page, limit=limit)
        if not taxes:
            raise HTTPException(status_code=404, detail="Nessun tax trovato")

        total_count = await tax_service.get_taxes_count()

        return {"taxes": taxes, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{tax_id}", status_code=status.HTTP_200_OK, response_model=TaxResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_tax_by_id(
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service),
    tax_id: int = Path(gt=0)
):
    """
    Restituisce un singolo tax basato sull'ID specificato.

    - **tax_id**: Identificativo del tax da ricercare.
    """
    try:
        tax = await tax_service.get_tax(tax_id)
        return tax
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Tax non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Tax creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_tax(
    tax_data: TaxSchema,
    tax_service: ITaxService = Depends(get_tax_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo tax con i dati forniti.
    """
    try:
        return await tax_service.create_tax(tax_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{tax_id}", status_code=status.HTTP_200_OK, response_description="Tax aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_tax(
    tax_data: TaxSchema,
    tax_service: ITaxService = Depends(get_tax_service),
    tax_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un tax esistente basato sull'ID specificato.

    - **tax_id**: Identificativo del tax da aggiornare.
    """
    try:
        return await tax_service.update_tax(tax_id, tax_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Tax non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{tax_id}", status_code=status.HTTP_200_OK, response_description="Tax eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_tax(
    user: dict = Depends(get_current_user),
    tax_service: ITaxService = Depends(get_tax_service),
    tax_id: int = Path(gt=0)
):
    """
    Elimina un tax basato sull'ID specificato.

    - **tax_id**: Identificativo del tax da eliminare.
    """
    try:
        await tax_service.delete_tax(tax_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Tax non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
