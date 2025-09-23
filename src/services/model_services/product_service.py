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

        if product is not None and product.id_origin != 0:
            price = self.ecommerce_api_service.get_product_value(
                product_id=product.id_origin,
                price_field_name="wholesale_price")
            if not price:
                raise HTTPException(status_code=404, detail="Prezzo live non trovato.")

            return price

        return 0.0

    def get_live_weight(self, product_id:int) -> float:
        product = self.product_repository.get_by_id(_id=product_id)
        if product is not None and product.id_origin != 0:
            weight = self.ecommerce_api_service.get_product_value(
                product_id=product.id_origin,
                price_field_name="weight")
            if not weight:
                raise HTTPException(status_code=404, detail="Peso live non trovato.")

            return weight

        return 0.0
