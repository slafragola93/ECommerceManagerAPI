from fastapi import APIRouter, Query, HTTPException, Path, Depends
from sqlalchemy.exc import IntegrityError
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import RoleSchema, AllRolesResponseSchema, RoleResponseSchema
from src.services.wrap import check_authentication
from ..repository.role_repository import RoleRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/roles',
    tags=['Role']
)


def get_repository(db: db_dependency):
    return RoleRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllRolesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_roles(
        user: user_dependency,
        rr: RoleRepository = Depends(get_repository),
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    roles = rr.get_all(page=page, limit=limit)

    if not roles:
        raise HTTPException(status_code=404, detail="Nessun ruolo trovato")

    total_count = rr.get_count()

    return {"roles": roles, "total": total_count, "page": page, "limit": limit}


@router.get("/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_role_by_id(user: user_dependency,
                         rr: RoleRepository = Depends(get_repository),
                         role_id: int = Path(gt=0)):
    role = rr.get_by_id(_id=role_id)

    if role is None:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")

    return role


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Ruolo creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_role(user: user_dependency,
                      rr: RoleSchema,
                      cr: RoleRepository = Depends(get_repository)):
    cr.create(data=rr)


@router.put("/{role_id}", status_code=status.HTTP_200_OK, response_description="Ruolo aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_role(user: user_dependency,
                      rs: RoleSchema,
                      cr: RoleRepository = Depends(get_repository),
                      role_id: int = Path(gt=0)):
    try:
        role = cr.get_by_id(_id=role_id)

        if role is None:
            raise HTTPException(status_code=404, detail="Ruolo non trovato")

        cr.update(edited_role=role,
                  data=rs)

    except IntegrityError:
        raise HTTPException(status_code=400,
                            detail="Errore di integrità dei dati. Verifica i valori unici e i vincoli.")


@router.delete("/{role_id}", status_code=status.HTTP_200_OK, response_description="Ruolo eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_role(user: user_dependency,
                      cr: RoleRepository = Depends(get_repository),
                      role_id: int = Path(gt=0)):
    role = cr.get_by_id(_id=role_id)

    if role is None:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")

    cr.delete(role)
