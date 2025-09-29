from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.auth import get_current_user
from src.models.user import User
from src.services.preventivo_service import PreventivoService
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema,
    PreventivoUpdateSchema,
    PreventivoResponseSchema,
    PreventivoListResponseSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema,
    ConvertiPreventivoSchema
)

router = APIRouter(prefix="/api/v1/preventivi", tags=["Preventivi"])

# Dependency per servizio preventivi
def get_preventivo_service(db: Session = Depends(get_db)) -> PreventivoService:
    return PreventivoService(db)

# Dependency per utente autenticato
user_dependency = Depends(get_current_user)
db_dependency = Depends(get_db)


@router.post("/", response_model=PreventivoResponseSchema, status_code=status.HTTP_201_CREATED,
             response_description="Preventivo creato con successo")
async def create_preventivo(
    preventivo_data: PreventivoCreateSchema,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Crea un nuovo preventivo"""
    try:
        service = get_preventivo_service(db)
        return service.create_preventivo(preventivo_data, user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/", response_model=PreventivoListResponseSchema,
            response_description="Lista preventivi recuperata con successo")
async def get_preventivi(
    page: int = Query(1, ge=1, description="Numero pagina"),
    limit: int = Query(100, ge=1, le=1000, description="Elementi per pagina"),
    search: Optional[str] = Query(None, description="Ricerca per numero, riferimento o note"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Recupera lista preventivi con filtri"""
    try:
        service = get_preventivo_service(db)
        skip = (page - 1) * limit
        
        preventivi = service.get_preventivi(skip, limit, search)
        
        return PreventivoListResponseSchema(
            preventivi=preventivi,
            total=len(preventivi),
            page=page,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/{id_order_document}", response_model=PreventivoResponseSchema,
            response_description="Preventivo recuperato con successo")
async def get_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Recupera preventivo per ID"""
    try:
        service = get_preventivo_service(db)
        preventivo = service.get_preventivo(id_order_document)
        
        if not preventivo:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return preventivo
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.put("/{id_order_document}", response_model=PreventivoResponseSchema,
            response_description="Preventivo aggiornato con successo")
async def update_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    preventivo_data: PreventivoUpdateSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Aggiorna preventivo"""
    try:
        service = get_preventivo_service(db)
        preventivo = service.update_preventivo(id_order_document, preventivo_data, user["id"])
        
        if not preventivo:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return preventivo
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/{id_order_document}/articoli", response_model=ArticoloPreventivoSchema,
             status_code=status.HTTP_201_CREATED, response_description="Articolo aggiunto con successo")
async def add_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    articolo: ArticoloPreventivoSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Aggiunge articolo a preventivo"""
    try:
        service = get_preventivo_service(db)
        result = service.add_articolo(id_order_document, articolo)
        
        if not result:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.put("/{id_order_document}/articoli/{id_order_detail}", response_model=ArticoloPreventivoSchema,
            response_description="Articolo aggiornato con successo")
async def update_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    articolo_data: ArticoloPreventivoUpdateSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Aggiorna articolo in preventivo"""
    try:
        service = get_preventivo_service(db)
        result = service.update_articolo(id_order_detail, articolo_data)
        
        if not result:
            raise HTTPException(status_code=404, detail="Articolo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.delete("/{id_order_document}/articoli/{id_order_detail}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Articolo rimosso con successo")
async def remove_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Rimuove articolo da preventivo"""
    try:
        service = get_preventivo_service(db)
        success = service.remove_articolo(id_order_detail)
        
        if not success:
            raise HTTPException(status_code=404, detail="Articolo non trovato")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/{id_order_document}/converti", status_code=status.HTTP_200_OK,
             response_description="Preventivo convertito in ordine con successo")
async def convert_to_order(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    conversion_data: ConvertiPreventivoSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Converte preventivo in ordine"""
    try:
        service = get_preventivo_service(db)
        result = service.convert_to_order(id_order_document, conversion_data, user["id"])
        
        if not result:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/{id_order_document}/totali", status_code=status.HTTP_200_OK,
            response_description="Totali calcolati con successo")
async def get_totals(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Recupera totali calcolati del preventivo"""
    try:
        service = get_preventivo_service(db)
        totals = service.get_totals(id_order_document)
        
        if not totals:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return totals
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")
