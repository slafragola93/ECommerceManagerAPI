from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import BrandSchema, BrandResponseSchema, AllBrandsResponseSchema
from src.services.wrap import check_authentication
from ..repository.brand_repository import BrandRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/brands',
    tags=['Brand'],
)


def get_repository(db: db_dependency) -> BrandRepository:
    return BrandRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllBrandsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_brands(user: user_dependency,
                         br: BrandRepository = Depends(get_repository),
                         page: int = Query(1, gt=0),
                         limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Restituisce l'elenco di tutti i marchi disponibili.

    - **user**: Utente autenticato (dipendenza).
    - **db**: Sessione del database (dipendenza).
    """

    brands = br.get_all(page=page, limit=limit)

    if brands is None:
        raise HTTPException(status_code=404, detail="Brands non trovati")

    total_count = br.get_count()

    return {"brands": brands, "total": total_count, "page": page, "limit": limit}



@router.get("/{brand_id}", status_code=status.HTTP_200_OK, response_model=BrandResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_brand_by_id(user: user_dependency,
                          br: BrandRepository = Depends(get_repository),
                          brand_id: int = Path(gt=0)):
    """
    Restituisce i dettagli di un singolo marchio specificato dall'ID.

    - **user**: Utente autenticato (dipendenza).
    - **db**: Sessione del database (dipendenza).
    - **brand_id**: ID del marchio da ricercare.
    """
    brand = br.get_by_id(_id=brand_id)

    if brand is None:
        raise HTTPException(status_code=404, detail="Brand non trovato")

    return brand


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Brand creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_brand(user: user_dependency,
                       bs: BrandSchema,
                       br: BrandRepository = Depends(get_repository), ):
    """
    Crea un nuovo marchio con i dettagli forniti.

    - **user**: Utente autenticato (dipendenza).
    - **db**: Sessione del database (dipendenza).
    - **bs**: Schema del marchio contenente i dati per la creazione.
    """

    br.create(data=bs)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Brand eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_brand(user: user_dependency,
                       br: BrandRepository = Depends(get_repository),
                       brand_id: int = Path(gt=0)):
    """
    Elimina il marchio specificato dall'ID.

    - **user**: Utente autenticato (dipendenza).
    - **db**: Sessione del database (dipendenza).
    - **brand_id**: ID del marchio da eliminare.
    """

    brand = br.get_by_id(_id=brand_id)

    if brand is None:
        raise HTTPException(status_code=404, detail="Brand non trovato.")

    br.delete(brand)


@router.put("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_brand(user: user_dependency,
                       bs: BrandSchema,
                       br: BrandRepository = Depends(get_repository),
                       brand_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli del marchio specificato dall'ID con i nuovi dati forniti.

    - **user**: Utente autenticato (dipendenza).
    - **db**: Sessione del database (dipendenza).
    - **bs**: Schema del marchio contenente i dati aggiornati.
    - **brand_id**: ID del marchio da aggiornare.
    """

    brand = br.get_by_id(_id=brand_id)

    if brand is None:
        raise HTTPException(status_code=404, detail="Brand non trovato.")

    br.update(edited_brand=brand, data=bs)
