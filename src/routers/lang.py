"""
Lang Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.lang_service_interface import ILangService
from src.repository.interfaces.lang_repository_interface import ILangRepository
from src.schemas.lang_schema import LangSchema, LangResponseSchema, AllLangsResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/languages",
    tags=["Lang"]
)

def get_lang_service(db: db_dependency) -> ILangService:
    """Dependency injection per Lang Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    lang_repo = configured_container.resolve_with_session(ILangRepository, db)
    lang_service = configured_container.resolve(ILangService)
    
    if hasattr(lang_service, '_lang_repository'):
        lang_service._lang_repository = lang_repo
    
    return lang_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllLangsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_langs(
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutte le lang con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    langs = await lang_service.get_langs(page=page, limit=limit)
    if not langs:
        raise NotFoundException("Langs", None)

    total_count = await lang_service.get_langs_count()

    return {"languages": langs, "total": total_count, "page": page, "limit": limit}

@router.get("/{lang_id}", status_code=status.HTTP_200_OK, response_model=LangResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_lang_by_id(
    lang_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service)
):
    """
    Restituisce una singola lang basata sull'ID specificato.

    - **lang_id**: Identificativo della lang da ricercare.
    """
    lang = await lang_service.get_lang(lang_id)
    return lang

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Lang creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_lang(
    lang_data: LangSchema,
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service)
):
    """
    Crea una nuova lang con i dati forniti.
    """
    return await lang_service.create_lang(lang_data)

@router.put("/{lang_id}", status_code=status.HTTP_200_OK, response_description="Lang aggiornata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_lang(
    lang_data: LangSchema,
    lang_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service)
):
    """
    Aggiorna i dati di una lang esistente basata sull'ID specificato.

    - **lang_id**: Identificativo della lang da aggiornare.
    """
    return await lang_service.update_lang(lang_id, lang_data)

@router.delete("/{lang_id}", status_code=status.HTTP_200_OK, response_description="Lang eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_lang(
    lang_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service)
):
    """
    Elimina una lang basata sull'ID specificato.

    - **lang_id**: Identificativo della lang da eliminare.
    """
    await lang_service.delete_lang(lang_id)