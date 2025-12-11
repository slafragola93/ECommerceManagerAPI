"""
Product Repository rifattorizzato seguendo SOLID
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, noload
from sqlalchemy import func, desc, text, or_
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
            
            # Filtro per nome prodotto (ricerca parziale, case-insensitive)
            # Cerca in name, sku e reference (almeno 4 caratteri richiesti)
            product_name = filters.get('product_name')
            if product_name and len(product_name) >= 4:
                search_term = f"%{product_name}%"
                query = query.filter(
                    or_(
                        Product.name.ilike(search_term),
                        Product.sku.ilike(search_term),
                        Product.reference.ilike(search_term)
                    )
                )
            
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
            
            # Applica gli stessi filtri del get_all per conteggio corretto
            product_name = filters.get('product_name')
            if product_name and len(product_name) >= 4:
                search_term = f"%{product_name}%"
                query = query.filter(
                    or_(
                        Product.name.ilike(search_term),
                        Product.sku.ilike(search_term),
                        Product.reference.ilike(search_term)
                    )
                )
            
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
                    price=data.price if data.price is not None else 0.0,
                    quantity=data.quantity if data.quantity is not None else 0,
                    purchase_price=data.purchase_price if data.purchase_price is not None else 0.0,
                    minimal_quantity=data.minimal_quantity if data.minimal_quantity is not None else 0
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
            price=data.price if data.price is not None else 0.0,
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
            price_map: Dizionario {id_origin: price} mappando id_origin a nuovo prezzo
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
                SET price = :price 
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

    def bulk_update_product_details(self, details_map: Dict[int, Dict[str, Any]], id_platform: int, batch_size: int = 5000) -> int:
        """
        Aggiorna i dettagli dei prodotti in batch utilizzando SQL diretto per performance ottimizzata.
        
        Aggiorna: sku, reference, weight, depth, height, width, purchase_price, 
        minimal_quantity, price, quantity.
        
        Usa batch processing con commit ogni N batch per ridurre I/O.
        
        Args:
            details_map: Dizionario {id_origin: {sku, reference, weight, ...}} con tutti i dettagli
            id_platform: ID della piattaforma per filtrare i prodotti
            batch_size: Dimensione del batch per l'aggiornamento (default: 5000)
            
        Returns:
            int: Numero di prodotti aggiornati
        """
        if not details_map:
            print("DEBUG: No product details to update, details_map is empty")
            return 0
        
        try:
            total_updated = 0
            items = list(details_map.items())
            
            # SQL statement per l'update - usa parametri per prepared statement
            stmt = text("""
                UPDATE products 
                SET 
                    sku = :sku,
                    reference = :reference,
                    weight = :weight,
                    depth = :depth,
                    height = :height,
                    width = :width,
                    purchase_price = :purchase_price,
                    minimal_quantity = :minimal_quantity,
                    price = :price,
                    quantity = :quantity
                WHERE id_origin = :id_origin AND id_platform = :id_platform
            """)
            
            # Processa in batch per evitare transazioni troppo lunghe
            # Commit ogni 3 batch per ridurre I/O (performance optimization)
            commit_interval = 3
            batch_count = 0
            
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                batch_updated = 0
                
                # Esegui ogni update nel batch
                for id_origin, details in batch:
                    try:
                        # Estrai valori con default sicuri
                        result = self._session.execute(stmt, {
                            'id_origin': id_origin,
                            'sku': str(details.get('sku', '') or '')[:32],
                            'reference': str(details.get('reference', 'ND') or 'ND')[:64],
                            'weight': float(details.get('weight', 0.0) or 0.0),
                            'depth': float(details.get('depth', 0.0) or 0.0),
                            'height': float(details.get('height', 0.0) or 0.0),
                            'width': float(details.get('width', 0.0) or 0.0),
                            'purchase_price': float(details.get('purchase_price', 0.0) or 0.0),
                            'minimal_quantity': int(details.get('minimal_quantity', 0) or 0),
                            'price': float(details.get('price', 0.0) or 0.0),
                            'quantity': int(details.get('quantity', 0) or 0),
                            'id_platform': id_platform
                        })
                        if result.rowcount > 0:
                            batch_updated += result.rowcount
                    except Exception as e:
                        print(f"DEBUG: Error updating product details id_origin={id_origin}: {str(e)}")
                        continue
                
                batch_count += 1
                total_updated += batch_updated
                
                # Commit ogni N batch invece che ogni batch (performance optimization)
                if batch_count % commit_interval == 0 or i + batch_size >= len(items):
                    self._session.commit()
                    print(f"DEBUG: Updated batch {batch_count}: {batch_updated} products (total: {total_updated})")
            
            # Final commit per sicurezza
            if batch_count % commit_interval != 0:
                self._session.commit()
            
            print(f"DEBUG: Total products details updated: {total_updated} out of {len(details_map)} in details_map")
            return total_updated
            
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(f"Database error updating product details: {str(e)}")

    def get_products_images_map(self, product_ids: List[int]) -> Dict[int, str]:
        """
        Recupera img_url per una lista di product_ids in batch.
        
        Args:
            product_ids: Lista di ID prodotti
            
        Returns:
            Dictionary {id_product: img_url}, con fallback se img_url è None
        """
        try:
            if not product_ids:
                return {}
            
            # Query ottimizzata: seleziona solo i campi necessari
            products = self._session.query(Product.id_product, Product.img_url).filter(
                Product.id_product.in_(product_ids)
            ).all()
            
            # Fallback image URL
            fallback_img_url = "media/product_images/fallback/product_not_found.jpg"
            
            # Crea mapping con fallback per img_url mancanti
            return {
                product.id_product: product.img_url if product.img_url else fallback_img_url
                for product in products
            }
        except Exception as e:
            raise InfrastructureException(f"Database error retrieving product images: {str(e)}")
    
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