import string
from typing import Optional

from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import CountryResponseSchema, AllCountryResponseSchema
from src.services.wrap import check_authentication
from ..repository.country_repository import CountryRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/countries',
    tags=['Country'],
)


def get_repository(db: db_dependency) -> CountryRepository:
    return CountryRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCountryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_countries(user: user_dependency,
                            cr: CountryRepository = Depends(get_repository),
                            page: int = Query(1, gt=0),
                            limit: int = Query(default=LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Restituisce l'elenco di tutti i paesi disponibili.
    """

    countries = cr.get_all(page, limit)

    if not countries:
        raise HTTPException(status_code=404, detail="Nessun paese trovato")

    total_count = cr.get_count()

    return {"countries": countries, "total": total_count, "page": page, "limit": limit}

@router.get("/all", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_list_all_countries(user: user_dependency,
                                 cr: CountryRepository = Depends(get_repository)):

    countries = cr.list_all()

    if countries is None:
        raise HTTPException(status_code=404, detail="Paesi non trovati")

    return countries
@router.get("/{country_id}", status_code=status.HTTP_200_OK, response_model=CountryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_country(user: user_dependency,
                      cr: CountryRepository = Depends(get_repository),
                      country_id: int = Path(gt=0)):
    """Restituisce le informazioni riguardanti un paese specifico tramite l'ID."""
    country = cr.get_by_id(_id=country_id)

    if country is None:
        raise HTTPException(status_code=404, detail="Paese non trovato")

    return country



