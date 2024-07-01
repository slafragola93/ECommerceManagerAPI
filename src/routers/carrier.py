from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path, Depends
from sqlalchemy.exc import IntegrityError
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import CarrierSchema, AllCarriersResponseSchema, CarrierResponseSchema
from src.services.wrap import check_authentication
from ..repository.carrier_repository import CarrierRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/carriers',
    tags=['Carrier']
)


def get_repository(db: db_dependency):
    return CarrierRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarriersResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_carriers(
        user: user_dependency,
        cr: CarrierRepository = Depends(get_repository),
        carriers_ids: Optional[str] = None,
        origin_ids: Optional[str] = None,
        carrier_name: Optional[str] = None,
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    carriers = cr.get_all(carriers_ids=carriers_ids,
                          origin_ids=origin_ids,
                          carrier_name=carrier_name,
                          page=page,
                          limit=limit)

    if not carriers:
        raise HTTPException(status_code=404, detail="Nessun corriere trovato")

    total_count = cr.get_count(carriers_ids=carriers_ids,
                               origin_ids=origin_ids,
                               carrier_name=carrier_name)

    return {"carriers": carriers, "total": total_count, "page": page, "limit": limit}


@router.get("/{carrier_id}", status_code=status.HTTP_200_OK, response_model=CarrierResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_carrier_by_id(user: user_dependency,
                            cr: CarrierRepository = Depends(get_repository),
                            carrier_id: int = Path(gt=0)):
    carrier = cr.get_by_id(_id=carrier_id)

    if carrier is None:
        raise HTTPException(status_code=404, detail="Corriere non trovata")

    return carrier


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Corriere creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_carrier(user: user_dependency,
                         cs: CarrierSchema,
                         cr: CarrierRepository = Depends(get_repository)):
    cr.create(data=cs)


@router.put("/{carrier_id}", status_code=status.HTTP_200_OK, response_description="Corriere aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_carrier(user: user_dependency,
                         cs: CarrierSchema,
                         cr: CarrierRepository = Depends(get_repository),
                         carrier_id: int = Path(gt=0)):
    try:
        carrier = cr.get_by_id(_id=carrier_id)

        if carrier is None:
            raise HTTPException(status_code=404, detail="Corriere non trovato")

        cr.update(edited_carrier=carrier,
                  data=cs)

    except IntegrityError:
        raise HTTPException(status_code=400,
                            detail="Errore di integrità dei dati. Verifica i valori unici e i vincoli.")


@router.delete("/{carrier_id}", status_code=status.HTTP_200_OK, response_description="Corriere eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_carrier(user: user_dependency,
                         cr: CarrierRepository = Depends(get_repository),
                         carrier_id: int = Path(gt=0)):
    carrier = cr.get_by_id(_id=carrier_id)

    if carrier is None:
        raise HTTPException(status_code=404, detail="Corriere non trovato")

    cr.delete(carrier)
