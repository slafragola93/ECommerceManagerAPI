from fastapi import APIRouter, Path, HTTPException, Query
from starlette import status
from src.models.sectional import Sectional
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import SectionalSchema, SectionalResponseSchema, AllSectionalsResponseSchema
from src.services.tool import edit_entity
from src.services.wrap import check_authentication
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/sectional',
    tags=['Sectional'],
)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllSectionalsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_sectionals(user: user_dependency,
                             db: db_dependency,
                             page: int = Query(1, gt=0),
                             limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Restituisce l'elenco di tutti i sezionali disponibili.
    """

    offset = (page - 1) * limit
    sectionals = db.query(Sectional).offset(offset).limit(limit).all()
    return {"sectionals": sectionals, "total": len(sectionals), "page": page, "limit": limit}


@router.get("/{sectional_id}", status_code=status.HTTP_200_OK, response_model=SectionalResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_sectional_by_id(user: user_dependency,
                              db: db_dependency,
                              sectional_id: int = Path(gt=0)):
    """
    Restituisce un sezionale specificato dall'ID.

    - **sectional_id**: ID del sezionale da ricercare.
    """
    sectional = db.query(Sectional).filter(Sectional.id_sectional == sectional_id).first()

    if sectional is None:
        raise HTTPException(status_code=404, detail="Sezionale non trovato")

    return sectional


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Sezionale creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_sectional(user: user_dependency,
                           db: db_dependency,
                           ss: SectionalSchema):
    """
    Crea una nuovo sezionale

    - **ss**: Schema del sezionale contenente i dati per la creazione.
    """

    sectional = Sectional(**ss.model_dump())
    db.add(sectional)
    db.commit()


@router.delete("/{sectional_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Sezionale eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_sectional(user: user_dependency,
                           db: db_dependency,
                           sectional_id: int = Path(gt=0)):
    """
    Elimina il marchio specificato dall'ID.

    - **sectional_id**: ID del sezionale da eliminare.
    """

    sectional = db.query(Sectional).filter(Sectional.id_sectional == sectional_id).first()

    if sectional is None:
        raise HTTPException(status_code=404, detail="Sezionale non trovato.")

    db.delete(sectional)
    db.commit()


@router.put("/{sectional_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_sectional(user: user_dependency,
                           db: db_dependency,
                           ss: SectionalSchema,
                           sectional_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli del sezionale specificato dall'ID con i nuovi dati forniti.

    - **sectional_id**: ID del sezionale da eliminare.
    """

    sectional = db.query(Sectional).filter(Sectional.id_sectional == sectional_id).first()

    if sectional is None:
        raise HTTPException(status_code=404, detail="Sezionale non trovata.")

    edit_entity(sectional, ss)

    db.add(sectional)
    db.commit()
