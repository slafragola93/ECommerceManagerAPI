"""
Product Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc, text
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
                # Converti 0 a None per le foreign key se necessario
                id_category = data.id_category if data.id_category and data.id_category > 0 else None
                id_brand = data.id_brand if data.id_brand and data.id_brand > 0 else None
                
                product = Product(
                    id_origin=data.id_origin if data.id_origin and data.id_origin > 0 else 0,
                    id_category=id_category,
                    id_brand=id_brand,
                    id_platform=data.id_platform if data.id_platform is not None else 0,
                    img_url=data.img_url,
                    name=data.name,
                    sku=data.sku,
                    reference=data.reference,
                    type=data.type,
                    weight=data.weight,
                    depth=data.depth,
                    height=data.height,
                    width=data.width,
                    price_without_tax=data.price_without_tax if data.price_without_tax is not None else 0.0,
                    quantity=data.quantity if data.quantity is not None else 0
                )
                products.append(product)
            
            self._session.bulk_save_objects(products)
            total_inserted += len(products)
            
            # Commit every batch
            self._session.commit()
            
        return total_inserted

    def create(self, data: ProductSchema):
        # Crea il prodotto usando i campi specifici
        # Converti 0 a None per le foreign key se necessario
        id_category = data.id_category if data.id_category and data.id_category > 0 else None
        id_brand = data.id_brand if data.id_brand and data.id_brand > 0 else None
        
        product = Product(
            id_origin=data.id_origin if data.id_origin and data.id_origin > 0 else 0,
            id_category=id_category,
            id_brand=id_brand,
            id_platform=data.id_platform if data.id_platform is not None else 0,
            img_url=data.img_url,
            name=data.name,
            sku=data.sku,
            reference=data.reference,
            type=data.type,
            weight=data.weight,
            depth=data.depth,
            height=data.height,
            width=data.width,
            price_without_tax=data.price_without_tax if data.price_without_tax is not None else 0.0,
            quantity=data.quantity if data.quantity is not None else 0
        )

        self._session.add(product)
        self._session.commit()
        self._session.refresh(product)
        return product

    def update(self, edited_product: Product, data: ProductSchema):

        entity_updated = data.model_dump(exclude_unset=True)  # Esclude i campi non impostati

        for key, value in entity_updated.items():
            if hasattr(edited_product, key) and value is not None:
                # Gestione speciale per le foreign key
                if key in ['id_category', 'id_brand']:
                    # Converti 0 a None per le foreign key
                    if value == 0:
                        setattr(edited_product, key, None)
                    else:
                        setattr(edited_product, key, value)
                else:
                    setattr(edited_product, key, value)

        self._session.add(edited_product)
        self._session.commit()
        return edited_product

    def delete(self, product: Product) -> bool:
        self._session.delete(product)
        self._session.commit()

        return True

    def bulk_update_quantity(self, quantity_map: Dict[int, int], id_platform: int, batch_size: int = 1000) -> int:
        """
        Aggiorna le quantità dei prodotti in batch utilizzando SQL diretto per performance.
        
        Args:
            quantity_map: Dizionario {id_origin: quantity} mappando id_origin a nuova quantità
            id_platform: ID della piattaforma per filtrare i prodotti
            batch_size: Dimensione del batch per l'aggiornamento (default: 1000)
            
        Returns:
            int: Numero di prodotti aggiornati
        """
        if not quantity_map:
            print("DEBUG: No quantities to update, quantity_map is empty")
            return 0
        
        try:
            total_updated = 0
            items = list(quantity_map.items())
            
            # SQL statement per l'update
            stmt = text("""
                UPDATE products 
                SET quantity = :quantity 
                WHERE id_origin = :id_origin AND id_platform = :id_platform
            """)
            
            # Processa in batch per evitare transazioni troppo lunghe
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                batch_updated = 0
                
                # Esegui ogni update singolarmente nel batch
                for id_origin, quantity in batch:
                    try:
                        result = self._session.execute(stmt, {
                            'id_origin': id_origin,
                            'quantity': quantity,
                            'id_platform': id_platform
                        })
                        if result.rowcount > 0:
                            batch_updated += result.rowcount
                    except Exception as e:
                        print(f"DEBUG: Error updating product id_origin={id_origin}: {str(e)}")
                        continue
                
                # Commit dopo ogni batch
                self._session.commit()
                total_updated += batch_updated
                
                print(f"DEBUG: Updated batch {i // batch_size + 1}: {batch_updated} products")
            
            print(f"DEBUG: Total products updated: {total_updated} out of {len(quantity_map)} in quantity_map")
            return total_updated
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating product quantities: {str(e)}")

    def bulk_update_price(self, price_map: Dict[int, float], id_platform: int, batch_size: int = 1000) -> int:
        """
        Aggiorna i prezzi dei prodotti in batch utilizzando SQL diretto per performance.
        
        Args:
            price_map: Dizionario {id_origin: price} mappando id_origin a nuovo prezzo (wholesale_price -> price_without_tax)
            id_platform: ID della piattaforma per filtrare i prodotti
            batch_size: Dimensione del batch per l'aggiornamento (default: 1000)
            
        Returns:
            int: Numero di prodotti aggiornati
        """
        if not price_map:
            print("DEBUG: No prices to update, price_map is empty")
            return 0
        
        try:
            total_updated = 0
            items = list(price_map.items())
            
            # SQL statement per l'update
            stmt = text("""
                UPDATE products 
                SET price_without_tax = :price 
                WHERE id_origin = :id_origin AND id_platform = :id_platform
            """)
            
            # Processa in batch per evitare transazioni troppo lunghe
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                batch_updated = 0
                
                # Esegui ogni update singolarmente nel batch
                for id_origin, price in batch:
                    try:
                        result = self._session.execute(stmt, {
                            'id_origin': id_origin,
                            'price': float(price),
                            'id_platform': id_platform
                        })
                        if result.rowcount > 0:
                            batch_updated += result.rowcount
                    except Exception as e:
                        print(f"DEBUG: Error updating product price id_origin={id_origin}: {str(e)}")
                        continue
                
                # Commit dopo ogni batch
                self._session.commit()
                total_updated += batch_updated
                
            
            print(f"DEBUG: Total products prices updated: {total_updated} out of {len(price_map)} in price_map")
            return total_updated
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating product prices: {str(e)}")

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