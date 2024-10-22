from fastapi import APIRouter, Path, HTTPException, Depends, Query
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import UserSchema
from src.services.wrap import check_authentication
from ..repository.user_repository import UserRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/users',
    tags=['User'],
)


def get_repository(db: db_dependency) -> UserRepository:
    return UserRepository(db)


@router.get("/", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_all_users(user: user_dependency,
                        ur: UserRepository = Depends(get_repository),
                        page: int = Query(1, gt=0),
                        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    users = ur.get_all(page=page, limit=limit)

    if not users:
        raise HTTPException(status_code=404, detail="Nessun utente trovato")

    total_count = ur.get_count()

    return {
        "users": users,
        "total": total_count,
        "page": page,
        "limit": limit
    }

@router.get("/user-information", status_code=status.HTTP_200_OK)
@check_authentication
async def get_user_by_id(user: user_dependency):
    return user

@router.get("/{user_id}", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI', 'USER'], permissions_required=['R'])
async def get_user_by_id(user: user_dependency,
                         ur: UserRepository = Depends(get_repository),
                         user_id: int = Path(gt=0)):
    user = ur.get_by_id(_id=user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    return user



@router.put("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['U'])
async def update_user(user: user_dependency,
                      us: UserSchema,
                      ur: UserRepository = Depends(get_repository),
                      user_id: int = Path(gt=0)):
    user = ur.get_by_id(_id=user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="Categoria non trovato.")

    ur.update(edited_user=user, data=us)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Utente eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['D'])
async def delete_user(user: user_dependency,
                      ur: UserRepository = Depends(get_repository),
                      user_id: int = Path(gt=0)):
    user = ur.get_by_id(_id=user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="Utente non trovato.")

    ur.delete(user=user)
