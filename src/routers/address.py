"""
Address Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.address_service_interface import IAddressService
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.schemas.address_schema import AddressSchema, AddressResponseSchema, AllAddressResponseSchema
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
    prefix="/api/v1/addresses",
    tags=["Address"]
)

def get_address_service(db: db_dependency) -> IAddressService:
    """Dependency injection per Address Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    address_repo = configured_container.resolve_with_session(IAddressRepository, db)
    
    # Crea il service con il repository
    address_service = configured_container.resolve(IAddressService)
    # Inietta il repository nel service
    if hasattr(address_service, '_address_repository'):
        address_service._address_repository = address_repo
    
    return address_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllAddressResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_addresses(
    user: dict = Depends(get_current_user),
    address_service: IAddressService = Depends(get_address_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i address con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        addresses = await address_service.get_addresses(page=page, limit=limit)
        if not addresses:
            raise HTTPException(status_code=404, detail="Nessun address trovato")

        total_count = await address_service.get_addresses_count()

        return {"addresses": addresses, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{address_id}", status_code=status.HTTP_200_OK, response_model=AddressResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_address_by_id(
    user: dict = Depends(get_current_user),
    address_service: IAddressService = Depends(get_address_service),
    address_id: int = Path(gt=0)
):
    """
    Restituisce un singolo address basato sull'ID specificato.

    - **address_id**: Identificativo del address da ricercare.
    """
    try:
        address = await address_service.get_address(address_id)
        return address
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Address non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Address creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_address(
    address_data: AddressSchema,
    user: dict = Depends(get_current_user),
    address_service: IAddressService = Depends(get_address_service)
):
    """
    Crea un nuovo address con i dati forniti.
    """
    try:
        return await address_service.create_address(address_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{address_id}", status_code=status.HTTP_200_OK, response_description="Address aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_address(
    address_data: AddressSchema,
    user: dict = Depends(get_current_user),
    address_service: IAddressService = Depends(get_address_service),
    address_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un address esistente basato sull'ID specificato.

    - **address_id**: Identificativo del address da aggiornare.
    """
    try:
        return await address_service.update_address(address_id, address_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Address non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{address_id}", status_code=status.HTTP_200_OK, response_description="Address eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_address(
    user: dict = Depends(get_current_user),
    address_service: IAddressService = Depends(get_address_service),
    address_id: int = Path(gt=0)
):
    """
    Elimina un address basato sull'ID specificato.

    - **address_id**: Identificativo del address da eliminare.
    """
    try:
        await address_service.delete_address(address_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Address non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
