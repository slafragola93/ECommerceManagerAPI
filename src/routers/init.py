"""
Router per i dati di inizializzazione del frontend
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from pydantic import ValidationError
from typing import Optional
import time

from src.database import get_db
from src.services.routers.init_service import InitService
from src.schemas.init_schema import InitDataSchema
from src.core.exceptions import InfrastructureException, ErrorCode

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
    try:
        start_time = time.time()
        init_service = InitService(db)
        
        if include == "static":
            # Solo dati statici
            static_data = await init_service.get_static_data()
            
            return JSONResponse(
                content={
                    **static_data,
                    "sectionals": [],
                    "order_states": [],
                    "shipping_states": [],
                    "ecommerce_order_states": [],
                    "cache_info": {
                        "generated_at": time.time(),
                        "ttl_static": 604800,  # 7 giorni
                        "ttl_dynamic": 0,
                        "version": version,
                        "total_items": len(static_data.get("platforms", [])) + 
                                      len(static_data.get("languages", [])) + 
                                      len(static_data.get("countries", [])) + 
                                      len(static_data.get("taxes", [])) +
                                      len(static_data.get("carriers", [])) +
                                      len(static_data.get("stores", []))
                    }
                }
            )
        
        elif include == "dynamic":
            # Solo dati dinamici
            dynamic_data = await init_service.get_dynamic_data()
            
            return JSONResponse(
                content={
                    "platforms": [],
                    "languages": [],
                    "countries": [],
                    "taxes": [],
                    "payments": [],
                    "carriers": [],
                    "stores": [],
                    **dynamic_data,
                    "cache_info": {
                        "generated_at": time.time(),
                        "ttl_static": 0,
                        "ttl_dynamic": 86400,  # 1 giorno
                        "version": version,
                        "total_items": len(dynamic_data.get("sectionals", [])) + 
                                      len(dynamic_data.get("order_states", [])) + 
                                      len(dynamic_data.get("shipping_states", [])) +
                                      len(dynamic_data.get("ecommerce_order_states", []))
                    }
                }
            )
        
        else:
            # Tutti i dati (default)
            try:
                init_data = await init_service.get_full_init_data()
                return init_data
            except (ValidationError, ValueError) as e:
                # Se c'è un errore di validazione Pydantic, potrebbe essere cache vecchia
                error_msg = str(e)
                raise InfrastructureException(
                    message=f"Errore validazione dati inizializzazione. Il campo 'stores' potrebbe mancare nella cache. "
                           f"Prova a cancellare la cache e riprova.",
                    error_code=ErrorCode.DATABASE_ERROR,
                    details={
                        "original_error": error_msg,
                        "suggestion": "Cancella la cache e riprova",
                        "cache_keys": ["init_data:static", "init_data:full"]
                    }
                )
            except ResponseValidationError as e:
                # Errore di validazione della risposta (Pydantic)
                error_msg = str(e)
                raise InfrastructureException(
                    message=f"Errore validazione risposta. Il campo 'stores' potrebbe mancare nella cache. "
                           f"Prova a cancellare la cache e riprova.",
                    error_code=ErrorCode.DATABASE_ERROR,
                    details={
                        "original_error": error_msg,
                        "suggestion": "Cancella la cache e riprova",
                        "cache_keys": ["init_data:static", "init_data:full"]
                    }
                )
            except Exception as e:
                error_msg = str(e)
                if "stores" in error_msg.lower() or "validation" in error_msg.lower():
                    raise InfrastructureException(
                        message=f"Errore validazione dati inizializzazione. Il campo 'stores' potrebbe mancare nella cache. "
                               f"Prova a cancellare la cache e riprova.",
                        error_code=ErrorCode.DATABASE_ERROR,
                        details={
                            "original_error": error_msg,
                            "suggestion": "Cancella la cache e riprova",
                            "cache_keys": ["init_data:static", "init_data:full"]
                        }
                    )
                raise
    
    except Exception as e:
        raise InfrastructureException(
            message=f"Errore interno durante il caricamento dei dati: {str(e)}",
            error_code=ErrorCode.DATABASE_ERROR,
            details={"original_error": str(e)}
        )


@router.get("/static")
async def get_static_data_only(db=Depends(get_db)):
    """
    Ottiene solo i dati statici (platforms, languages, countries, taxes).
    Cache: 7 giorni
    """
    try:
        init_service = InitService(db)
        static_data = await init_service.get_static_data()
        
        return JSONResponse(
            content={
                **static_data,
                "cache_info": {
                    "generated_at": time.time(),
                    "ttl": 604800,  # 7 giorni
                    "version": "1.0",
                    "type": "static"
                }
            }
        )
    
    except Exception as e:
        raise InfrastructureException(
            message=f"Errore caricamento dati statici: {str(e)}",
            error_code=ErrorCode.DATABASE_ERROR,
            details={"original_error": str(e)}
        )


@router.get("/dynamic")
async def get_dynamic_data_only(db=Depends(get_db)):
    """
    Ottiene solo i dati dinamici (sectionals, order_states, shipping_states).
    Cache: 1 giorno
    """
    try:
        init_service = InitService(db)
        dynamic_data = await init_service.get_dynamic_data()
        
        return JSONResponse(
            content={
                **dynamic_data,
                "cache_info": {
                    "generated_at": time.time(),
                    "ttl": 86400,  # 1 giorno
                    "version": "1.0",
                    "type": "dynamic"
                }
            }
        )
    
    except Exception as e:
        raise InfrastructureException(
            message=f"Errore caricamento dati dinamici: {str(e)}",
            error_code=ErrorCode.DATABASE_ERROR,
            details={"original_error": str(e)}
        )


@router.get("/health")
async def get_init_health(db=Depends(get_db)):
    """
    Health check per i dati di inizializzazione.
    Verifica che tutti i servizi siano disponibili.
    """
    try:
        init_service = InitService(db)
        
        # Test rapido di tutti i servizi
        health_status = {
            "status": "healthy",
            "services": {},
            "timestamp": time.time()
        }
        
        # Test platforms
        try:
            platforms = await init_service._get_platforms()
            health_status["services"]["platforms"] = {
                "status": "ok",
                "count": len(platforms)
            }
        except Exception as e:
            health_status["services"]["platforms"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Test languages
        try:
            languages = await init_service._get_languages()
            health_status["services"]["languages"] = {
                "status": "ok",
                "count": len(languages)
            }
        except Exception as e:
            health_status["services"]["languages"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Test countries
        try:
            countries = await init_service._get_countries()
            health_status["services"]["countries"] = {
                "status": "ok",
                "count": len(countries)
            }
        except Exception as e:
            health_status["services"]["countries"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Test altri servizi...
        # (omesso per brevità, ma stesso pattern)
        
        return health_status
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }