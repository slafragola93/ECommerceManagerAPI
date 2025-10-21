"""
Router per i dati di inizializzazione del frontend
"""

from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional, List
import time

from src.database import get_db
from src.services.routers.init_service import InitService
from src.schemas.init_schema import InitDataSchema

router = APIRouter(
    prefix="/api/v1/init",
    tags=["Initialization"]
)

@router.get("/", response_model=InitDataSchema)
async def get_init_data(
    include: Optional[str] = Query("all", description="Dati da includere (static,dynamic,all)"),
    version: Optional[str] = Query("1.0", description="Versione dei dati"),
    db=Depends(get_db)
):
    """
    Ottiene i dati di inizializzazione per il frontend.
    
    - **include**: Specifica quali dati includere
      - `static`: Solo dati statici (platforms, languages, countries, taxes)
      - `dynamic`: Solo dati dinamici (sectionals, order_states, shipping_states)
      - `all`: Tutti i dati (default)
    - **version**: Versione dei dati richiesta
    
    Returns:
        InitDataSchema: Dati di inizializzazione completi
    """
    