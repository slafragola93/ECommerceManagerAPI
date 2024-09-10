from sqlalchemy.exc import IntegrityError
from starlette import status
from fastapi import APIRouter, HTTPException, Query, Depends, Path
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from ..repository.api_carrier_repository import CarrierApiRepository
from src.schemas.carrier_api_schema import *
from src.services.wrap import check_authentication
from ..services.auth import authorize

router = APIRouter(
    prefix="/api/v1/api_carrier",
    tags=['ApiCarrier']
)


def get_api_carrier_repository(db: db_dependency) -> CarrierApiRepository:
    return CarrierApiRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarriersApiResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_all_api_carriers(
        user: user_dependency,
        car: CarrierApiRepository = Depends(get_api_carrier_repository),
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    carriers = car.get_all(page=page,
                           limit=limit)
    if not carriers:
        raise HTTPException(status_code=404, detail="Nessuna corriere trovato")

    total_count = car.get_count()

    return {"carriers": carriers, "total": total_count, "page": page, "limit": limit}


@router.get("/{carrier_api_id}", status_code=status.HTTP_200_OK, response_model=CarrierApiResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_api_carrier_by_id(user: user_dependency,
                                car: CarrierApiRepository = Depends(get_api_carrier_repository),
                                carrier_api_id: int = Path(gt=0)
                                ):
    carrier = car.get_by_id(_id=carrier_api_id)

    if carrier is None:
        raise HTTPException(status_code=404, detail="Corriere non trovata")

    return carrier


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Corriere creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['C'])
async def create_carrier_api(user: user_dependency,
                             cs: CarrierApiSchema,
                             car: CarrierApiRepository = Depends(get_api_carrier_repository)):

    car.create(data=cs)


@router.put("/{carrier_api_id}", status_code=status.HTTP_200_OK,
            response_description="Corriere aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['U'])
async def update_carrier_api(user: user_dependency,
                             cs: CarrierApiSchema,
                             car: CarrierApiRepository = Depends(get_api_carrier_repository),
                             carrier_api_id: int = Path(gt=0)):
    try:
        carrier = car.get_by_id(_id=carrier_api_id)

        if carrier is None:
            raise HTTPException(status_code=404, detail="Corriere non trovato")

        car.update(edited_carrier=carrier,
                   data=cs)

    except IntegrityError:
        raise HTTPException(status_code=400,
                            detail="Errore di integrità dei dati. Verifica i valori unici e i vincoli.")


@router.delete("/{carrier_api_id}", status_code=status.HTTP_200_OK,
               response_description="Corriere eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['D'])
async def delete_carrier_api(user: user_dependency,
                             car: CarrierApiRepository = Depends(get_api_carrier_repository),
                             carrier_api_id: int = Path(gt=0)):

    carrier = car.get_by_id(_id=carrier_api_id)

    if carrier is None:
        raise HTTPException(status_code=404, detail="Corriere non trovato")

    car.delete(carrier)

