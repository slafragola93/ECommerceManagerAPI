"""
Middleware per il logging centralizzato degli errori
"""
import logging
import time
import traceback
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

logger = logging.getLogger(__name__)

class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware per il logging centralizzato degli errori e delle richieste
    """
    
    def __init__(self, app, log_requests: bool = True, log_responses: bool = False):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercetta le richieste e le risposte per il logging"""
        
        # Log della richiesta in arrivo
        start_time = time.time()
        request_id = id(request)
        
        if self.log_requests:
            logger.info(
                f"Request started: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                }
            )
        
        try:
            # Esegui la richiesta
            response = await call_next(request)
            
            # Calcola il tempo di risposta
            process_time = time.time() - start_time
            
            # Log della risposta
            if self.log_responses:
                logger.info(
                    f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "process_time": process_time,
                    }
                )
            
            # Aggiungi header con tempo di processamento
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = str(request_id)
            
            return response
            
        except Exception as exc:
            # Calcola il tempo di processamento anche in caso di errore
            process_time = time.time() - start_time
            
            # Log dell'errore
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {type(exc).__name__}: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "process_time": process_time,
                    "traceback": traceback.format_exc(),
                },
                exc_info=True
            )
            
            # Rilancia l'eccezione per essere gestita dagli exception handler
            raise exc

class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware per il logging delle performance
    """
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitora le performance delle richieste"""
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log delle richieste lente
            if process_time > self.slow_request_threshold:
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "process_time": process_time,
                        "threshold": self.slow_request_threshold,
                        "status_code": response.status_code,
                    }
                )
            
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            
            # Log anche gli errori con tempo di processamento
            logger.error(
                f"Request error with timing: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time": process_time,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            
            raise exc

class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware per il logging di eventi di sicurezza
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitora eventi di sicurezza"""
        
        # Log tentativi di accesso a endpoint sensibili
        sensitive_paths = ["/api/v1/auth/", "/api/v1/admin/", "/api/v1/cache"]
        if any(path in request.url.path for path in sensitive_paths):
            logger.info(
                f"Access to sensitive endpoint: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                    "referer": request.headers.get("referer"),
                }
            )
        
        # Log richieste con status code di errore
        try:
            response = await call_next(request)
            
            if response.status_code >= 400:
                logger.warning(
                    f"Error response: {request.method} {request.url.path} - {response.status_code}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "client_ip": request.client.host if request.client else None,
                    }
                )
            
            return response
            
        except Exception as exc:
            # Log errori di sicurezza
            logger.error(
                f"Security-related error: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "client_ip": request.client.host if request.client else None,
                }
            )
            
            raise exc
