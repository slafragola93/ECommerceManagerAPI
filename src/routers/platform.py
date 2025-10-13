from fastapi import APIRouter, Path, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from starlette import status
from src.models import Platform
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import PlatformSchema, PlatformResponseSchema, AllPlatformsResponseSchema
from src.services.tool import edit_entity
from src.services.wrap import check_authentication

router = APIRouter(
    prefix='/api/v1/platforms',
    tags=['Platform'],
)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllPlatformsResponseSchema)
@check_authentication
async def get_all_platforms(user: user_dependency,
                            db: db_dependency,
                            page: int = Query(1, gt=0),
                            limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
     Ottiene un elenco paginato di tutte le piattaforme disponibili nel sistema.

     Args:
         page (int): Numero della pagina corrente per la paginazione.
         limit (int): Numero massimo di elementi per pagina.

     Returns:
         Una lista paginata di piattaforme conforme allo schema 'AllPlatformsResponseSchema'.
     """
    offset = (page - 1) * limit
    platforms = db.query(Platform).offset(offset).limit(limit).all()

    return {"platforms": platforms, "total": len(platforms), "page": page, "limit": limit}


@router.get("/{platform_id}", status_code=status.HTTP_200_OK, response_model=PlatformResponseSchema)
@check_authentication
async def get_platform_by_id(user: user_dependency,
                             db: db_dependency,
                             platform_id: int = Path(gt=0)):
    """
    Recupera i dettagli di una singola piattaforma basata sull'ID fornito.

    Args:
        platform_id (int): ID univoco della piattaforma da recuperare.

    Returns:
        I dettagli della piattaforma conforme allo schema 'PlatformResponseSchema'.
    """
    platform = db.query(Platform).filter(Platform.id_platform == platform_id).first()

    if platform is None:
        raise HTTPException(status_code=404, detail="Platform non trovato")

    return platform


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Piattaforma creato correttamente")
@check_authentication
async def create_platform(user: user_dependency,
                          db: db_dependency,
                          ps: PlatformSchema):
    """
    Crea una nuova piattaforma nel sistema.

    Returns:
        Conferma della creazione con dettagli della nuova piattaforma inserita.
    """
    platform = Platform(**ps.model_dump())
    db.add(platform)
    db.commit()


@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Piattaforma eliminata correttamente")
@check_authentication
async def delete_platform_by_id(user: user_dependency,
                                db: db_dependency,
                                platform_id: int = Path(gt=0)):
    platform = db.query(Platform).filter(Platform.id_platform == platform_id).first()

    if platform is None:
        raise HTTPException(status_code=404, detail="Piattaforma non trovata.")

    db.delete(platform)
    db.commit()


@router.put("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
async def update_platform(user: user_dependency,
                          db: db_dependency,
                          ps: PlatformSchema,
                          platform_id: int = Path(gt=0)):
    """
    Elimina una piattaforma specifica dal sistema.

    Args:
        platform_id (int): ID della piattaforma da eliminare.

    Returns:
        Conferma dell'eliminazione senza contenuto restituito.
    """
    try:
        platform = db.query(Platform).filter(Platform.id_platform == platform_id).first()

        if platform is None:
            raise HTTPException(status_code=404, detail="Piattaforma non trovata")

        edit_entity(platform, ps)

        db.add(platform)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400,
                            detail="Errore di integrità dei dati. Verifica i valori unici e i vincoli.")


@router.delete("/{platform_id}", status_code=status.HTTP_200_OK,
               response_description="Piattaforma eliminata correttamente")
@check_authentication
async def delete_platform(user: user_dependency,
                          db: db_dependency,
                          platform_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli di una piattaforma esistente.

    Args:
        platform_id (int): ID della piattaforma da aggiornare.

    Returns:
        Conferma dell'aggiornamento senza contenuto restituito.
    """
    platform = db.query(Platform).filter(Platform.id_platform == platform_id).first()

    if platform is None:
        raise HTTPException(status_code=404, detail="Piattaforma non trovata")

    db.delete(platform)
    db.commit()


def formatted_output(platform: Platform):
    return {
        "id_platform": platform.id_platform,
        "name": platform.name,
        "is_default": platform.is_default
    }
