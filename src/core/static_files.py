"""
Cached StaticFiles per servire file statici con cache headers
"""
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send


class CachedStaticFiles(StaticFiles):
    """StaticFiles con cache headers per le immagini e altri file statici"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Override per aggiungere cache headers alle risposte"""
        
        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                
                # Aggiungi cache headers per file statici
                # Cache per 1 anno (31536000 secondi) - appropriato per immagini immutabili
                headers[b"cache-control"] = b"public, max-age=31536000, immutable"
                headers[b"expires"] = b"Thu, 31 Dec 2025 23:59:59 GMT"
                
                # Aggiungi ETag se non presente (utile per validazione cache)
                if b"etag" not in headers:
                    # ETag basato sul path (può essere migliorato con hash del file)
                    etag = f'"{hash(scope.get("path", ""))}"'.encode()
                    headers[b"etag"] = etag
                
                message["headers"] = list(headers.items())
            
            await send(message)
        
        await super().__call__(scope, receive, send_wrapper)

