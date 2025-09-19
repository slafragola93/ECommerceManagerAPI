from fastapi import HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .. import Brand, Category
from ..models import Product
from src.schemas.product_schema import *
from src.services import QueryUtils
from ..routers.dependencies import LIMIT_DEFAULT


class ProductRepository:
    """
    Repository clienti
    """

    def __init__(self, session: Session):
        """
        Inizializza la repository con la sessione del DB

        Args:
            session (Session): Sessione del DB
        """
        self.session = session

    def get_all(self,
                categories_ids: Optional[str] = None,
                brands_ids: Optional[str] = None,
                product_name: Optional[str] = None,
                products_ids: Optional[str] = None,
                sku: Optional[str] = None,
                page: int = 1, limit: int = LIMIT_DEFAULT
                ) -> AllProductsResponseSchema:

        query = self.session.query(Product,
                                   Brand.name.label("brand_name"),
                                   Brand.id_origin.label("brand_id_origin"),
                                   Category.name.label("category_name"),
                                   Category.id_origin.label("category_id_origin")

                                   ).order_by(desc(Product.id_product)) \
            .outerjoin(Brand, Product.id_brand == Brand.id_brand) \
            .outerjoin(Category, Product.id_category == Category.id_category)

        try:
            query = QueryUtils.filter_by_id(query, Product, 'id_category', categories_ids)
            query = QueryUtils.filter_by_id(query, Product, 'id_brand', brands_ids)
            query = QueryUtils.filter_by_id(query, Product, 'id_product', products_ids)

            query = QueryUtils.filter_by_string(query, Product, 'name', product_name)
            query = QueryUtils.filter_by_string(query, Product, 'sku', sku)


        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        products_result = query.offset(QueryUtils.get_offset(limit, page)).limit(limit).all()

        return products_result

    def get_count(self,
                  categories_ids: Optional[str] = None,
                  brands_ids: Optional[str] = None,
                  product_name: Optional[str] = None,
                  products_ids: Optional[str] = None,
                  sku: Optional[str] = None
                ) -> int:

        query = self.session.query(func.count(Product.id_product)) \
            .join(Brand, Product.id_brand == Brand.id_brand) \
            .join(Category, Product.id_category == Category.id_category)

        try:
            query = QueryUtils.filter_by_id(query, Product, 'id_category', categories_ids)
            query = QueryUtils.filter_by_id(query, Product, 'id_brand', brands_ids)
            query = QueryUtils.filter_by_id(query, Product, 'id_product', products_ids)

            query = QueryUtils.filter_by_string(query, Product, 'name', product_name)
            query = QueryUtils.filter_by_string(query, Product, 'sku', sku)

        except ValueError:
            raise HTTPException(status_code=400, detail="Parametri di ricerca non validi")

        total_count = query.scalar()

        return total_count

    def get_by_id_complete(self, _id: int) -> ProductResponseSchema:
        product = self.session.query(
            Product,
            Brand.name.label("brand_name"),
            Brand.id_origin.label("brand_id_origin"),
            Category.name.label("category_name"),
            Category.id_origin.label("category_id_origin")
        ).outerjoin(Brand, Product.id_brand == Brand.id_brand) \
            .outerjoin(Category, Product.id_category == Category.id_category) \
            .filter(Product.id_product == _id) \
            .first()
        return product

    def get_by_id(self, _id: int) -> Product:
        return self.session.query(Product).filter(Product.id_product == _id).first()
    
    def get_by_origin_id(self, origin_id: str) -> Product:
        """Get product by origin ID"""
        return self.session.query(Product).filter(Product.id_origin == origin_id).first()

    def bulk_create(self, data_list: list[ProductSchema], batch_size: int = 1000):
        """Bulk insert products for better performance"""
        # Get existing origin IDs to avoid duplicates
        origin_ids = [str(data.id_origin) for data in data_list]
        existing_products = self.session.query(Product).filter(Product.id_origin.in_(origin_ids)).all()
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
            
            self.session.bulk_save_objects(products)
            total_inserted += len(products)
            
            # Commit every batch
            self.session.commit()
            
        return total_inserted

    def create(self, data: ProductSchema):
        product = Product(**data.model_dump())

        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)

    def update(self, edited_product: Product, data: ProductSchema):

        entity_updated = data.dict(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_product, key) and value is not None:
                setattr(edited_product, key, value)

        self.session.add(edited_product)
        self.session.commit()

    def delete(self, product: Product) -> bool:
        self.session.delete(product)
        self.session.commit()

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
            "id_image": product.id_image,
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
