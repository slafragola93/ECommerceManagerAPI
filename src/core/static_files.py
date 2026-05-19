"""
Cached StaticFiles per servire file statici con cache headers
"""
from starlette.exceptions import HTTPException
from starlette.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

# Path RELATIVO alla directory montata (es. "media") per il placeholder immagini prodotto.
# Convenzione: mount su "media", placeholder in "media/product_images/fallback/...".
FALLBACK_PRODUCT_IMAGE_REL_PATH = "product_images/fallback/product_not_found.jpg"
PRODUCT_IMAGES_PREFIX = "product_images/"


class CachedStaticFiles(StaticFiles):
    """StaticFiles con cache headers e fallback automatico per immagini prodotto."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope: Scope) -> Response:
        """
        Restituisce la risposta per il path richiesto.

        Se un file sotto `product_images/` non esiste, evita il 404 servendo
        il placeholder. In questo modo il frontend non rompe il layout quando
        la sync delle immagini non è ancora avvenuta (es. errori di rete verso
        l'ecommerce sorgente).
        """
        normalized = path.replace("\\", "/").lstrip("/")
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            # Fallback solo per i 404 sulle immagini prodotto e solo se non
            # stiamo già richiedendo il fallback stesso (evita loop).
            if (
                exc.status_code == 404
                and normalized.startswith(PRODUCT_IMAGES_PREFIX)
                and not normalized.endswith(FALLBACK_PRODUCT_IMAGE_REL_PATH.split("/")[-1])
            ):
                try:
                    response = await super().get_response(FALLBACK_PRODUCT_IMAGE_REL_PATH, scope)
                except HTTPException:
                    # Se anche il fallback manca, rilancia il 404 originale
                    raise exc
                # Marcatore letto da send_wrapper per applicare cache headers
                # meno aggressivi (il vero file potrebbe arrivare in futuro).
                scope["_static_fallback_served"] = True
                return response
            raise

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Override per aggiungere cache headers alle risposte 2xx."""

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                is_fallback = bool(scope.get("_static_fallback_served"))

                if is_fallback:
                    # Cache breve e revalidate: quando la sync produrrà il vero
                    # file, i client lo otterranno entro pochi minuti.
                    headers[b"cache-control"] = b"public, max-age=60, must-revalidate"
                    headers.pop(b"expires", None)
                else:
                    # Cache per 1 anno - immagini immutabili.
                    headers[b"cache-control"] = b"public, max-age=31536000, immutable"
                    headers[b"expires"] = b"Thu, 31 Dec 2025 23:59:59 GMT"

                if b"etag" not in headers:
                    etag = f'"{hash(scope.get("path", ""))}"'.encode()
                    headers[b"etag"] = etag

                message["headers"] = list(headers.items())

            await send(message)

        await super().__call__(scope, receive, send_wrapper)

