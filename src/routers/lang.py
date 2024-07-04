from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import LangSchema, LangResponseSchema, AllLangsResponseSchema
from src.services.wrap import check_authentication
from ..repository.lang_repository import LangRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/languages',
    tags=['Lang'],
)


def get_repository(db: db_dependency) -> LangRepository:
    return LangRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllLangsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_langs(user: user_dependency,
                        lr: LangRepository = Depends(get_repository),
                        page: int = Query(1, gt=0),
                        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Restituisce l'elenco di tutti i marchi disponibili.
    """

    langs = lr.get_all(page=page, limit=limit)

    if not langs:
        raise HTTPException(status_code=404, detail="Nessun cliente trovato")


    return {"languages": langs, "total": len(langs), "page": page, "limit": limit}


@router.get("/{lang_id}", status_code=status.HTTP_200_OK, response_model=LangResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_lang_by_id(user: user_dependency,
                         lr: LangRepository = Depends(get_repository),
                         lang_id: int = Path(gt=0)):
    """
    Restituisce iuna lingua specificata dall'ID.

    - **lang_id**: ID della lingua da ricercare.
    """
    language = lr.get_by_id(_id=lang_id)

    if language is None:
        raise HTTPException(status_code=404, detail="Lingua non trovata")

    return language


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Lingua creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_language(user: user_dependency,
                          ls: LangSchema,
                          lr: LangRepository = Depends(get_repository)):
    """
    Crea una nuova lingua

    - **ls**: Schema della lingua contenente i dati per la creazione.
    """

    lr.create(data=ls)


@router.delete("/{lang_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Language eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_lang(user: user_dependency,
                      lr: LangRepository = Depends(get_repository),
                      lang_id: int = Path(gt=0)):
    """
    Elimina il marchio specificato dall'ID.

    - **lang_id**: ID della lingua da eliminare.
    """

    language = lr.get_by_id(_id=lang_id)

    if language is None:
        raise HTTPException(status_code=404, detail="Lingua non trovata.")

    lr.delete(lang=language)


@router.put("/{lang_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_brand(user: user_dependency,
                       ls: LangSchema,
                       lr: LangRepository = Depends(get_repository),
                       lang_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli del marchio specificato dall'ID con i nuovi dati forniti.

    - **lang_id**: ID della lingua da aggiornare.
    """

    language = lr.get_by_id(_id=lang_id)

    if language is None:
        raise HTTPException(status_code=404, detail="Lingua non trovata.")

    lr.update(edited_lang=language,
              data=ls)
