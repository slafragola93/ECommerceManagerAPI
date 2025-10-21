"""
Lang Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
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
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    lang_repo = configured_container.resolve_with_session(ILangRepository, db)
    
    # Crea il service con il repository
    lang_service = configured_container.resolve(ILangService)
    # Inietta il repository nel service
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
    Restituisce tutti i lang con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        langs = await lang_service.get_langs(page=page, limit=limit)
        if not langs:
            raise HTTPException(status_code=404, detail="Nessun lang trovato")

        total_count = await lang_service.get_langs_count()

        return {"languages": langs, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{lang_id}", status_code=status.HTTP_200_OK, response_model=LangResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_lang_by_id(
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service),
    lang_id: int = Path(gt=0)
):
    """
    Restituisce un singolo lang basato sull'ID specificato.

    - **lang_id**: Identificativo del lang da ricercare.
    """
    try:
        lang = await lang_service.get_lang(lang_id)
        return lang
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Lang non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Lang creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_lang(
    lang_data: LangSchema,
    lang_service: ILangService = Depends(get_lang_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo lang con i dati forniti.
    """
    try:
        return await lang_service.create_lang(lang_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{lang_id}", status_code=status.HTTP_200_OK, response_description="Lang aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_lang(
    lang_data: LangSchema,
    lang_service: ILangService = Depends(get_lang_service),
    lang_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un lang esistente basato sull'ID specificato.

    - **lang_id**: Identificativo del lang da aggiornare.
    """
    try:
        return await lang_service.update_lang(lang_id, lang_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Lang non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{lang_id}", status_code=status.HTTP_200_OK, response_description="Lang eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_lang(
    user: dict = Depends(get_current_user),
    lang_service: ILangService = Depends(get_lang_service),
    lang_id: int = Path(gt=0)
):
    """
    Elimina un lang basato sull'ID specificato.

    - **lang_id**: Identificativo del lang da eliminare.
    """
    try:
        await lang_service.delete_lang(lang_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Lang non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
