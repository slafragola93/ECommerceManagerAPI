"""
Middleware per trasformare automaticamente img_url in API endpoints
"""

import re
import json
from typing import Any, Dict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class ImageUrlTransformerMiddleware(BaseHTTPMiddleware):
    """
    Middleware che trasforma automaticamente img_url in API endpoints
    per abilitare il caching delle immagini
    """
    
    def __init__(self, app, api_prefix: str = "/api/v1/images/product"):
        super().__init__(app)
        self.api_prefix = api_prefix
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Trasforma solo le risposte JSON
        if (response.headers.get("content-type", "").startswith("application/json") and 
            response.status_code == 200):
            
            # Leggi il corpo della risposta
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                # Parse JSON
                data = json.loads(body.decode())
                
                # Trasforma img_url in img_api_url
                transformed_data = self._transform_image_urls(data)
                
                # Ricrea la risposta con i dati trasformati
                new_body = json.dumps(transformed_data, ensure_ascii=False).encode()
                
                return Response(
                    content=new_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="application/json"
                )
                
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Se non è JSON valido, restituisci la risposta originale
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.headers.get("content-type", "application/json")
                )
        
        return response
    
    def _transform_image_urls(self, data: Any) -> Any:
        """
        Trasforma ricorsivamente img_url in img_api_url
        """
        if isinstance(data, dict):
            # Trasforma img_url se presente
            if "img_url" in data and data["img_url"]:
                data["img_api_url"] = self._convert_to_api_url(data["img_url"])
            
            # Ricorsione su tutti i valori del dict
            return {k: self._transform_image_urls(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            # Ricorsione su tutti gli elementi della lista
            return [self._transform_image_urls(item) for item in data]
        
        else:
            # Valori primitivi non modificati
            return data
    
    def _convert_to_api_url(self, img_url: str) -> str:
        """
        Converte img_url in API endpoint
        """
        if not img_url:
            return None
        
        # Pattern per estrarre platform_id e filename
        match = re.match(r'/media/product_images/(\d+)/(.+)', img_url)
        if match:
            platform_id, filename = match.groups()
            return f"{self.api_prefix}/{platform_id}/{filename}"
        
        # Se non matcha il pattern, restituisci l'URL originale
        return img_url
