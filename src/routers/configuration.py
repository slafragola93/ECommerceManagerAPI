from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from src.services.wrap import check_authentication
from ..repository.configuration_repository import ConfigurationRepository
from ..schemas.configuration_schema import AllConfigurationsResponseSchema, ConfigurationResponseSchema, \
    ConfigurationSchema
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/configs',
    tags=['Configuration'],
)


def get_repository(db: db_dependency) -> ConfigurationRepository:
    return ConfigurationRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllConfigurationsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_configurations(user: user_dependency,
                                 cr: ConfigurationRepository = Depends(get_repository),
                                 page: int = Query(1, gt=0),
                                 limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    configurations = cr.get_all(page=page, limit=limit)

    if configurations is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    total_count = cr.get_count()

    return {"configurations": configurations, "total": total_count, "page": page, "limit": limit}


@router.get("/{configuration_id}", status_code=status.HTTP_200_OK, response_model=ConfigurationResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_configuration_by_id(user: user_dependency,
                                  cr: ConfigurationRepository = Depends(get_repository),
                                  configuration_id: int = Path(gt=0)):
    configuration = cr.get_by_id(_id=configuration_id)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata")

    return configuration


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Configurazione creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_configuration(user: user_dependency,
                               cs: ConfigurationSchema,
                               cr: ConfigurationRepository = Depends(get_repository) ):
    cr.create(data=cs)


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Configuration eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_configuration(user: user_dependency,
                               br: ConfigurationRepository = Depends(get_repository),
                               configuration_id: int = Path(gt=0)):
    configuration = br.get_by_id(_id=configuration_id)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovata.")

    br.delete(configuration)


@router.put("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_configuration(user: user_dependency,
                               bs: ConfigurationSchema,
                               br: ConfigurationRepository = Depends(get_repository),
                               configuration_id: int = Path(gt=0)):

    configuration = br.get_by_id(_id=configuration_id)

    if configuration is None:
        raise HTTPException(status_code=404, detail="Configurazione non trovato.")

    br.update(edited_configuration=configuration, data=bs)
