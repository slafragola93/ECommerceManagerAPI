"""
Country Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.country_service_interface import ICountryService
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.schemas.country_schema import CountrySchema, CountryResponseSchema, AllCountryResponseSchema
from src.core.container import container
from src.core.exceptions import (
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/countries",
    tags=["Country"],
)

def get_country_service(db: db_dependency) -> ICountryService:
    """Dependency injection per Country Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    country_repo = configured_container.resolve_with_session(ICountryRepository, db)
    country_service = configured_container.resolve(ICountryService)
    
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
    countries = await country_service.get_countries(page=page, limit=limit)
    if not countries:
        raise NotFoundException("Countries", None)

    total_count = await country_service.get_countries_count()

    return {"countries": countries, "total": total_count, "page": page, "limit": limit}

@router.get("/{country_id}", status_code=status.HTTP_200_OK, response_model=CountryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_country_by_id(
    country_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service)
):
    """
    Restituisce un singolo country basato sull'ID specificato.

    - **country_id**: Identificativo del country da ricercare.
    """
    country = await country_service.get_country(country_id)
    return country

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
    return await country_service.create_country(country_data)

@router.put("/{country_id}", status_code=status.HTTP_200_OK, response_description="Country aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_country(
    country_data: CountrySchema,
    country_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service)
):
    """
    Aggiorna i dati di un country esistente basato sull'ID specificato.

    - **country_id**: Identificativo del country da aggiornare.
    """
    return await country_service.update_country(country_id, country_data)

@router.delete("/{country_id}", status_code=status.HTTP_200_OK, response_description="Country eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_country(
    country_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    country_service: ICountryService = Depends(get_country_service)
):
    """
    Elimina un country basato sull'ID specificato.

    - **country_id**: Identificativo del country da eliminare.
    """
    await country_service.delete_country(country_id)