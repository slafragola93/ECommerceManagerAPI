"""
Country Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.country_service_interface import ICountryService
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.schemas.country_schema import CountrySchema, CountryResponseSchema, AllCountryResponseSchema
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
    prefix="/api/v1/countries",
    tags=["Country"]
)

def get_country_service(db: db_dependency) -> ICountryService:
    """Dependency injection per Country Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    country_repo = configured_container.resolve_with_session(ICountryRepository, db)
    
    # Crea il service con il repository
    country_service = configured_container.resolve(ICountryService)
    # Inietta il repository nel service
    if hasattr(country_service, '_country_repository'):
        country_service._country_repository = country_repo
    
    return country_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCountryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_countries(
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i country con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        countries = await country_service.get_countries(page=page, limit=limit)
        if not countries:
            raise HTTPException(status_code=404, detail="Nessun country trovato")

        total_count = await country_service.get_countries_count()

        return {"countries": countries, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{country_id}", status_code=status.HTTP_200_OK, response_model=CountryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_country_by_id(
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service),
    country_id: int = Path(gt=0)
):
    """
    Restituisce un singolo country basato sull'ID specificato.

    - **country_id**: Identificativo del country da ricercare.
    """
    try:
        country = await country_service.get_country(country_id)
        return country
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Country non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Country creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_country(
    country_data: CountrySchema,
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service)
):
    """
    Crea un nuovo country con i dati forniti.
    """
    try:
        return await country_service.create_country(country_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{country_id}", status_code=status.HTTP_200_OK, response_description="Country aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_country(
    country_data: CountrySchema,
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service),
    country_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un country esistente basato sull'ID specificato.

    - **country_id**: Identificativo del country da aggiornare.
    """
    try:
        return await country_service.update_country(country_id, country_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Country non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{country_id}", status_code=status.HTTP_200_OK, response_description="Country eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_country(
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service),
    country_id: int = Path(gt=0)
):
    """
    Elimina un country basato sull'ID specificato.

    - **country_id**: Identificativo del country da eliminare.
    """
    try:
        await country_service.delete_country(country_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Country non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
