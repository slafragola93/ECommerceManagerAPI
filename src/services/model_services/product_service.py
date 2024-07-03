import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.repository.product_repository import ProductRepository
from src.services.ecommerce_api_service import ECommerceApiService


class ProductService:
    def __init__(self,
                 session: Session
                 ):
        self.ecommerce_api_service = ECommerceApiService(
            api_key=os.environ.get("PRESTASHOP_API_KEY"),
            base_url=os.environ.get("PRESTASHOP_BASE_URL"),
            formatted_output="JSON"
        )
        self.session = session
        self.product_repository = ProductRepository(session)

    def get_live_price(self, product_id: int) -> float:
        # Check se prodotto esiste
        product = self.product_repository.get_by_id(_id=product_id)
        # TODO: Se esiste e l'id origin non è zero, quindi deriva da e commerce esterno
        # (nel caso si volesse modulare dinamicamente la chiamata api verso un X e commerce,
        # identificare la sorgente del prodotto con l'id platform
        if product is not None and product.id_origin != 0:
            price = self.ecommerce_api_service.retrieve_live_price(
                product_id=product.id_origin,
                price_field_name="wholesale_price")
            if not price:
                raise HTTPException(status_code=404, detail="Prezzo live non trovato.")

            return price

        return 0.0
