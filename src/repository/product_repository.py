"""
Product Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc
from src.models.product import Product
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.schemas.product_schema import ProductSchema
from src.services import QueryUtils

class ProductRepository(BaseRepository[Product, int], IProductRepository):
    """Product Repository rifattorizzato seguendo SOLID"""
    
    def __init__(self, session: Session):
        super().__init__(session, Product)
    
    def get_all(self, **filters) -> List[Product]:
        """Ottiene tutte le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class).order_by(desc(Product.id_product))
            
            # Paginazione
            page = filters.get('page', 1)
            limit = filters.get('limit', 100)
            offset = self.get_offset(limit, page)
            
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving {self._model_class.__name__} list: {str(e)}")
    
    def get_count(self, **filters) -> int:
        """Conta le entità con filtri opzionali"""
        try:
            query = self._session.query(self._model_class)
            return query.count()
        except Exception as e:
            raise InfrastructureException(f"Database error counting {self._model_class.__name__}: {str(e)}")
    
    def get_by_name(self, name: str) -> Optional[Product]:
        """Ottiene un product per nome (case insensitive)"""
        try:
            return self._session.query(Product).filter(
                func.lower(Product.name) == func.lower(name)
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving product by name: {str(e)}")
    
    def get_by_origin_id(self, origin_id: str) -> Optional[Product]:
        """Ottiene un prodotto per origin ID"""
        try:
            return self._session.query(Product).filter(
                Product.id_origin == origin_id
            ).first()
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving product by origin ID: {str(e)}")
    
    def bulk_create(self, data_list: list[ProductSchema], batch_size: int = 1000):
        """Bulk insert products for better performance"""
        # Get existing origin IDs to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_products = self._session.query(Product).filter(Product.id_origin.in_(origin_ids)).all()
        existing_origin_ids = {str(product.id_origin) for product in existing_products}
        
        # Filter out existing products
        new_products_data = [data for data in data_list if str(data.id_origin) not in existing_origin_ids]
        
        if not new_products_data:
            return 0
        
        # Process in batches
        total_inserted = 0
        for i in range(0, len(new_products_data), batch_size):
            batch = new_products_data[i:i + batch_size]
            products = []
            
            for data in batch:
                product = Product(**data.model_dump())
                products.append(product)
            
            self._session.bulk_save_objects(products)
            total_inserted += len(products)
            
            # Commit every batch
            self._session.commit()
            
        return total_inserted

    def create(self, data: ProductSchema):
        product = Product(**data.model_dump())

        self._session.add(product)
        self._session.commit()
        self._session.refresh(product)

    def update(self, edited_product: Product, data: ProductSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_product, key) and value is not None:
                setattr(edited_product, key, value)

        self._session.add(edited_product)
        self._session.commit()

    def delete(self, product: Product) -> bool:
        self._session.delete(product)
        self._session.commit()

        return True

    @staticmethod
    def formatted_output(product: Product,
                         category_id_origin: int,
                         category_name: str,
                         brand_name: str,
                         brand_id_origin: int
                         ):
        return {
            "id_product": product.id_product,
            "id_origin": product.id_origin,
            "name": product.name,
            "sku": product.sku,
            "reference": product.reference,
            "type": product.type,
            "weight": product.weight,
            "depth": product.depth,
            "height": product.height,
            "width": product.width,
            "category": {
                "id_category": product.id_category,  # Assumi che tu abbia l'ID disponibile qui
                "id_origin": category_id_origin,
                "name": category_name
            },
            "brand": {
                "id_brand": product.id_brand,  # Assumi che tu abbia l'ID disponibile qui
                "id_origin": brand_id_origin,
                "name": brand_name
            }
        }