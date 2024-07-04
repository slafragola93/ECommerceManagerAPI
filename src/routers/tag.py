from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import TagSchema, TagResponseSchema, AllTagsResponseSchema
from src.services.wrap import check_authentication
from ..repository.tag_repository import TagRepository

router = APIRouter(
    prefix='/api/v1/tags',
    tags=['Tag'],
)


def get_repository(db: db_dependency) -> TagRepository:
    return TagRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllTagsResponseSchema)
@check_authentication
async def get_all_tags(user: user_dependency,
                       tr: TagRepository = Depends(get_repository),
                       page: int = Query(1, gt=0),
                       limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Restituisce l'elenco di tutti i tag disponibili.
    """

    tags = tr.get_all(page=page, limit=limit)

    if not tags:
        raise HTTPException(status_code=404, detail="Nessun tag trovato")

    total_count = tr.get_count()

    return {"tags": tags, "total": total_count, "page": page, "limit": limit}


@router.get("/{tag_id}", status_code=status.HTTP_200_OK, response_model=TagResponseSchema)
@check_authentication
async def get_tag_by_id(user: user_dependency,
                        tr: TagRepository = Depends(get_repository),
                        tag_id: int = Path(gt=0)):
    """
    Restituisce i dettagli di un singolo marchio specificato dall'ID.

    - **tag_id**: ID del tag da ricercare.
    """
    tag = tr.get_by_id(_id=tag_id)

    if tag is None:
        raise HTTPException(status_code=404, detail="Tag non trovato")

    return tag


@router.put("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
async def update_tag(user: user_dependency,
                     ts: TagSchema,
                     tr: TagRepository = Depends(get_repository),
                     tag_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli del tag specificato dall'ID con i nuovi dati forniti.

    - **tag_id**: ID del tag da eliminare.
    """

    tag = tr.get_by_id(_id=tag_id)

    if tag is None:
        raise HTTPException(status_code=404, detail="Tag non trovato.")

    tr.update(edited_tag=tag, data=ts)
