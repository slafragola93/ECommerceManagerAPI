"""
API Carrier Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.api_carrier_service_interface import IApiCarrierService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.schemas.carrier_api_schema import CarrierApiSchema, CarrierApiResponseSchema, AllCarriersApiResponseSchema
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
    prefix="/api/v1/api_carriers",
    tags=["ApiCarrier"],
)

def get_api_carrier_service(db: db_dependency) -> IApiCarrierService:
    """Dependency injection per API Carrier Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    api_carrier_repo = configured_container.resolve_with_session(IApiCarrierRepository, db)
    api_carrier_service = configured_container.resolve(IApiCarrierService)
    if hasattr(api_carrier_service, '_api_carrier_repository'):
        api_carrier_service._api_carrier_repository = api_carrier_repo
    
    return api_carrier_service


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarriersApiResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_all_api_carriers(
    user: dict = Depends(get_current_user),
    api_carrier_service: IApiCarrierService = Depends(get_api_carrier_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti gli API carrier con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        api_carriers = await api_carrier_service.get_api_carriers(page=page, limit=limit)
        if not api_carriers:
            raise HTTPException(status_code=404, detail="Nessun API carrier trovato")

        total_count = await api_carrier_service.get_api_carriers_count()

        return {"carriers": api_carriers, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{carrier_api_id}", status_code=status.HTTP_200_OK, response_model=CarrierApiResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_api_carrier_by_id(
    user: dict = Depends(get_current_user),
    api_carrier_service: IApiCarrierService = Depends(get_api_carrier_service),
    carrier_api_id: int = Path(gt=0)
):
    """
    Restituisce un singolo API carrier basato sull'ID specificato.
    - **carrier_api_id**: Identificativo dell'API carrier da ricercare.
    """
    try:
        api_carrier = await api_carrier_service.get_api_carrier(carrier_api_id)
        return api_carrier
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="API carrier non trovato.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CarrierApiResponseSchema, response_description="API carrier creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['C'])
async def create_carrier_api(
    api_carrier_data: CarrierApiSchema,
    user: dict = Depends(get_current_user),
    api_carrier_service: IApiCarrierService = Depends(get_api_carrier_service)
):
    """
    Crea un nuovo API carrier con i dati forniti.
    - **api_carrier_data**: Dati del nuovo API carrier da creare.
    """
    try:
        api_carrier = await api_carrier_service.create_api_carrier(api_carrier_data)
        return api_carrier
    except (ValidationException, BusinessRuleException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{carrier_api_id}", status_code=status.HTTP_200_OK, response_model=CarrierApiResponseSchema, response_description="API carrier aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['U'])
async def update_carrier_api(
    api_carrier_data: CarrierApiSchema,
    api_carrier_service: IApiCarrierService = Depends(get_api_carrier_service),
    carrier_api_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna un API carrier esistente con i nuovi dati forniti.
    - **carrier_api_id**: Identificativo dell'API carrier da aggiornare.
    - **api_carrier_data**: Nuovi dati dell'API carrier.
    """
    try:
        api_carrier = await api_carrier_service.update_api_carrier(carrier_api_id, api_carrier_data)
        return api_carrier
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="API carrier non trovato.")
    except (ValidationException, BusinessRuleException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{carrier_api_id}", status_code=status.HTTP_200_OK, response_description="API carrier eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['D'])
async def delete_carrier_api(
    user: dict = Depends(get_current_user),
    api_carrier_service: IApiCarrierService = Depends(get_api_carrier_service),
    carrier_api_id: int = Path(gt=0)
):
    """
    Elimina un API carrier dal sistema.
    - **carrier_api_id**: Identificativo dell'API carrier da eliminare.
    """
    try:
        success = await api_carrier_service.delete_api_carrier(carrier_api_id)
        if not success:
            raise HTTPException(status_code=500, detail="Errore durante l'eliminazione dell'API carrier.")
        return {"message": "API carrier eliminato correttamente"}
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="API carrier non trovato.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

