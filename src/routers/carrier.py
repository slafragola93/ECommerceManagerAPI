"""
Carrier Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.carrier_service_interface import ICarrierService
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.schemas.carrier_schema import CarrierSchema, CarrierResponseSchema, AllCarriersResponseSchema
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
    prefix="/api/v1/carriers",
    tags=["Carrier"]
)

def get_carrier_service(db: db_dependency) -> ICarrierService:
    """Dependency injection per Carrier Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    carrier_repo = configured_container.resolve_with_session(ICarrierRepository, db)
    
    # Crea il service con il repository
    carrier_service = configured_container.resolve(ICarrierService)
    # Inietta il repository nel service
    if hasattr(carrier_service, '_carrier_repository'):
        carrier_service._carrier_repository = carrier_repo
    
    return carrier_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarriersResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_carriers(
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i carrier con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        carriers = await carrier_service.get_carriers(page=page, limit=limit)
        if not carriers:
            raise HTTPException(status_code=404, detail="Nessun carrier trovato")

        total_count = await carrier_service.get_carriers_count()

        return {"carriers": carriers, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{carrier_id}", status_code=status.HTTP_200_OK, response_model=CarrierResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_carrier_by_id(
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service),
    carrier_id: int = Path(gt=0)
):
    """
    Restituisce un singolo carrier basato sull'ID specificato.

    - **carrier_id**: Identificativo del carrier da ricercare.
    """
    try:
        carrier = await carrier_service.get_carrier(carrier_id)
        return carrier
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Carrier non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Carrier creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_carrier(
    carrier_data: CarrierSchema,
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service)
):
    """
    Crea un nuovo carrier con i dati forniti.
    """
    try:
        return await carrier_service.create_carrier(carrier_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{carrier_id}", status_code=status.HTTP_200_OK, response_description="Carrier aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_carrier(
    carrier_data: CarrierSchema,
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service),
    carrier_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un carrier esistente basato sull'ID specificato.

    - **carrier_id**: Identificativo del carrier da aggiornare.
    """
    try:
        return await carrier_service.update_carrier(carrier_id, carrier_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Carrier non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{carrier_id}", status_code=status.HTTP_200_OK, response_description="Carrier eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_carrier(
    user: dict = Depends(get_current_user),
    carrier_service: ICarrierService = Depends(get_carrier_service),
    carrier_id: int = Path(gt=0)
):
    """
    Elimina un carrier basato sull'ID specificato.

    - **carrier_id**: Identificativo del carrier da eliminare.
    """
    try:
        await carrier_service.delete_carrier(carrier_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Carrier non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
