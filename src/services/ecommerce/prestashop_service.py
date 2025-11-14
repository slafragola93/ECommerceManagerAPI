"""
PrestaShop synchronization service
"""

from typing import Dict, List, Any, Optional
from fastapi.datastructures import Address
from sqlalchemy.orm import Session
from sqlalchemy import text
import base64
import asyncio
from datetime import datetime
import os
from src.schemas.order_schema import OrderUpdateSchema
from src.services.core.tool import safe_int, safe_float, sql_value
from src.services.external.province_service import province_service
from src.services.media.image_service import ImageService
from src.services.media.image_cache_service import get_image_cache_service
from src.repository.customer_repository import CustomerRepository
from src.schemas.customer_schema import CustomerSchema
from .base_ecommerce_service import BaseEcommerceService


class PrestaShopService(BaseEcommerceService):
    """
    PrestaShop synchronization service implementation
    """
    
    def __init__(
        self, 
        db: Session, 
        platform_id: int = 1, 
        batch_size: int = 5000, 
        max_concurrent_requests: int = 10,  # Original value
        default_language_id: int = 1,
        new_elements: bool = True
        ):
        super().__init__(db, platform_id, batch_size)
        self.max_concurrent_requests = max_concurrent_requests
        self._semaphore = None  # Will be initialized in async context
        self.default_language_id = default_language_id
        self.new_elements = new_elements
        self.image_service = ImageService()
        self.image_cache_service = None  # Inizializzato lazy
        self._product_data_for_images = []  # Store product data for image synchronization
        self._original_products_data = []  # Store original PrestaShop data for images
        self.max_concurrent_images = 50  # Massima concorrenza per download immagini
        
    async def _get_image_cache_service(self):
        """Inizializza lazy il servizio di cache delle immagini"""
        if self.image_cache_service is None:
            self.image_cache_service = await get_image_cache_service()
        return self.image_cache_service
    
    async def _warm_up_image_cache(self):
        """Warm-up della cache per le immagini appena sincronizzate"""
        try:
            cache_service = await self._get_image_cache_service()
            
            # Ottieni i prodotti con immagini per questa piattaforma
            
            query_sql = f"""
                SELECT id_origin FROM products 
                WHERE img_url IS NOT NULL 
                AND img_url LIKE '/media/product_images/{self.platform_id}/%'
                ORDER BY id_product DESC
                LIMIT 100
            """
            products_query = self.db.execute(text(query_sql)).fetchall()
            
            if products_query:
                product_ids = [p.id_origin for p in products_query]
                print(f"🔥 Warm-up cache per {len(product_ids)} immagini")
                
                # Pre-carica i metadati in batch
                await cache_service.warm_cache_for_products(
                    self.platform_id, 
                    product_ids, 
                    batch_size=50
                )
                
                print(f"✅ Cache warm-up completato per {len(product_ids)} immagini")
            
        except Exception as e:
            print(f"⚠️ Errore durante warm-up cache: {e}")
            # Non bloccare la sincronizzazione per errori di cache
    
    def configure_image_performance(self, max_concurrent: int = 50, quality: int = 15, max_size: tuple = (400, 300)):
        """
        Configura i parametri di performance per il download delle immagini.
        
        Args:
            max_concurrent: Numero massimo di download concorrenti
            quality: Qualità JPEG (1-100, più basso = più veloce)
            max_size: Dimensioni massime (width, height)
        """
        self.max_concurrent_images = max_concurrent
        self.image_service.configure_performance(quality, max_size)
    
    def _update_product_img_urls(self, product_data_list: list, original_products_data: list):
        """
        Aggiorna img_url per i prodotti inseriti che hanno immagini.
        Aggiorna solo i prodotti che hanno immagini e che non hanno già img_url impostato.
        
        Args:
            product_data_list: Lista di ProductSchema inseriti
            original_products_data: Lista di dati originali da PrestaShop
        """
        try:
            from src.repository.product_repository import ProductRepository
            from src.models.product import Product
            
            
            product_repo = ProductRepository(self.db)
            
            # Crea mapping tra id_origin e dati originali
            origin_to_original = {}
            for i, product_data in enumerate(product_data_list):
                if i < len(original_products_data):
                    origin_to_original[product_data.id_origin] = original_products_data[i]
            
            # Trova i prodotti che hanno immagini e aggiorna img_url
            # Prima devo ottenere gli ID locali dei prodotti inseriti
            origin_ids = [str(product_data.id_origin) for product_data in product_data_list]
            
            products_query = product_repo._session.query(Product.id_product, Product.id_origin, Product.img_url).filter(Product.id_origin.in_(origin_ids)).all()
            origin_to_local_id = {str(product.id_origin): (product.id_product, product.img_url) for product in products_query}
            
            products_to_update = []
            for product_data in product_data_list:
                original_data = origin_to_original.get(product_data.id_origin)
                if original_data:
                    id_image_default = original_data.get('id_default_image', 0)
                    if id_image_default and int(id_image_default) > 0:
                        # Usa l'ID locale del database per il percorso dell'immagine
                        local_info = origin_to_local_id.get(str(product_data.id_origin))
                        if local_info:
                            local_id, current_img_url = local_info
                            # Aggiorna solo se non ha già img_url o se è diverso
                            expected_img_url = f"/media/product_images/{self.platform_id}/product_{local_id}.jpg"
                            if not current_img_url or current_img_url != expected_img_url:
                                products_to_update.append({
                                    'id_product': local_id,
                                    'img_url': expected_img_url
                                })
                                print(f"DEBUG: Will update img_url for product {local_id} (origin: {product_data.id_origin})")
            
            # Aggiorna img_url per i prodotti che hanno immagini
            if products_to_update:
                for update_data in products_to_update:
                    product_repo._session.execute(
                        text("UPDATE products SET img_url = :img_url WHERE id_product = :id_product"),
                        update_data
                    )
                product_repo._session.commit()
            
        except Exception as e:
            print(f"DEBUG: Error updating product img_urls: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def force_update_product_img_url(self, product_id: int):
        """
        Forza l'aggiornamento di img_url per un prodotto specifico.
        Utile per recuperare immagini mancanti.
        
        Args:
            product_id: ID locale del prodotto da aggiornare
        """
        try:
            from src.repository.product_repository import ProductRepository
            
            
            product_repo = ProductRepository(self.db)
            
            # Genera il nuovo img_url
            img_url = f"/media/product_images/{self.platform_id}/product_{product_id}.jpg"
            
            # Aggiorna il prodotto
            product_repo._session.execute(
                text("UPDATE products SET img_url = :img_url WHERE id_product = :id_product"),
                {'id_product': product_id, 'img_url': img_url}
            )
            product_repo._session.commit()
            
            print(f"DEBUG: Force updated img_url for product {product_id}: {img_url}")
            return True
            
        except Exception as e:
            print(f"DEBUG: Error force updating product {product_id} img_url: {str(e)}")
            return False

    def _get_one_year_ago_date(self) -> str:
        """Get date string for one year ago in YYYY-MM-DD format"""
        from datetime import timedelta
        one_year_ago = datetime.now() - timedelta(days=365)  # 1 year
        return one_year_ago.strftime('%Y-%m-%d')
    
    def _parse_prestashop_datetime(self, date_string: str) -> Optional[datetime]:
        """
        Parse PrestaShop datetime string to Python datetime object
        Handles various PrestaShop datetime formats
        """
        if not date_string:
            return None
            
        try:
            # PrestaShop typically uses format: "2024-01-15 14:30:25" or "2024-01-15"
            if ' ' in date_string:
                # Full datetime format
                return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
            else:
                # Date only format - convert to datetime with current time
                date_part = datetime.strptime(date_string, '%Y-%m-%d')
                return datetime.combine(date_part.date(), datetime.now().time())
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse datetime '{date_string}': {e}")
            return datetime.now()  # Fallback to current datetime
    
    def _get_date_range_filter(self) -> str:
        """Get date range filter string for PrestaShop API [start_date,end_date]"""
        from datetime import timedelta
        one_year_ago = datetime.now() - timedelta(days=365)  # 1 year ago
        today = datetime.now()
        
        start_date = one_year_ago.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
        date_range = f"[{start_date},{end_date}]"
        return date_range
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get PrestaShop authentication headers"""
        # PrestaShop uses Basic Auth with API key
        credentials = f"{self.api_key}:"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Output-Format': 'JSON'
        }
    
    async def _make_request_with_rate_limit(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting to prevent server overload
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            API response data
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        async with self._semaphore:
            # Add small delay to be gentle with the server
            await asyncio.sleep(0.1)
            try:
                return await self._make_request(endpoint, params)
            except Exception as e:
                # If we get a file descriptor error, wait a bit longer before retrying
                if "too many file descriptors" in str(e).lower():
                    print(f"DEBUG: File descriptor limit reached, waiting 2 seconds before retry...")
                    await asyncio.sleep(2)
                    return await self._make_request(endpoint, params)
                else:
                    raise
    
    async def sync_all_data(self) -> Dict[str, Any]:
        """
        Synchronize all data from PrestaShop in the correct order
        """
        sync_results = {
            'start_time': datetime.now().isoformat(),
            'phases': [],
            'total_processed': 0,
            'total_errors': 0
        }
        
        try:
            # Disable foreign key checks for the entire synchronization
            self._disable_foreign_key_checks()
            
            # Phase 1: Base tables (sequential to ensure all complete before proceeding)
            phase1_functions = [
                #("Languages", self.sync_languages),
                #("Countries", self.sync_countries),
                #("Brands", self.sync_brands),
                #("Categories", self.sync_categories),
                ("Carriers", self.sync_carriers),  # REQUIRED: Must sync carriers before orders
            ]
            
            phase1_results = await self._sync_phase_sequential("Phase 1 - Base Tables", phase1_functions)
            sync_results['phases'].append(phase1_results)
            
            # Check if Phase 1 completed successfully
            if phase1_results['total_errors'] > 0:
                print("ERROR: Phase 1 failed. Stopping synchronization.")
                sync_results['status'] = 'ERROR'
                sync_results['error'] = 'Phase 1 (Base Tables) failed'
                return sync_results
            
            # Phase 2: Dependent tables (sequential - addresses need customers)
            phase2_functions = [
                #("Products", self.sync_products),
                #("Customers", self.sync_customers),
                ("Addresses", self.sync_addresses),
            ]
            
            phase2_results = await self._sync_phase_sequential("Phase 2 - Dependent Tables", phase2_functions)
            sync_results['phases'].append(phase2_results)
            
            # Check if Phase 2 completed successfully
            if phase2_results['total_errors'] > 0:
                print("ERROR: Phase 2 failed. Stopping synchronization.")
                sync_results['status'] = 'ERROR'
                sync_results['error'] = 'Phase 2 (Dependent Tables) failed'
                return sync_results
            
            # Phase 3: Complex tables (only after all dependencies are complete)
            phase3_functions = []
            
            # Controlla se skip_images è 0 prima di aggiungere sync_product_images
            skip_images = self._ecommerce_config.get('skip_images', 0)
            
            if skip_images == 0:
                phase3_functions.append(("Product Images", self.sync_product_images))
            
            # Aggiungi sempre Orders
            phase3_functions.append(("Orders", self.sync_orders))
            
            phase3_results = await self._sync_phase_sequential("Phase 3 - Complex Tables", phase3_functions)
            sync_results['phases'].append(phase3_results)
            
            # Calculate totals
            for phase in sync_results['phases']:
                sync_results['total_processed'] += phase['total_processed']
                sync_results['total_errors'] += phase['total_errors']
            
            sync_results['end_time'] = datetime.now().isoformat()
            sync_results['status'] = 'SUCCESS' if sync_results['total_errors'] == 0 else 'PARTIAL'
            
            # Add final debug summary
            self._print_final_sync_summary(sync_results)
            
        except Exception as e:
            sync_results['end_time'] = datetime.now().isoformat()
            sync_results['status'] = 'ERROR'
            sync_results['error'] = str(e)
            
            # Print error summary
            self._print_error_summary(sync_results, str(e))
            raise
        finally:
            # Re-enable foreign key checks
            self._enable_foreign_key_checks()
        
        return sync_results

    async def _sync_phase_sequential(self, phase_name: str, functions: List[tuple]) -> Dict[str, Any]:
        """
        Execute sync functions sequentially and stop if any fails
        
        Args:
            phase_name: Name of the phase
            functions: List of tuples (name, function) to execute sequentially
            
        Returns:
            Dict with phase results
        """
        print(f"\n{'='*60}")
        print(f"Starting {phase_name}")
        print(f"{'='*60}")
        
        phase_start_time = datetime.now()
        phase_results = {
            'phase': phase_name,
            'start_time': phase_start_time.isoformat(),
            'functions': [],
            'total_processed': 0,
            'total_errors': 0,
            'status': 'SUCCESS'
        }
        
        for func_name, func in functions:
            print(f"\n{'='*50}")
            print(f"EXECUTING {func_name}")
            print(f"{'='*50}")
            func_start_time = datetime.now()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = func()
                
                func_end_time = datetime.now()
                func_duration = (func_end_time - func_start_time).total_seconds()
                
                # Handle different result formats
                if isinstance(result, list):
                    processed_count = len(result)
                elif isinstance(result, dict) and 'total_processed' in result:
                    processed_count = result['total_processed']
                else:
                    processed_count = 1 if result else 0
                
                phase_results['functions'].append({
                    'function': func_name,
                    'status': 'SUCCESS',
                    'processed': processed_count,
                    'duration': func_duration,
                    'start_time': func_start_time.isoformat(),
                    'end_time': func_end_time.isoformat()
                })
                
                phase_results['total_processed'] += processed_count
                
                print(f"✅ {func_name}: {processed_count} records processed in {func_duration:.2f}s")
                
            except Exception as e:
                func_end_time = datetime.now()
                func_duration = (func_end_time - func_start_time).total_seconds()
                
                phase_results['functions'].append({
                    'function': func_name,
                    'status': 'ERROR',
                    'processed': 0,
                    'duration': func_duration,
                    'start_time': func_start_time.isoformat(),
                    'end_time': func_end_time.isoformat(),
                    'error': str(e)
                })
                
                phase_results['total_errors'] += 1
                phase_results['status'] = 'ERROR'
                
                print(f"❌ {func_name}: FAILED - {str(e)}")
                print(f"STOPPING {phase_name} due to error in {func_name}")
                
                # Stop the entire phase if any function fails
                break
        
        phase_end_time = datetime.now()
        phase_duration = (phase_end_time - phase_start_time).total_seconds()
        
        phase_results['end_time'] = phase_end_time.isoformat()
        phase_results['duration'] = phase_duration
        
        print(f"\n{phase_name} completed in {phase_duration:.2f}s")
        print(f"Total processed: {phase_results['total_processed']}")
        print(f"Total errors: {phase_results['total_errors']}")
        print(f"Status: {phase_results['status']}")
        
        return phase_results
        
    
    async def sync_languages(self) -> List[Dict[str, Any]]:
        """Synchronize languages from ps_lang"""
        try:
            # Get languages from PrestaShop API
            response = await self._make_request_with_rate_limit('/api/languages', params={'display': '[id,name,iso_code]'})
            
            # Extract languages from response
            languages = self._extract_items_from_response(response, 'languages')
            # Prepare all language data
            lang_data_list = []
            for lang in languages:
                lang_data = {
                    'lang_name': lang.get('name', ''),
                    'iso_code': lang.get('iso_code', ''),
                    'id_origin': lang.get('id', '')
                }
                lang_data_list.append(lang_data)
            
            # Process all upserts concurrently using asyncio.gather
            if lang_data_list:
                results = await asyncio.gather(*[self._upsert_language(data) for data in lang_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Language {lang_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Languages", len(successful_results), errors)
                else:
                    self._log_sync_result("Languages", len(successful_results))
                
                return successful_results
            else:
                self._log_sync_result("Languages", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Languages", 0, [str(e)])
            raise
    
    async def sync_countries(self) -> List[Dict[str, Any]]:
        """Synchronize countries from ps_country_lang"""
        try:
            # Get countries from PrestaShop API with all necessary fields in one call
            params = {
                'display': '[id,iso_code,name]'  # Get all necessary fields in one call,
            }

            if self.new_elements:
                last_id = self.db.execute(text("SELECT MAX(id_origin) FROM countries WHERE id_origin IS NOT NULL")).scalar()
                last_id = last_id if last_id else 0
                params['filter[id]'] = f'>[{last_id}]'

            response = await self._make_request_with_rate_limit('/api/countries', params)
            countries = self._extract_items_from_response(response, 'countries')
            
            # Prepare all country data (no need for additional API calls)
            country_data_list = []
            for country in countries:
                id_origin = int(country.get('id', ''))
                
                # Skip if id_origin is 0 or empty
                if not id_origin or id_origin == 0:
                    continue
                
                # Check if country already exists by id_origin
                existing_country = self._get_country_id_by_origin(id_origin)
                if existing_country:
                    continue  # Skip existing country
                
                country_data = {
                    'id_origin': id_origin,
                    'name': country.get('name', ''),
                    'iso_code': country.get('iso_code', '')
                }
                country_data_list.append(country_data)
            
            # Process all upserts concurrently
            if country_data_list:
                results = await asyncio.gather(*[self._upsert_country(data) for data in country_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Country {country_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Countries", len(successful_results), errors)
                else:
                    self._log_sync_result("Countries", len(successful_results))
                
                return successful_results
            else:
                self._log_sync_result("Countries", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Countries", 0, [str(e)])
            raise
    
    async def sync_brands(self) -> List[Dict[str, Any]]:
        """Synchronize brands from ps_manufacturer (Italian language only)"""
        try:
            # Get manufacturers with only necessary fields
            params = {
                'display': '[id,name]'  # Only necessary fields
            }

            if self.new_elements:
                last_id = self.db.execute(text("SELECT MAX(id_origin) FROM brands WHERE id_origin IS NOT NULL")).scalar()
                last_id = last_id if last_id else 0
                params['filter[id]'] = f'>[{last_id}]'

            response = await self._make_request_with_rate_limit('/api/manufacturers', params)
            manufacturers = self._extract_items_from_response(response, 'manufacturers')
            
            # Prepare all brand data
            brand_data_list = []
            for manufacturer in manufacturers:
                # Since we filtered by Italian language, we can directly use the name
                brand_name = manufacturer.get('name', '')
                
                # Skip brands without name
                if not brand_name or not brand_name.strip():
                    continue
                
                brand_data = {
                    'id_origin': manufacturer.get('id', ''),
                    'name': brand_name
                }
                brand_data_list.append(brand_data)
            
            # Process all upserts concurrently
            if brand_data_list:
                results = await asyncio.gather(*[self._upsert_brand(data) for data in brand_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Brand {brand_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Brands (Italian)", len(successful_results), errors)
                else:
                    self._log_sync_result("Brands (Italian)", len(successful_results))
                
                return successful_results
            else:
                print("DEBUG: No brands to process")
                self._log_sync_result("Brands (Italian)", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Brands (Italian)", 0, [str(e)])
            raise
    
    async def sync_categories(self) -> List[Dict[str, Any]]:
        """Synchronize categories from ps_category (Italian language only)"""
        try:
            # Get Italian language ID
            
            
            # Get categories with only necessary fields
            params = {
                'display': '[id,name]'  # Only necessary fields
            }
    
            if self.new_elements:
                last_id = self.db.execute(text("SELECT MAX(id_origin) FROM categories WHERE id_origin IS NOT NULL")).scalar()
                last_id = last_id if last_id else 0
                params['filter[id]'] = f'>[{last_id}]'

            response = await self._make_request_with_rate_limit('/api/categories', params)
            categories = self._extract_items_from_response(response, 'categories')
            
            # Prepare all category data
            category_data_list = []
            for category in categories:
                # Handle name field - it might be a list or string
                category_name_raw = category.get('name', '')
                category_name = next((item['value'] for item in category_name_raw if item.get('id') == str(self.default_language_id)), '')
                
                # Skip categories without name
                if not category_name:
                    print(f"DEBUG: Skipping category {category.get('id', 'unknown')} - no name found")
                    continue
                
                category_data = {
                    'id_origin': category.get('id', ''),
                    'name': category_name
                }
                category_data_list.append(category_data)
            
            # Process all upserts concurrently
            if category_data_list:
                results = await asyncio.gather(*[self._upsert_category(data) for data in category_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Category {category_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Categories (Italian)", len(successful_results), errors)
                else:
                    self._log_sync_result("Categories (Italian)", len(successful_results))
                
                print(f"DEBUG: Processed {len(successful_results)} Italian categories (API filtered)")
                return successful_results
            else:
                print("DEBUG: No categories to process")
                self._log_sync_result("Categories (Italian)", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Categories (Italian)", 0, [str(e)])
            raise
    
    async def sync_carriers(self) -> List[Dict[str, Any]]:
        """Synchronize carriers from ps_carrier"""
        try:
            
            
            params={
                'display': '[id,name]'
                }

            if self.new_elements:
                last_id = self.db.execute(text("SELECT MAX(id_origin) FROM carriers WHERE id_origin IS NOT NULL")).scalar()
                last_id = last_id if last_id else 0
                params['filter[id]'] = f'>[{last_id}]'


            response = await self._make_request_with_rate_limit('/api/carriers', params)
            carriers = self._extract_items_from_response(response, 'carriers')
            
            # Check for existing carriers to avoid duplicates
            existing_carriers = self.db.execute(text("SELECT id_origin FROM carriers WHERE id_origin IS NOT NULL")).fetchall()
            existing_carrier_origins = {str(row[0]) for row in existing_carriers}
            
            print(f"DEBUG: Found {len(carriers)} total carriers from API")
            print(f"DEBUG: Found {len(existing_carrier_origins)} existing carriers in database")
            
            # Filter out carriers that already exist
            new_carriers = []
            for carrier in carriers:
                carrier_id = str(carrier.get('id', ''))
                if carrier_id not in existing_carrier_origins:
                    new_carriers.append(carrier)
                else:
                    print(f"DEBUG: Carrier {carrier_id} already exists, skipping...")
            
            print(f"DEBUG: Found {len(new_carriers)} new carriers to process out of {len(carriers)} total carriers")
            
            # Prepare all carrier data
            carrier_data_list = []
            for carrier in new_carriers:
                carrier_data = {
                    'id_origin': carrier.get('id', ''),
                    'name': carrier.get('name', '')
                }
                carrier_data_list.append(carrier_data)
            
            # Process all upserts concurrently
            if carrier_data_list:
                results = await asyncio.gather(*[self._upsert_carrier(data) for data in carrier_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Carrier {carrier_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Carriers", len(successful_results), errors)
                else:
                    self._log_sync_result("Carriers", len(successful_results))
                
                return successful_results
            else:
                print("DEBUG: No new carriers to process")
                self._log_sync_result("Carriers", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Carriers", 0, [str(e)])
            raise
    
    
    async def sync_products(self) -> List[Dict[str, Any]]:
        """Synchronize products from ps_product (Italian language only)"""
        print("🚀 STARTING SYNC_PRODUCTS")
        try:
            # Try with pagination to avoid server disconnection
            all_products = []
            limit = 1000  # Batch size
            offset = 0
            params = {
                'display': '[id,id_manufacturer,id_category_default,name,reference,ean13,weight,depth,height,width,id_default_image]',  # Only necessary fields
            }
            last_id = None
            if self.new_elements:
                last_id = self.db.execute(text("SELECT MAX(id_origin) FROM products WHERE id_origin IS NOT NULL")).scalar()
                last_id = last_id if last_id else 0

            
            while True:
                try:
                    print(f"DEBUG: Starting products loop - offset: {offset}, limit: {limit}")
                    # Include only necessary fields to reduce response size
                    # Use PrestaShop format: limit=[offset,]limit

                    if last_id:
                        params['filter[id]'] = f'>[{str(last_id)}]'

                    params['limit'] = f'{offset},{limit}'
                    
                    response = await self._make_request_with_rate_limit('/api/products', params)

                    products = self._extract_items_from_response(response, 'products')
                    print(f"DEBUG: Extracted {len(products)} products from response")
                    if not products:
                        print("DEBUG: No products found, breaking loop")
                        break
                        
                    all_products.extend(products)
                    print(f"DEBUG: Total products so far: {len(all_products)}")
                    offset += limit
                    
                    # Small delay to avoid overwhelming the server
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"DEBUG: Exception in products loop: {str(e)}")
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['server disconnected', '500', 'timeout', 'connection reset']):
                        print(f"DEBUG: Server error detected, reducing batch size from {limit} to {max(10, limit // 2)}")
                        limit = max(10, limit // 2)  # Reduce batch size
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Non-server error, raising exception")
                        raise
                
                
            print(f"DEBUG: Finished products loop. Total products fetched: {len(all_products)}")
            # Deduplicate products by ID and filter for Italian language
            unique_products = {}
            print(f"DEBUG: Starting deduplication process...")
            for product in all_products:
                product_name_list = product.get('name', {})
                product['name'] = next((item['value'] for item in product_name_list if item.get('id') == str(self.default_language_id)), '')
                product_id = product.get('id', '')
                if not product_id:
                    continue
                

                unique_products[product_id] = product
            
            products = list(unique_products.values())

            # Prepare all product data with async lookups
            from src.schemas.product_schema import ProductSchema
            
            async def prepare_product_data(product):                
                try:
                    # Extract type from name (dual/trial logic)
                    # Skip products without name or with empty name
                    if not product['name']:
                       product['name'] = ''
                    product_type = self._extract_product_type(product['name'])
                    
                    # Parallelize the ID lookups
                    category_id, brand_id = await asyncio.gather(
                        self._get_category_id_by_origin(product.get('id_category_default', '')),
                        self._get_brand_id_by_origin(product.get('id_manufacturer', ''))
                    )
                    
                    # Verifica che brand e category esistano
                    if not brand_id:
                        print(f"DEBUG: Brand not found for product {product.get('id', 'unknown')}, manufacturer: {product.get('id_manufacturer', '')}")

                    if not category_id:
                        print(f"DEBUG: Category not found for product {product.get('id', 'unknown')}, category: {product.get('id_category_default', '')}")

                
                    # Genera img_url se il prodotto ha un'immagine
                    id_image_default = product.get('id_default_image', 0)
                    
                    if id_image_default and int(id_image_default) > 0:
                        # Genera il percorso dell'immagine basato sull'ID del prodotto che verrà creato
                        # Useremo un placeholder temporaneo che verrà aggiornato dopo l'inserimento
                        img_url = f"/media/product_images/{self.platform_id}/product_{product.get('id', 0)}.jpg"
                        
                    else:
                        # Se non c'è immagine, usa l'immagine di fallback
                        img_url = "media/fallback/product_not_found.jpg"
                    # Extract price without tax (PrestaShop 'price' field is without tax)
                    price_without_tax = float(product.get('price', 0.0)) if product.get('price') else 0.0
                    
                    # Extract purchase_price from wholesale_price
                    purchase_price = float(product.get('wholesale_price', 0.0)) if product.get('wholesale_price') else 0.0
                    
                    # Extract quantity - try different possible fields
                    # PrestaShop might have quantity in different places
                    quantity = 0
                    
                    # Extract minimal_quantity
                    minimal_quantity = int(product.get('minimal_quantity', 0)) if product.get('minimal_quantity') else 0
                    
                    return ProductSchema(
                        id_origin=int(product.get('id', 0)),
                        id_category=int(category_id) if category_id else 0,
                        id_brand=int(brand_id) if brand_id else 0,
                        id_platform=self.platform_id,
                        img_url=img_url,
                        name=product['name'],
                        sku=product.get('ean13', ''),
                        reference=product.get('reference', 'ND'),
                        weight=float(product.get('weight', 0.0)) if product.get('weight') else 0.0,
                        depth=float(product.get('depth', 0.0)) if product.get('depth') else 0.0,
                        height=float(product.get('height', 0.0)) if product.get('height') else 0.0,
                        width=float(product.get('width', 0.0)) if product.get('width') else 0.0,
                        price_without_tax=price_without_tax,
                        quantity=quantity,
                        purchase_price=purchase_price,
                        minimal_quantity=minimal_quantity,
                        type=product_type
                    )
                except Exception as e:
                    print(f"DEBUG: Error in prepare_product_data for product {product.get('id', 'unknown')}: {str(e)}")
                    print(e)
                    raise
                
            # Prepare all product data concurrently
            product_data_list = await asyncio.gather(*[prepare_product_data(product) for product in products], return_exceptions=True)
            print(f"DEBUG: Product data list count: {len(product_data_list)}")
            # Filter out None values and exceptions
            valid_product_data = []
            errors = []
            for i, result in enumerate(product_data_list):
                if isinstance(result, Exception):
                    print(f"DEBUG: Error processing product {products[i].get('id', 'unknown')}: {str(result)}")
                    errors.append(f"Product {products[i].get('id', 'unknown')}: {str(result)}")
                elif result is not None:
                    valid_product_data.append(result)
                else:
                    print(f"DEBUG: Product {products[i].get('id', 'unknown')} returned None")
            
            print(f"DEBUG: Valid products to insert: {len(valid_product_data)}")
            print(f"DEBUG: Errors: {len(errors)}")
            
            # Bulk insert products for better performance
            if valid_product_data:
                from src.repository.product_repository import ProductRepository
                
                product_repo = ProductRepository(self.db)
                
                # valid_product_data already contains ProductSchema objects
                # Bulk insert
                print(f"DEBUG: Attempting to insert {len(valid_product_data)} products")
                total_inserted = product_repo.bulk_create(valid_product_data, batch_size=10000)
                print(f"DEBUG: Successfully inserted {total_inserted} products")
                
                # Aggiorna img_url per i prodotti inseriti che hanno immagini
                self._update_product_img_urls(valid_product_data, products)
                
                # Store product data for image synchronization in phase3
                if valid_product_data:
                    # Store the product data and original data for later image synchronization
                    self._product_data_for_images = valid_product_data
                    self._original_products_data = products  # Store original PrestaShop data
                
                successful_results = [{"status": "success", "count": total_inserted}]
                upsert_errors = []
                
                all_errors = errors + upsert_errors
                if all_errors:
                    self._log_sync_result("Products (Italian)", total_inserted, all_errors)
                else:
                    self._log_sync_result("Products (Italian)", total_inserted)
                
                print(f"DEBUG: Bulk inserted {total_inserted} Italian products")
                return successful_results
            else:
                print("DEBUG: No products to process")
                self._log_sync_result("Products (Italian)", 0, errors)
                return []
                
        except Exception as e:
            self._log_sync_result("Products (Italian)", 0, [str(e)])
            raise
    
    async def sync_quantity(self) -> Dict[str, Any]:
        """
        Sincronizza le quantità dei prodotti da PrestaShop stock_availables.
        
        Chiama l'endpoint /api/stock_availables per recuperare le quantità aggiornate
        e restituisce un dizionario mappando id_product (id_origin) a quantity.
        
        Returns:
            Dict con:
                - quantity_map: Dict[int, int] - Mappa {id_origin: quantity}
                - total_items: int - Numero totale di prodotti con quantità
                - stats: Dict con statistiche
        """
        print("🚀 STARTING SYNC_QUANTITY")
        try:
            params = {
                'display': '[id_product,quantity]',
                'output_format': 'JSON'
            }
            
            # Chiama l'endpoint stock_availables
            response = await self._make_request_with_rate_limit('/api/stock_availables', params)
            
            # Estrai i dati dalla risposta
            stock_items = self._extract_items_from_response(response, 'stock_availables')
            
            if not stock_items:
                print("DEBUG: No stock_availables data found in response")
                return {
                    'quantity_map': {},
                    'total_items': 0,
                    'stats': {
                        'success': True,
                        'errors': []
                    }
                }
            
            # Crea il dizionario {id_product: quantity}
            # Nota: id_product nell'API PrestaShop corrisponde a id_origin nel nostro DB
            quantity_map = {}
            errors = []
            
            for item in stock_items:
                try:
                    # L'API restituisce id_product come ID del prodotto in PrestaShop (id_origin)
                    id_product_origin = safe_int(item.get('id_product', 0))
                    quantity = safe_int(item.get('quantity', 0))
                    
                    if id_product_origin and id_product_origin > 0:
                        quantity_map[id_product_origin] = quantity
                except Exception as e:
                    error_msg = f"Error processing stock item {item.get('id', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    print(f"DEBUG: {error_msg}")
            
            print(f"DEBUG: Successfully processed {len(quantity_map)} products with quantities")
            if errors:
                print(f"DEBUG: {len(errors)} errors during processing")
            
            return {
                'quantity_map': quantity_map,
                'total_items': len(quantity_map),
                'stats': {
                    'success': True,
                    'errors': errors,
                    'error_count': len(errors)
                }
            }
            
        except Exception as e:
            error_msg = f"Error in sync_quantity: {str(e)}"
            print(f"DEBUG: {error_msg}")
            self._log_sync_result("Product Quantities", 0, [error_msg])
            raise
    
    async def sync_price(self) -> Dict[str, Any]:
        """
        Sincronizza i prezzi dei prodotti da PrestaShop products.
        
        Chiama l'endpoint /api/products con paginazione per recuperare i prezzi aggiornati
        e restituisce un dizionario mappando id_product (id_origin) a price.
        
        Returns:
            Dict con:
                - price_map: Dict[int, float] - Mappa {id_origin: price}
                - total_items: int - Numero totale di prodotti con prezzo
                - stats: Dict con statistiche
        """
        print("🚀 STARTING SYNC_PRICE")
        try:
            all_products = []
            limit = 5000  # Batch size per evitare crash del server
            offset = 0
            params = {
                'display': '[id,price]',  # Solo i campi necessari
            }
            
            while True:
                try:
                    print(f"DEBUG: Starting price sync loop - offset: {offset}, limit: {limit}")
                    
                    params['limit'] = f'{offset},{limit}'
                    
                    # Chiama l'endpoint products con paginazione
                    response = await self._make_request_with_rate_limit('/api/products', params)
                    
                    products = self._extract_items_from_response(response, 'products')
                    print(f"DEBUG: Extracted {len(products)} products from response")
                    
                    if not products:
                        print("DEBUG: No products found, breaking loop")
                        break
                    
                    all_products.extend(products)
                    print(f"DEBUG: Total products so far: {len(all_products)}")
                    offset += limit
                    
                    # Small delay to avoid overwhelming the server
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"DEBUG: Exception in price sync loop: {str(e)}")
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['server disconnected', '500', 'timeout', 'connection reset']):
                        print(f"DEBUG: Server error detected, reducing batch size from {limit} to {max(10, limit // 2)}")
                        limit = max(10, limit // 2)  # Reduce batch size
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Non-server error, raising exception")
                        raise
            
            print(f"DEBUG: Finished price sync loop. Total products fetched: {len(all_products)}")
            
            # Crea il dizionario {id_product: price}
            # Nota: id nell'API PrestaShop corrisponde a id_origin nel nostro DB
            price_map = {}
            errors = []
            
            for product in all_products:
                try:
                    # L'API restituisce id come ID del prodotto in PrestaShop (id_origin)
                    id_product_origin = safe_int(product.get('id', 0))
                    price = safe_float(product.get('price', 0.0))
                    
                    if id_product_origin and id_product_origin > 0:
                        # Converti None o stringa vuota a 0.0
                        if price is None or price == '':
                            price = 0.0
                        price_map[id_product_origin] = float(price)
                except Exception as e:
                    error_msg = f"Error processing product {product.get('id', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    print(f"DEBUG: {error_msg}")
            
            print(f"DEBUG: Successfully processed {len(price_map)} products with prices")
            if errors:
                print(f"DEBUG: {len(errors)} errors during processing")
            
            return {
                'price_map': price_map,
                'total_items': len(price_map),
                'stats': {
                    'success': True,
                    'errors': errors,
                    'error_count': len(errors)
                }
            }
            
        except Exception as e:
            error_msg = f"Error in sync_price: {str(e)}"
            print(f"DEBUG: {error_msg}")
            self._log_sync_result("Product Prices", 0, [error_msg])
            raise
    
    async def sync_product_details(self) -> Dict[str, Any]:
        """
        Sincronizza i dettagli dei prodotti da PrestaShop products.
        
        Recupera SKU, REFERENCE, WEIGHT, DEPTH, HEIGHT, WIDTH, PURCHASE_PRICE, 
        MINIMAL_QUANTITY, PRICE_WITHOUT_TAX da PrestaShop API.
        
        Chiama l'endpoint /api/products con paginazione per recuperare i dettagli aggiornati
        e restituisce un dizionario mappando id_product (id_origin) ai dettagli completi.
        Filtra automaticamente prodotti con id_origin = 0 (SKIP).
        
        Returns:
            Dict con:
                - details_map: Dict[int, Dict[str, Any]] - Mappa {id_origin: {sku, reference, weight, ...}}
                - total_items: int - Numero totale di prodotti con dettagli
                - stats: Dict con statistiche
        """
        print("🚀 STARTING SYNC_PRODUCT_DETAILS")
        try:
            all_products = []
            limit = 5000  # Batch size per evitare crash del server
            offset = 0
            params = {
                'display': '[id,reference,ean13,weight,depth,height,width,wholesale_price,minimal_quantity,price]',
            }
            
            while True:
                try:
                    print(f"DEBUG: Starting product details sync loop - offset: {offset}, limit: {limit}")
                    
                    params['limit'] = f'{offset},{limit}'
                    
                    # Chiama l'endpoint products con paginazione
                    response = await self._make_request_with_rate_limit('/api/products', params)
                    
                    products = self._extract_items_from_response(response, 'products')
                    print(f"DEBUG: Extracted {len(products)} products from response")
                    
                    if not products:
                        print("DEBUG: No products found, breaking loop")
                        break
                    
                    all_products.extend(products)
                    print(f"DEBUG: Total products so far: {len(all_products)}")
                    offset += limit
                    
                    # Small delay to avoid overwhelming the server
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"DEBUG: Exception in product details sync loop: {str(e)}")
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['server disconnected', '500', 'timeout', 'connection reset']):
                        print(f"DEBUG: Server error detected, reducing batch size from {limit} to {max(10, limit // 2)}")
                        limit = max(10, limit // 2)  # Reduce batch size
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Non-server error, raising exception")
                        raise
            
            print(f"DEBUG: Finished product details sync loop. Total products fetched: {len(all_products)}")
            
            # Crea il dizionario {id_origin: {sku, reference, weight, ...}}
            # Nota: id nell'API PrestaShop corrisponde a id_origin nel nostro DB
            details_map = {}
            errors = []
            
            for product in all_products:
                try:
                    # L'API restituisce id come ID del prodotto in PrestaShop (id_origin)
                    id_product_origin = safe_int(product.get('id', 0))
                    
                    # SKIP prodotti con id_origin = 0
                    if not id_product_origin or id_product_origin == 0:
                        continue
                    
                    # Estrai e converti tutti i campi
                    sku = str(product.get('ean13', '') or '')[:32]  # Max 32 chars
                    reference = str(product.get('reference', 'ND') or 'ND')[:64]  # Max 64 chars
                    weight = safe_float(product.get('weight', 0.0)) or 0.0
                    depth = safe_float(product.get('depth', 0.0)) or 0.0
                    height = safe_float(product.get('height', 0.0)) or 0.0
                    width = safe_float(product.get('width', 0.0)) or 0.0
                    purchase_price = safe_float(product.get('wholesale_price', 0.0)) or 0.0
                    minimal_quantity = safe_int(product.get('minimal_quantity', 0)) or 0
                    price_without_tax = safe_float(product.get('price', 0.0)) or 0.0
                    
                    details_map[id_product_origin] = {
                        'sku': sku,
                        'reference': reference,
                        'weight': float(weight),
                        'depth': float(depth),
                        'height': float(height),
                        'width': float(width),
                        'purchase_price': float(purchase_price),
                        'minimal_quantity': int(minimal_quantity),
                        'price_without_tax': float(price_without_tax)
                    }
                except Exception as e:
                    error_msg = f"Error processing product {product.get('id', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    print(f"DEBUG: {error_msg}")
            
            print(f"DEBUG: Successfully processed {len(details_map)} products with details")
            if errors:
                print(f"DEBUG: {len(errors)} errors during processing")
            
            return {
                'details_map': details_map,
                'total_items': len(details_map),
                'stats': {
                    'success': True,
                    'errors': errors,
                    'error_count': len(errors)
                }
            }
            
        except Exception as e:
            error_msg = f"Error in sync_product_details: {str(e)}"
            print(f"DEBUG: {error_msg}")
            self._log_sync_result("Product Details", 0, [error_msg])
            raise
    
    async def get_live_price(self, id_origin: int) -> Optional[float]:
        """
        Recupera il prezzo live (price) di un prodotto direttamente da PrestaShop.
        
        Args:
            id_origin: ID origin del prodotto in PrestaShop
            
        Returns:
            float: Prezzo price del prodotto, o None se non trovato
        """
        try:
            params = {
                'display': '[price]',
                'filter[id]': f'[{id_origin}]',
                'output_format': 'JSON'
            }
            
            # Chiama l'endpoint products con filtro per id_origin
            response = await self._make_request_with_rate_limit('/api/products', params)
            
            # Estrai i dati dalla risposta
            products = self._extract_items_from_response(response, 'products')
            
            if not products or len(products) == 0:
                print(f"DEBUG: Product with id_origin={id_origin} not found in PrestaShop")
                return None
            
            # Prendi il primo prodotto (dovrebbe essere solo uno con il filtro)
            product = products[0]
            price = safe_float(product.get('price', 0.0))
            
            # Converti None o stringa vuota a None
            if price is None or price == '':
                return None
            
            return float(price)
            
        except Exception as e:
            error_msg = f"Error getting live price for product id_origin={id_origin}: {str(e)}"
            print(f"DEBUG: {error_msg}")
            raise
    
    def check_image_exist(self, id_product: int) -> bool:
        """
        Controlla se un'immagine esiste già per un prodotto.
        
        Args:
            id_product: ID del prodotto locale
            
        Returns:
            True se l'immagine esiste, False altrimenti
        """
        import os
        
        # Genera il percorso locale dell'immagine
        local_image_path = self.image_service.generate_local_image_path(
            self.platform_id,
            id_product
        )
        
        # Controlla se il file esiste
        full_path = os.path.join(os.getcwd(), local_image_path)
        return os.path.exists(full_path)
    
    async def _download_single_product_image(self, product_data, product_info, id_image_default):
        """
        Download a single product image asynchronously.
        
        Args:
            product_data: ProductSchema with product data
            product_info: Tuple of (id_product, current_img_url) from database
            
        Returns:
            Dict with update data if successful, None if failed or skipped
        """
        # Usa semaforo per limitare la concorrenza
        if not hasattr(self, '_image_semaphore'):
            self._image_semaphore = asyncio.Semaphore(self.max_concurrent_images)
        
        async with self._image_semaphore:
            try:
                id_product, current_img_url = product_info
                
                # Genera il percorso locale dell'immagine usando l'ID locale
                local_image_path = self.image_service.generate_local_image_path(
                    self.platform_id,
                    id_product
                )
                
                # Genera il percorso relativo dell'immagine
                image_relative_path = self.image_service.generate_local_image_path(
                    self.platform_id,
                    id_product
                )
                
                # Controlla se l'immagine esiste già

                full_path = os.path.join(os.getcwd(), local_image_path)
                if os.path.exists(full_path):
                    print(f"DEBUG: Image already exists for product {id_product}, skipping download")
                    # Aggiungi alla lista per batch update se necessario
                    if current_img_url != image_relative_path:
                        return {"img_url": image_relative_path, "id_product": id_product}
                    return {"img_url": image_relative_path, "id_product": id_product, "skipped": True}
                
                # Ricostruisci l'URL remoto per il download
                name = product_data.name
                link_rewrite = self.image_service._generate_link_rewrite(name)
                remote_image_url = self.image_service.generate_prestashop_image_url(
                    self.base_url, 
                    id_image_default, 
                    link_rewrite
                )
                
                # Scarica l'immagine usando l'ID locale
                saved_path = self.image_service.download_and_save_image(
                    remote_image_url,
                    id_product,
                    self.platform_id
                )
                
                if saved_path:
                    return {"img_url": image_relative_path, "id_product": id_product, "downloaded": True}
                else:
                    print(f"DEBUG: Failed to download image for product {id_product}, using fallback image")
                    # Usa l'immagine di fallback quando il download fallisce
                    fallback_img_url = "media/fallback/product_not_found.jpg"
                    return {"img_url": fallback_img_url, "id_product": id_product, "downloaded": False, "fallback": True}
                    
            except Exception as e:
                print(f"DEBUG: Error downloading image for product {product_data.id_origin}: {str(e)}, using fallback image")
                # Usa l'immagine di fallback quando c'è un errore
                fallback_img_url = "media/fallback/product_not_found.jpg"
                return {"img_url": fallback_img_url, "id_product": id_product, "downloaded": False, "fallback": True}

    async def _download_product_images(self, product_data_list: list, original_products_data: list):
        """
        Scarica le immagini dei prodotti dopo il salvataggio nel database e aggiorna il campo img_url.
        Utilizza asyncio.gather per il download parallelo delle immagini.
        
        Args:
            product_data_list: Lista di ProductSchema con i prodotti salvati
        """
        try:
            print(f"DEBUG: Downloading images for {len(product_data_list)} products")
            
            # Import repository e model per la query
            from src.repository.product_repository import ProductRepository
            from src.models.product import Product
            
            
            product_repo = ProductRepository(self.db)
            
            # Estrai tutti gli id_origin dai prodotti da processare (con e senza immagini)
            origin_ids = []
            products_with_images = []
            products_without_images = []
            for i, product_data in enumerate(product_data_list):
                original_product = original_products_data[i]
                id_image_default = original_product.get('id_default_image', 0)
                origin_ids.append(str(product_data.id_origin))
                if id_image_default and int(id_image_default) > 0:
                    products_with_images.append((product_data, id_image_default))
                else:
                    products_without_images.append(product_data)
            
            if not origin_ids:
                print("DEBUG: No products to process")
                return
            
            # Query unica per ottenere tutti i prodotti necessari
            products_query = product_repo._session.query(
                Product.id_product,
                Product.id_origin,
                Product.img_url
            ).filter(Product.id_origin.in_(origin_ids)).all()
            
            # Crea dizionario per matching veloce: id_origin -> (id_product, img_url)
            products_dict = {str(product.id_origin): (product.id_product, product.img_url) 
                           for product in products_query}
            
            print(f"DEBUG: Found {len(products_dict)} products in database")
            
            # Prepara le task per il download parallelo
            download_tasks = []
            skipped_existing_count = 0
            for product_data, id_image_default in products_with_images:
                product_info = products_dict.get(str(product_data.id_origin))
                if product_info:
                    id_product, current_img_url = product_info
                    
                    # Controlla se l'immagine esiste già prima di aggiungere il task
                    if self.check_image_exist(id_product):
                        skipped_existing_count += 1
                        # Aggiorna il campo img_url nel database se necessario
                        if current_img_url != self.image_service.generate_local_image_path(self.platform_id, id_product):
                            image_relative_path = self.image_service.generate_local_image_path(self.platform_id, id_product)
                            product_repo._session.execute(
                                {"img_url": image_relative_path, "id_product": id_product}
                            )
                        continue
                    
                    # Se l'immagine non esiste, aggiungi il task per il download
                    download_tasks.append(
                        self._download_single_product_image(product_data, product_info, id_image_default)
                    )
                else:
                    print(f"DEBUG: Product {product_data.id_origin} not found in database")
            
            # Commit eventuali aggiornamenti di prodotti con immagini già esistenti
            if skipped_existing_count > 0:
                product_repo._session.commit()
                print(f"DEBUG: Skipped {skipped_existing_count} products with existing images")
            
            # Esegui tutti i download in parallelo
            if download_tasks:
                print(f"DEBUG: Starting parallel download of {len(download_tasks)} images")
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
            else:
                print(f"DEBUG: No images to download (all already exist)")
                results = []
            
            # Processa i risultati
            updates_to_process = []
            downloaded_count = 0
            failed_count = 0
            skipped_count = 0
            fallback_count = 0
            
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    print(f"DEBUG: Exception in image download: {str(result)}")
                elif result is not None:
                    if result.get("skipped"):
                        skipped_count += 1
                    elif result.get("downloaded"):
                        downloaded_count += 1
                    elif result.get("fallback"):
                        fallback_count += 1
                    updates_to_process.append({
                        "img_url": result["img_url"], 
                        "id_product": result["id_product"]
                    })
                else:
                    failed_count += 1
            
            # Processa prodotti senza immagini per impostare il fallback se necessario
            fallback_img_url = "media/fallback/product_not_found.jpg"
            for product_data in products_without_images:
                product_info = products_dict.get(str(product_data.id_origin))
                if product_info:
                    id_product, current_img_url = product_info
                    # Se il prodotto non ha img_url o ha None, imposta il fallback
                    if not current_img_url or current_img_url is None:
                        updates_to_process.append({
                            "img_url": fallback_img_url,
                            "id_product": id_product
                        })
                        fallback_count += 1
            
            # Esegui batch update di tutti i prodotti
            if updates_to_process:
                print(f"DEBUG: Performing batch update for {len(updates_to_process)} products")
                for update_data in updates_to_process:
                    product_repo._session.execute(
                        text("UPDATE products SET img_url = :img_url WHERE id_product = :id_product"),
                        update_data
                    )
                product_repo._session.commit()
                print(f"DEBUG: Batch update completed")
            
            print(f"DEBUG: Image download completed - Downloaded: {downloaded_count}, Skipped: {skipped_count}, Fallback: {fallback_count}, Failed: {failed_count}")
            
        except Exception as e:
            print(f"DEBUG: Error in batch image download: {str(e)}")
    
    async def sync_product_images(self) -> List[Dict[str, Any]]:
        """
        Synchronize product images using stored product data from sync_products.
        This method is called in phase3 to avoid duplicate API calls.
        """
        print("🚀 STARTING SYNC_PRODUCT_IMAGES")
        try:
            if not hasattr(self, '_product_data_for_images') or not self._product_data_for_images:
                print("DEBUG: No product data available for image synchronization")
                self._log_sync_result("Product Images", 0, ["No product data available"])
                return []
            
            if not hasattr(self, '_original_products_data') or not self._original_products_data:
                print("DEBUG: No original product data available for image synchronization")
                self._log_sync_result("Product Images", 0, ["No original product data available"])
                return []
            
            product_count = len(self._product_data_for_images)
            print(f"DEBUG: Starting image downloads for {product_count} products")
            await self._download_product_images(self._product_data_for_images, self._original_products_data)
            
            # Clear the stored data after processing
            self._product_data_for_images = []
            self._original_products_data = []
            
            # Warm-up cache per le immagini appena sincronizzate
            if product_count > 0:
                await self._warm_up_image_cache()
            
            self._log_sync_result("Product Images", product_count)
            return [{"status": "success", "count": product_count}]
            
        except Exception as e:
            self._log_sync_result("Product Images", 0, [str(e)])
            raise
    
    async def sync_customers(self) -> List[Dict[str, Any]]:
        """Synchronize customers from ps_customer"""
        print("🚀 STARTING SYNC_CUSTOMERS")
        try:
            all_customers = []
            limit = 5000
            offset = 0
            
            while True:
                params = {
                    'display': '[id,firstname,lastname,email]',
                    'limit': f'{offset},{limit}'
                }

                if self.new_elements:
                    last_id = self.db.execute(text("SELECT MAX(id_origin) FROM customers WHERE id_origin IS NOT NULL")).scalar()
                    last_id = last_id if last_id else 0
                    params['filter[id]'] = f'>[{last_id}]'
                

                response = await self._make_request_with_rate_limit('/api/customers', params)
                customers = self._extract_items_from_response(response, 'customers')
                if not customers:
                    return []
                    
                all_customers.extend(customers)
                
                # If we got less than the limit, we've reached the end
                if len(customers) < limit:
                    break
                    
                offset += limit
                # Small delay between batches
                await asyncio.sleep(0.1)
            
            customers = all_customers
            
            # Prepare all customer data
            customer_data_list = []
            for customer in customers:
                customer_data = {
                    'id_origin': customer.get('id', ''),
                    'firstname': customer.get('firstname', ''),
                    'lastname': customer.get('lastname', ''),
                    'email': customer.get('email', ''),
                    'date_add': datetime.now()
                }
                customer_data_list.append(customer_data)
            
            # Bulk insert customers for better performance
            if customer_data_list:
                
                customer_repo = CustomerRepository(self.db)
                
                # Convert to CustomerSchema objects
                customer_schemas = []
                for data in customer_data_list:
                    firstname = data.get('firstname', '')
                    lastname = data.get('lastname', '')
                    email = data.get('email', '')
                    
                    # Use defaults if fields are empty
                    if not firstname:
                        firstname = f"Customer_{data.get('id_origin', 'unknown')}"
                    if not lastname:
                        lastname = "Unknown"
                    if not email:
                        email = f"customer_{data.get('id_origin', 'unknown')}@example.com"
                    
                    # Get Italian language ID (default)
                    
                    
                    customer_schema = CustomerSchema(
                        id_origin=data.get('id_origin', 0),
                        id_lang=self.default_language_id,
                        firstname=firstname,
                        lastname=lastname,
                        email=email
                    )
                    customer_schemas.append(customer_schema)
                
                # Bulk insert
                total_inserted = customer_repo.bulk_create(customer_schemas, batch_size=10000)
                successful_results = [{"status": "success", "count": total_inserted}]
                errors = []
                
                self._log_sync_result("Customers", total_inserted)
                return successful_results
            else:
                self._log_sync_result("Customers", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Customers", 0, [str(e)])
            raise
    

    async def sync_payments(self) -> List[Dict[str, Any]]:
        """Synchronize payment methods from ps_orders"""
        print("🚀 STARTING SYNC_PAYMENTS")
        try:
            orders = await self._get_payments_data()  # Use cached data
            
            # Extract unique payment methods
            payment_methods = set()
            for order in orders:
                payment_method = order.get('payment', '')
                if payment_method:
                    payment_methods.add(payment_method)
            
            # Prepare all payment data
            payment_data_list = []
            for payment_method in payment_methods:
                payment_data = {
                    'payment_name': payment_method,
                    'is_complete_payment': 1
                }
                payment_data_list.append(payment_data)
            
            # Process all upserts concurrently
            if payment_data_list:
                results = await asyncio.gather(*[self._upsert_payment(data) for data in payment_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Payment {payment_data_list[i].get('payment_name', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Payments", len(successful_results), errors)
                else:
                    self._log_sync_result("Payments", len(successful_results))
                
                return successful_results
            else:
                self._log_sync_result("Payments", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Payments", 0, [str(e)])
            raise
    
    async def _process_and_insert_address_batch(self, batch_addresses: List[Dict], all_states: Dict, all_countries: Dict, address_repo) -> tuple:
        """Process and insert a batch of addresses immediately"""
        try:
            # Prepare address data for this batch
            async def prepare_address_data(address):
                # Get state name from the pre-fetched dictionary
                state_id = int(address.get('id_state', ''))
                state_name = all_states[state_id] if state_id != 0 else 'ND'
                
                # Get country ID from pre-fetched dictionary
                country_origin_id_raw = address.get('id_country')
                # Converti a int, gestendo stringhe e numeri
                try:
                    country_origin_id = int(country_origin_id_raw) if country_origin_id_raw and str(country_origin_id_raw) != '0' else None
                except (ValueError, TypeError):
                    country_origin_id = None
                
                country_id = all_countries.get(country_origin_id) if country_origin_id else None
                

                # Get customer ID (still need to call this as it's not pre-fetched)
                customer_origin = str(address.get('id_customer', ''))
                customer_id = self._get_customer_id_by_origin(customer_origin)
                customer_id = customer_id if customer_id != 0 else None
                
                # Debug customer mapping
                if customer_origin != '' and customer_origin != '0' and customer_id is None:
                    print(f"DEBUG: Customer origin '{customer_origin}' not found in database")
                elif customer_origin != '' and customer_origin != '0' and customer_id is not None:
                    print(f"DEBUG: Found customer '{customer_origin}' -> {customer_id}")
                return {
                    'id_origin': address.get('id', 0),
                    'id_country': country_id,
                    'id_customer': customer_id,
                    'company': address.get('company', ''),
                    'firstname': address.get('firstname', ''),
                    'lastname': address.get('lastname', ''),
                    'address1': address.get('address1', ''),
                    'address2': address.get('address2', ''),
                    'state': province_service.update_state_with_abbreviation(state_name),
                    'postcode': address.get('postcode', ''),
                    'city': address.get('city', ''),
                    'phone': address.get('phone_mobile', None),
                    'vat': address.get('vat', ''),
                    'dni': address.get('dni', ''),
                    'pec': address.get('pec', ''),
                    'sdi': address.get('sdi', ''),
                    'date_add': datetime.now()
                }
            
            # Prepare all address data concurrently for this batch
            address_data_list = await asyncio.gather(*[prepare_address_data(address) for address in batch_addresses], return_exceptions=True)
            
            # Filter out exceptions
            valid_address_data = []
            errors = []
            for i, result in enumerate(address_data_list):
                if isinstance(result, Exception):
                    errors.append(f"Address {batch_addresses[i].get('id', 'unknown')}: {str(result)}")
                else:
                    valid_address_data.append(result)
            
            batch_processed = len(batch_addresses)
            batch_errors = len(errors)
            batch_successful = 0
            
            # Insert valid addresses immediately
            if valid_address_data:
                from src.schemas.address_schema import AddressSchema
                
                # Convert to AddressSchema objects
                address_schemas = []
                for data in valid_address_data:
                    # Remove date_add as it's not in AddressSchema
                    data_copy = data.copy()
                    data_copy.pop('date_add', None)
                    address_schema = AddressSchema(**data_copy)
                    address_schemas.append(address_schema)
                
                # Bulk insert this batch using ultra-fast CSV import method
                batch_successful = address_repo.bulk_create_csv_import(address_schemas, batch_size=10000)
                print(f"DEBUG: Inserted {batch_successful} addresses from batch via CSV import")
            
            return batch_processed, batch_successful, batch_errors
            
        except Exception as e:
            print(f"DEBUG: Error processing batch: {str(e)}")
            return len(batch_addresses), 0, 1
    
    async def _process_all_addresses_and_create_sql(self, all_addresses: List[Dict], all_states: Dict, all_countries: Dict) -> int:
        """Process all addresses and create SQL file for bulk insert"""
        try:

            
            from datetime import date
            # Pre-fetch all customer IDs to avoid repeated DB calls
            print("DEBUG: Pre-fetching customer IDs...")
            customer_origins = set()
            for address in all_addresses:
                customer_origin = address.get('id_customer', '')
                if customer_origin and customer_origin != '0':
                    try:
                        customer_origins.add(int(customer_origin))
                    except (ValueError, TypeError):
                        print(f"DEBUG: Invalid customer origin '{customer_origin}', skipping")
            
            # Get all customer IDs in one query
            all_customers = {}
            
            
            if not customer_origins:
                print("WARNING: No valid customer origins found in addresses. This might indicate missing customers.")
                return 0
            if customer_origins:
                from src.repository.customer_repository import CustomerRepository
                from src.models.customer import Customer
                customer_repo = CustomerRepository(self.db)
                customers = customer_repo._session.query(Customer).filter(
                    Customer.id_origin.in_(customer_origins)
                ).all()
                all_customers = {int(customer.id_origin): customer.id_customer for customer in customers}
            
            print(f"DEBUG: Pre-fetched {len(all_customers)} customer IDs from {len(customer_origins)} unique origins")

            
            # Optimized prepare address data function
            def prepare_address_data_optimized(address):
                # Get state name from the pre-fetched dictionary
                state_id_raw = address.get('id_state')
                state_id = int(state_id_raw) if state_id_raw is not None and state_id_raw != '' else 0
                state_name = all_states[state_id] if state_id != 0 else 'ND'
                
                # Get country ID from pre-fetched dictionary
                country_origin_id_raw = address.get('id_country')
                # Converti a int, gestendo stringhe e numeri
                try:
                    country_origin_id = int(country_origin_id_raw) if country_origin_id_raw and str(country_origin_id_raw) != '0' else None
                except (ValueError, TypeError):
                    country_origin_id = None
                
                country_id = all_countries.get(country_origin_id) if country_origin_id else None
                


                # Get customer ID from pre-fetched dictionary
                customer_origin_raw = address.get('id_customer')
                customer_origin = int(customer_origin_raw) if customer_origin_raw is not None and customer_origin_raw != '' else 0
                customer_id_raw = all_customers.get(customer_origin)
                customer_id = int(customer_id_raw) if customer_id_raw is not None else 0
                
                
                return {
                    'id_origin': address.get('id', 0),
                    'id_platform': self.platform_id,
                    'id_country': country_id,
                    'id_customer': customer_id,
                    'company': address.get('company', ''),
                    'firstname': address.get('firstname', ''),
                    'lastname': address.get('lastname', ''),
                    'address1': address.get('address1', ''),
                    'address2': address.get('address2', ''),
                    'state': province_service.update_state_with_abbreviation(state_name),
                    'postcode': address.get('postcode', ''),
                    'city': address.get('city', ''),
                    'phone': address.get('phone', None),
                    'vat': address.get('vat_number', ''),
                    'dni': address.get('dni', ''),
                    'pec': address.get('pec', ''),
                    'sdi': address.get('sdi', ''),
                    'date_add': date.today()
                }
            
            # Prepare all address data in batches for better performance
            valid_address_data = []
            errors = []
            
            # Process in batches of 5000 for better memory management and performance
            batch_size = 5000
            total_batches = (len(all_addresses) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(all_addresses))
                batch_addresses = all_addresses[start_idx:end_idx]
                
                # Process batch
                for address in batch_addresses:
                    try:
                        result = prepare_address_data_optimized(address)
                        valid_address_data.append(result)
                    except Exception as e:
                        errors.append(f"Address {address.get('id', 'unknown')}: {str(e)}")
            
            print(f"DEBUG: Prepared {len(valid_address_data)} valid addresses, {len(errors)} errors")
            if not valid_address_data:
                print("DEBUG: No valid addresses to insert")
                return 0
            
            # Use executemany for bulk insert (more reliable than SQL file)
            # Get existing address origin IDs to avoid duplicates
            existing_origins = set()
            existing_addresses = self.db.execute(text("SELECT id_origin FROM addresses WHERE id_origin IS NOT NULL")).fetchall()
            existing_origins = {str(row[0]) for row in existing_addresses}
            
            # Prepare data for executemany, filtering out existing addresses
            insert_data = []
            skipped_count = 0
            
            for data in valid_address_data:
                # Check if address already exists
                address_origin = str(data.get('id_origin', 0))
                if address_origin in existing_origins:
                    skipped_count += 1
                    continue
                
                # Clean the data
                if data.get('id_country') == 0:
                    data['id_country'] = None
                if data.get('id_customer') == 0:
                    data['id_customer'] = None
                
                insert_data.append({
                    'id_origin': data.get('id_origin', 0),
                    'id_platform': data.get('id_platform', self.platform_id),
                    'id_country': data.get('id_country'),
                    'id_customer': data.get('id_customer'),
                    'company': data.get('company', ''),
                    'firstname': data.get('firstname', ''),
                    'lastname': data.get('lastname', ''),
                    'address1': data.get('address1', ''),
                    'address2': data.get('address2', ''),
                    'state': data.get('state', ''),
                    'postcode': data.get('postcode', ''),
                    'city': data.get('city', ''),
                    'phone': data.get('phone'),
                    'vat': data.get('vat', ''),
                    'dni': data.get('dni', ''),
                    'pec': data.get('pec', ''),
                    'sdi': data.get('sdi', ''),
                    'date_add': data.get('date_add')
                })
            
            if not insert_data:
                print("DEBUG: No new addresses to insert")
                return 0
            
            # Execute bulk insert in batches
            insert_sql = text("""
                INSERT INTO addresses (
                    id_origin, id_platform, id_country, id_customer, company, firstname, lastname,
                    address1, address2, state, postcode, city, phone, vat, dni, pec, sdi, date_add
                ) VALUES (
                    :id_origin, :id_platform, :id_country, :id_customer, :company, :firstname, :lastname,
                    :address1, :address2, :state, :postcode, :city, :phone, :vat, :dni, :pec, :sdi, :date_add
                )
            """)
            
            # Insert in batches of 5000 for better performance
            batch_size = 5000
            total_inserted = 0
            
            for i in range(0, len(insert_data), batch_size):
                batch = insert_data[i:i + batch_size]
                self.db.execute(insert_sql, batch)
                self.db.commit()
                total_inserted += len(batch)
            
            print(f"DEBUG: Successfully inserted {total_inserted} addresses")
            
            return len(valid_address_data)
            
        except Exception as e:
            print(f"DEBUG: Error processing addresses: {str(e)}")
            raise
    
    async def sync_addresses(self) -> List[Dict[str, Any]]:
        """Synchronize addresses from ps_address"""
        print("🚀 STARTING SYNC_ADDRESSES")
        try:
            limit = 5000  # 25k addresses per API call
            offset = 0
            parallel_batches = 1  # Single call per batch since we're getting 50k at once

            # Fetch all states at once for efficient lookup
            all_states = await self._get_all_states()
            all_countries = self._get_all_countries()
            
            # Collect all addresses first
            all_addresses = []
            total_processed = 0
            total_errors = 0
            
            while True:
                # Prepare multiple parallel requests
                tasks = []
                for i in range(parallel_batches):
                    current_offset = offset + (i * limit)
                    params = {
                        'display': 'full',
                        'limit': f'{current_offset},{limit}'
                    }

                    if self.new_elements:
                        last_id = self.db.execute(text("SELECT MAX(id_origin) FROM addresses WHERE id_origin IS NOT NULL")).scalar()
                        last_id = last_id if last_id else 0
                        params['filter[id]'] = f'>[{last_id}]'

                    tasks.append(self._make_request_with_rate_limit('/api/addresses', params=params))
                
                # Execute parallel requests
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                
                # Process responses
                batch_addresses = []
                for i, response in enumerate(responses):
                    if isinstance(response, Exception):
                        print(f"DEBUG: Error in batch {i}: {str(response)}")
                        total_errors += 1
                        continue
                        
                    addresses = self._extract_items_from_response(response, 'addresses')
                    if addresses:
                        batch_addresses.extend(addresses)
                
                if not batch_addresses:
                    break
                
                # Collect addresses instead of processing immediately
                all_addresses.extend(batch_addresses)
                total_processed += len(batch_addresses)
                
                # If we got less than expected, we've reached the end
                if len(batch_addresses) < limit:
                    break
                    
                offset += limit
                # Small delay between batches
                await asyncio.sleep(0.1)  # Reduced delay for faster processing
            
            # All addresses collected, now process them all at once
            if not all_addresses:
                print("DEBUG: No addresses to process")
                self._log_sync_result("Addresses", 0)
                return []
            
            # Process all addresses and create SQL file
            total_successful = await self._process_all_addresses_and_create_sql(
                all_addresses, all_states, all_countries
            )
            
            print(f"DEBUG: Address sync completed - Processed: {total_processed}, Inserted: {total_successful}")
            
            if total_successful > 0:
                self._log_sync_result("Addresses", total_successful)
                return [{"status": "success", "count": total_successful}]
            else:
                self._log_sync_result("Addresses", 0, [f"Total errors: {total_errors}"])
                return []
            
        except Exception as e:
            self._log_sync_result("Addresses", 0, [str(e)])
            raise
    
    async def sync_orders(self) -> List[Dict[str, Any]]:
        """Synchronize orders and order details from ps_orders with associations"""
        print("🚀 STARTING SYNC_ORDERS")
        try:
            print("DEBUG: Starting orders synchronization...")
            
            # Final check: ensure all dependencies are synced successfully
            
            customers_count = self.db.execute(text("SELECT COUNT(*) FROM customers")).scalar()
            products_count = self.db.execute(text("SELECT COUNT(*) FROM products")).scalar()
            payments_count = self.db.execute(text("SELECT COUNT(*) FROM payments")).scalar()
            addresses_count = self.db.execute(text("SELECT COUNT(*) FROM addresses")).scalar()
            carriers_count = self.db.execute(text("SELECT COUNT(*) FROM carriers")).scalar()
            
            print(f"DEBUG: Dependencies check - Customers: {customers_count}, Products: {products_count}, Payments: {payments_count}, Addresses: {addresses_count}, Carriers: {carriers_count}")
            
            if customers_count == 0:
                raise Exception("No customers found. Cannot sync orders without customers.")
            if products_count == 0:
                raise Exception("No products found. Cannot sync orders without products.")
            if addresses_count == 0:
                raise Exception("No addresses found. Cannot sync orders without addresses.")
            if carriers_count == 0:
                print("⚠️ WARNING: No carriers found in database. Orders will have id_carrier = 0. Please run sync_carriers first!")
            
            print("DEBUG: All dependencies verified. Proceeding with orders sync...")
            
            orders = await self._get_orders_data()  # Get fresh orders data
            
            
            existing_orders = self.db.execute(text("SELECT id_origin FROM orders WHERE id_origin IS NOT NULL")).fetchall()
            existing_order_origins = {str(row[0]) for row in existing_orders}
            
            # Filter out existing orders
            new_orders = []
            for order in orders:
                order_id_prestashop = order.get('id', 0)
                if str(order_id_prestashop) not in existing_order_origins:
                    new_orders.append(order)
                else:
                    print(f"DEBUG: Order {order_id_prestashop} already exists, skipping...")
            
            print(f"DEBUG: Found {len(new_orders)} new orders to process out of {len(orders)} total orders")
            
            if not new_orders:
                print("DEBUG: No new orders to process")
                self._log_sync_result("Orders", 0)
                return []
            
            # Process all orders and create SQL file for bulk insert
            total_successful = await self._process_all_orders_and_create_sql(new_orders)
            
            print(f"DEBUG: Order sync completed - Total processed: {len(new_orders)}, Successful: {total_successful}")
            
            if total_successful > 0:
                self._log_sync_result("Orders", total_successful)
                return [{"status": "success", "count": total_successful}]
            else:
                self._log_sync_result("Orders", 0, ["No orders could be processed"])
                return []
   
        except Exception as e:
            self._log_sync_result("Orders", 0, [str(e)])
            raise
    
    
    # Helper methods for data extraction and transformation
    def _extract_product_type(self, product_name: Any) -> str:
        """Extract product type from name (dual/trial logic)"""
        # Handle both string and list formats
        if isinstance(product_name, list):
            # If it's a list, take the first element or join them
            if product_name:
                product_name = product_name[0] if isinstance(product_name[0], str) else str(product_name[0])
            else:
                return 'standard'
        elif not isinstance(product_name, str):
            product_name = str(product_name)
        
        if 'dual' in product_name.lower():
            return 'dual'
        elif 'trial' in product_name.lower():
            return 'trial'
        return 'standard'
    
    # Database upsert methods (to be implemented based on your models)
    async def _upsert_language(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert language record"""
        try:
            from src.repository.lang_repository import LangRepository
            from src.schemas.lang_schema import LangSchema
            
            lang_repo = LangRepository(self.db)
            
            # Extract data from PrestaShop format - handle empty fields
            lang_name = data.get('lang_name', data.get('name', ''))
            iso_code = data.get('iso_code', '')
            
            # Skip if both fields are empty (invalid language data)
            if not lang_name and not iso_code:
                print(f"DEBUG: Skipping language {data.get('id_origin', 'unknown')} - empty name and iso_code")
                return {"status": "skipped", "id_origin": data.get('id_origin', 'unknown')}
            
            # Use defaults if fields are empty
            if not lang_name:
                lang_name = f"Language_{data.get('id_origin', 'unknown')}"
            if not iso_code:
                iso_code = "XX"
            
            # Check if language already exists by ISO code
            existing_lang = lang_repo.get_by_iso_code(iso_code)
            if existing_lang:
                return {"status": "skipped", "id_origin": data.get('id_origin', 'unknown'), "reason": "already_exists", "existing_id": existing_lang.id_lang}
            
            # Create LangSchema
            lang_schema = LangSchema(
                name=lang_name,
                iso_code=iso_code
            )
            
            # Create language in database
            lang_repo.create(lang_schema)
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_country(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert country record"""
        try:
            from src.repository.country_repository import CountryRepository
            from src.schemas.country_schema import CountrySchema
            
            country_repo = CountryRepository(self.db)
            
            # Extract data from PrestaShop format
            country_name = data.get('name', '')
            if isinstance(country_name, list) and country_name:
                country_name = country_name[0].get('value', '') if isinstance(country_name[0], dict) else str(country_name[0])
            
            iso_code = data.get('iso_code', '')
            if isinstance(iso_code, list) and iso_code:
                iso_code = iso_code[0].get('value', '') if isinstance(iso_code[0], dict) else str(iso_code[0])
            
            # Create CountrySchema
            country_schema = CountrySchema(
                id_origin=data.get('id_origin', 0),
                name=country_name,
                iso_code=iso_code
            )
            
            # Create country in database
            country_repo.create(country_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting country {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_brand(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert brand record"""
        try:
            from src.repository.brand_repository import BrandRepository
            from src.schemas.brand_schema import BrandSchema
            
            brand_repo = BrandRepository(self.db)
            
            # Check if brand already exists
            id_origin = data.get('id_origin', 0)
            existing_brand = brand_repo.get_by_origin_id(str(id_origin))
            if existing_brand:
                return {"status": "skipped", "id_origin": id_origin, "reason": "already_exists"}
            
            # Convert data to BrandSchema, add id_platform
            brand_data = {**data, 'id_platform': self.platform_id}
            brand_schema = BrandSchema(**brand_data)
            
            # Create brand in database
            brand_repo.create(brand_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting brand {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_category(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert category record"""
        try:
            from src.repository.category_repository import CategoryRepository
            from src.schemas.category_schema import CategorySchema
            
            category_repo = CategoryRepository(self.db)
            
            # Check if category already exists
            id_origin = data.get('id_origin', 0)
            existing_category = category_repo.get_by_origin_id(str(id_origin))
            if existing_category:
                return {"status": "skipped", "id_origin": id_origin, "reason": "already_exists"}
            
            # Extract data from PrestaShop format - handle both string and object formats
            category_name = data.get('name', '')
            
            # Create CategorySchema with id_platform
            category_schema = CategorySchema(
                id_origin=data.get('id_origin', 0),
                id_platform=self.platform_id,
                name=category_name
            )
            
            # Create category in database
            category_repo.create(category_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting category {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_carrier(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert carrier record"""
        try:
            from src.repository.carrier_repository import CarrierRepository
            from src.schemas.carrier_schema import CarrierSchema
            
            carrier_repo = CarrierRepository(self.db)
            
            # Extract data from PrestaShop format - handle both string and object formats
            carrier_name = data.get('name', '')
            
            if isinstance(carrier_name, dict):
                if 'value' in carrier_name:
                    carrier_name = carrier_name['value']
                else:
                    # If it's a dict but no 'value' key, try to get the first string value
                    carrier_name = str(list(carrier_name.values())[0]) if carrier_name else ''
            elif isinstance(carrier_name, list) and carrier_name:
                if isinstance(carrier_name[0], dict):
                    if 'value' in carrier_name[0]:
                        carrier_name = carrier_name[0]['value']
                    else:
                        # If it's a list of dicts but no 'value' key, try to get the first string value
                        carrier_name = str(list(carrier_name[0].values())[0]) if carrier_name[0] else ''
                else:
                    carrier_name = str(carrier_name[0])

            
            # Create CarrierSchema
            carrier_schema = CarrierSchema(
                id_origin=data.get('id_origin', 0),
                name=carrier_name
            )
            
            # Create carrier in database - convert schema to dict
            carrier_repo.create(carrier_schema.model_dump())
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting carrier {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    
    async def _upsert_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.repository.product_repository import ProductRepository
            from src.schemas.product_schema import ProductSchema
            
            product_repo = ProductRepository(self.db)
            
            # Check if product already exists
            id_origin = data.get('id_origin', 0)
            
            existing_product = product_repo.get_by_origin_id(str(id_origin))
            if existing_product:
                print(f"DEBUG: Product with origin ID {id_origin} already exists, skipping")
                return {"status": "skipped", "id_origin": id_origin, "reason": "already_exists"}
            
            # Create ProductSchema with extracted data
            product_schema = ProductSchema(
                id_origin=data.get('id_origin', 0),
                id_category=data.get('id_category', 0),
                id_brand=data.get('id_brand', 0),
                name=data.get('name', {}),
                sku=data.get('sku', ''),
                type=data.get('type', 'standard')
            )
            
            # Create product in database
            product_repo.create(product_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(data)
            print(f"DEBUG: Error upserting product {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_customer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert customer record"""
        try:
            
            customer_repo = CustomerRepository(self.db)
            
            # Extract data from PrestaShop format
            firstname = data.get('firstname', '')
            lastname = data.get('lastname', '')
            email = data.get('email', '')
            
            # Use defaults if fields are empty
            if not firstname:
                firstname = f"Customer_{data.get('id_origin', 'unknown')}"
            if not lastname:
                lastname = "Unknown"     
            # Create CustomerSchema
            customer_schema = CustomerSchema(
                id_origin=data.get('id_origin', 0),
                id_lang=self.default_language_id,
                firstname=firstname,
                lastname=lastname,
                email=email
            )
            
            # Create customer in database
            customer_repo.create(customer_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting customer {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert payment record"""
        try:
            from src.repository.payment_repository import PaymentRepository
            from src.schemas.payment_schema import PaymentSchema
            
            payment_repo = PaymentRepository(self.db)
            
            # Extract data from PrestaShop format
            payment_name = data.get('payment_name', data.get('name', ''))
            is_complete = data.get('is_complete_payment', 1) == 1
            
            # Create PaymentSchema
            payment_schema = PaymentSchema(
                name=payment_name,
                is_complete_payment=is_complete
            )
            
            # Create payment in database
            payment_repo.create(payment_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting payment {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_address(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert address record"""
        try:
            from src.repository.address_repository import AddressRepository
            from src.schemas.address_schema import AddressSchema
            
            address_repo = AddressRepository(self.db)
            
            # Convert data to AddressSchema
            address_schema = AddressSchema(**data)
            
            # Create address in database
            address_repo.create(address_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert order record"""
        try:
            from src.repository.order_repository import OrderRepository
            from src.schemas.order_schema import OrderSchema
            
            order_repo = OrderRepository(self.db)
            
            # Convert data to OrderSchema
            order_schema = OrderSchema(**data)
            # Create order in database
            order_repo.create(order_schema)
            
            id_order = int(self._get_order_id_by_origin(data.get('id_origin')))
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown'), "id_order": id_order}
            
        except Exception as e:
            print(f"DEBUG: Error upserting order {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    
    async def _upsert_order_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert order detail record"""
        try:
            from src.repository.order_detail_repository import OrderDetailRepository
            from src.schemas.order_detail_schema import OrderDetailSchema
            
            order_detail_repo = OrderDetailRepository(self.db)
            
            # Convert data to OrderDetailSchema
            order_detail_schema = OrderDetailSchema(**data)
            
            # Create order detail in database
            order_detail_repo.create(order_detail_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting order detail {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _check_order_exists(self, id_origin: str) -> bool:
        """Check if order already exists in database by id_origin"""
        try:
            from src.repository.order_repository import OrderRepository
            order_repo = OrderRepository(self.db)
            existing_order = order_repo.get_by_origin_id(id_origin)
            return existing_order is not None
        except Exception as e:
            print(f"DEBUG: Error checking if order exists: {str(e)}")
            return False
    
    # Helper methods for ID lookups
    async def _get_category_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get category ID by origin ID"""
        try:
            from src.repository.category_repository import CategoryRepository
            category_repo = CategoryRepository(self.db)
            category = category_repo.get_by_origin_id(origin_id)
            return category.id_category if category else None
        except Exception as e:
            print(f"DEBUG: Error getting category ID by origin {origin_id}: {str(e)}")
            return None
    
    async def _get_brand_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get brand ID by origin ID"""
        try:
            from src.repository.brand_repository import BrandRepository
            brand_repo = BrandRepository(self.db)
            brand = brand_repo.get_by_origin_id(origin_id)
            return brand.id_brand if brand else None
        except Exception as e:
            print(f"DEBUG: Error getting brand ID by origin {origin_id}: {str(e)}")
            return None
    
    def _get_country_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get country ID by origin ID"""
        try:
            from src.repository.country_repository import CountryRepository
            country_repo = CountryRepository(self.db)
            country = country_repo.get_by_origin_id(origin_id)
            return country.id_country if country else None
        except Exception as e:
            print(f"DEBUG: Error getting country ID by origin {origin_id}: {str(e)}")
            return None
    def _get_customer_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get customer ID by origin ID"""
        try:
            from src.repository.customer_repository import CustomerRepository
            customer_repo = CustomerRepository(self.db)
            customer = customer_repo.get_by_origin_id(origin_id)
            return customer.id_customer if customer else 0
        except Exception as e:
            print(f"DEBUG: Error getting customer ID by origin {origin_id}: {str(e)}")
            return 0
    
    def _get_address_id_by_origin(self, origin_id: int) -> Optional[int]:
        """Get address ID by origin ID"""
        try:
            # Convert to string and check for empty/zero values               
            from src.repository.address_repository import AddressRepository
            address_repo = AddressRepository(self.db)
            address_id = address_repo.get_id_by_id_origin(origin_id)
            
            if address_id:
                return address_id
            else:
                return 0
        except Exception as e:
            return 0
    
    def _get_payment_id_by_name(self, payment_name: str) -> Optional[int]:
        """Get payment ID by name"""
        try:
            from src.repository.payment_repository import PaymentRepository
            payment_repo = PaymentRepository(self.db)
            payment = payment_repo.get_by_name(payment_name)
            return payment.id_payment if payment else 0
        except Exception as e:
            print(f"DEBUG: Error getting payment ID by name {payment_name}: {str(e)}")
            return 0
    
    async def _get_or_create_payment_id(self, payment_name: str, payment_repo=None) -> Optional[int]:
        """Get existing payment ID or create new payment if not exists"""
        try:
            if not payment_name:
                return None
                
            # Use provided repository or create new one if not provided
            if payment_repo is None:
                from src.repository.payment_repository import PaymentRepository
                payment_repo = PaymentRepository(self.db)
            
            # Try to find existing payment
            payment = payment_repo.get_by_name(payment_name)
            if payment:
                return payment.id_payment
            
            # Create new payment if not exists
            from src.schemas.payment_schema import PaymentSchema
            payment_schema = PaymentSchema(
                name=payment_name,
                is_complete_payment=False  # Default to incomplete, can be updated later
            )
            payment_repo.create(payment_schema)
            
            # Get the newly created payment ID
            new_payment = payment_repo.get_by_name(payment_name)
            return new_payment.id_payment if new_payment else None
            
        except Exception as e:
            print(f"DEBUG: Error getting or creating payment {payment_name}: {str(e)}")
            return None
    
    
    def _get_product_id_by_origin(self, origin_id: int) -> Optional[int]:
        """Get product ID by origin ID"""
        try:
            from src.repository.product_repository import ProductRepository
            product_repo = ProductRepository(self.db)
            product = product_repo.get_by_origin_id(origin_id)
            return product.id_product if product else 0
        except Exception as e:
            print(f"DEBUG: Error getting product ID by origin {origin_id}: {str(e)}")
            return 0
    
    def _get_order_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get order ID by origin ID"""
        try:
            from src.repository.order_repository import OrderRepository
            order_repo = OrderRepository(self.db)
            order = order_repo.get_id_by_origin_id(origin_id)
            return order.id_order if order else 0
        except Exception as e:
            print(f"DEBUG: Error getting order ID by origin {origin_id}: {str(e)}")
            return 0
    
    def _get_default_tax_id(self) -> int:
        """
        Get default tax ID using optimized query.
        
        Returns:
            int: ID della tassa con is_default = 1, oppure 1 come fallback
        """
        try:
            from src.models.tax import Tax
            
            # Query ottimizzata: seleziona solo id_tax dove is_default = 1
            result = self.db.query(Tax.id_tax).filter(
                Tax.is_default == 1
            ).first()
            
            if result:
                return result[0]  # result è una tupla (id_tax,)
            else:
                print("WARNING: No default tax found in database, using fallback id_tax=1")
                return 1  # Default fallback
                
        except Exception as e:
            print(f"DEBUG: Error getting default tax ID: {str(e)}")
            return 1  # Default fallback

    def _get_tax_by_country(self, id_country: int) -> float:
        """Get tax percentage by country ID"""
        try:
            from src.models.tax import Tax
            
            # Check if id_country is valid
            if id_country is None or id_country == 0:
                print(f"DEBUG: Invalid country ID: {id_country}, using default tax")
                tax = self.db.query(Tax).filter(Tax.is_default == True).first()
                if tax is None:
                    print(f"DEBUG: No default tax found, using fallback")
                    return {
                        "percentage": 22.0,
                        "id_tax": 1
                    }
                return {
                    "percentage": tax.percentage if tax.percentage is not None else 22.0,
                    "id_tax": tax.id_tax
                }

            tax = self.db.query(Tax).filter(Tax.id_country == id_country).first()
            
            if tax is None:
                # No tax found for this country, try to get default tax
                tax = self.db.query(Tax).filter(Tax.is_default == True).first()
                if tax is None:
                    print(f"DEBUG: No default tax found, using fallback")
                    return {
                        "percentage": 0.0,
                        "id_tax": 1
                    }
            
            percentage = tax.percentage if tax.percentage is not None else 0.0

            
            return {
                "percentage": percentage,
                "id_tax": tax.id_tax
            }
            
        except Exception as e:
            print(f"DEBUG: Error getting tax percentage for country {id_country}: {str(e)}")
            return 22  # Default fallback to 0% tax


    def _get_country_id_by_address_id(self, address_id: int) -> Optional[int]:
        """Get country ID by address ID"""
        try:
            if not address_id or address_id == 0:
                return None
                
            from src.repository.address_repository import AddressRepository
            address_repo = AddressRepository(self.db)
            address = address_repo.get_by_id(address_id)
            if address and address.id_country:
                return address.id_country
            return None
            
        except Exception as e:
            return None
    
    
    def _get_payment_complete_status(self, payment_name: str) -> bool:
        """Get payment complete status"""
        try:
            from src.repository.payment_repository import PaymentRepository
            payment_repo = PaymentRepository(self.db)
            payment = payment_repo.get_by_name(payment_name)
            return payment.is_complete_payment if payment else True
        except Exception as e:
            print(f"DEBUG: Error getting payment complete status for {payment_name}: {str(e)}")
            return True  # Default to complete
    
    def _create_order_history(self, order_id_mapping: Dict[int, int], valid_order_data: List[Dict]) -> None:
        """Create order history entries for all orders"""
        try:
            if not order_id_mapping:
                return
            
            # Prepare order history data and remove duplicates
            order_history_values = []
            seen_combinations = set()
            
            for order_data in valid_order_data:
                order_id = order_id_mapping.get(order_data['id_origin'])
                if order_id:
                    combination = (order_id, order_data['id_order_state'])
                    if combination not in seen_combinations:
                        order_history_values.append(combination)
                        seen_combinations.add(combination)
                    else:
                        print(f"DEBUG: Skipping duplicate order history - Order ID: {order_id}, State: {order_data['id_order_state']}")
            
            # Execute bulk insert for order history
            if order_history_values:
                
                
                # Check for existing records to avoid duplicates
                existing_combinations = set()
                if order_history_values:
                    order_ids = [str(order_id) for order_id, _ in order_history_values]
                    placeholders = ','.join(order_ids)
                    existing_query = text(f"SELECT id_order, id_order_state FROM orders_history WHERE id_order IN ({placeholders})")
                    existing_records = self.db.execute(existing_query).fetchall()
                    existing_combinations = {(row.id_order, row.id_order_state) for row in existing_records}
                
                # Filter out existing combinations
                new_values = []
                for order_id, order_state in order_history_values:
                    if (order_id, order_state) not in existing_combinations:
                        new_values.append((order_id, order_state))
                    else:
                        print(f"DEBUG: Order history already exists - Order ID: {order_id}, State: {order_state}")
                
                if new_values:
                    # Build the SQL query with direct values (safer approach)
                    from datetime import datetime
                    current_datetime = datetime.now()
                    values_list = []
                    for order_id, order_state in new_values:
                        values_list.append(f"({order_id}, {order_state}, '{current_datetime.strftime('%Y-%m-%d %H:%M:%S')}')")
                    
                    sql_query = f"INSERT INTO orders_history (id_order, id_order_state, date_add) VALUES {','.join(values_list)}"
                    
                    print(f"DEBUG: Creating {len(new_values)} new order history entries (skipped {len(order_history_values) - len(new_values)} existing)")
                    
                    original_echo = self.db.bind.echo
                    self.db.bind.echo = False
                    try:
                        self.db.execute(text(sql_query))
                        self.db.commit()
                        print(f"DEBUG: Successfully created {len(new_values)} order history entries")
                    finally:
                        self.db.bind.echo = original_echo
                else:
                    print("DEBUG: No new order history entries to create (all already exist)")
                    
        except Exception as e:
            print(f"DEBUG: Error creating order history: {str(e)}")
            raise
    
    def _create_order_packages(self, order_id_mapping: Dict[int, int], valid_order_data: List[Dict]) -> None:
        """Create order packages for all orders"""
        try:
            if not order_id_mapping:
                return
            
            from src.repository.order_package_repository import OrderPackageRepository
            from src.schemas.order_package_schema import OrderPackageSchema
            
            # Initialize order package repository
            order_package_repo = OrderPackageRepository(self.db)
            
            # Create order packages for each order
            for order_data in valid_order_data:
                order_id = order_id_mapping.get(order_data['id_origin'])
                if order_id:
                    order_package_schema = OrderPackageSchema(
                        id_order=order_id,
                        height=10.0,
                        width=10.0,
                        depth=10.0,
                        length=10.0,
                        weight=1.0,
                        value=order_data['total_paid']
                    )
                    order_package_repo.create(order_package_schema)
                    
        except Exception as e:
            print(f"DEBUG: Error creating order packages: {str(e)}")
            raise
    
    async def _get_all_states(self) -> Dict[str, str]:
        """Get all states and return as dictionary {id: name}"""
        try:
            all_states = {}
            limit = 1000
            offset = 0
            
            while True:
                params = {
                    'display': '[id,name]',
                    'limit': f'{offset},{limit}'
                }
                response = await self._make_request_with_rate_limit('/api/states', params=params)
                states = self._extract_items_from_response(response, 'states')
                
                if not states:
                    break
                    
                for state in states:
                    state_id = state.get('id', '')
                    state_name = state.get('name', '')
                    if state_id:
                        all_states[state_id] = state_name
                
                # If we got less than expected, we've reached the end
                if len(states) < limit:
                    break
                    
                offset += limit
                
            return all_states
        except Exception as e:
            print(f"DEBUG: Error fetching all states: {str(e)}")
            return {}

    def _get_all_countries(self) -> Dict[int, int]:
        """
        Get all countries from our database and return as dictionary {id_origin: id_country}.
        
        Uses optimized repository method that retrieves only necessary fields without limits.
        
        Returns:
            Dict[int, int]: Mapping id_origin -> id_country
        """
        try:
            from src.repository.country_repository import CountryRepository
            
            country_repo = CountryRepository(self.db)
            
            # Use optimized method that retrieves ALL countries (no limit) with only required fields
            all_countries = country_repo.get_all_id_mappings()
            
            print(f"DEBUG: Loaded {len(all_countries)} countries from database for address mapping")

                
            return all_countries
        except Exception as e:
            print(f"DEBUG: Error fetching all countries from database: {str(e)}")
            return {}

    def _disable_foreign_key_checks(self):
        """Disable foreign key checks temporarily"""
        try:
            # Use raw SQL to disable foreign key checks
            
            result = self.db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            
            # Verify that FK checks are disabled
            check_result = self.db.execute(text("SELECT @@FOREIGN_KEY_CHECKS")).fetchone()
            print(f"DEBUG: FOREIGN_KEY_CHECKS status: {check_result}")
            
            # Also disable autocommit to ensure the setting persists
            self.db.autocommit = False
        except Exception as e:
            print(f"Error disabling foreign key checks: {e}")

    def _enable_foreign_key_checks(self):
        """Re-enable foreign key checks"""
        try:
            # Re-enable autocommit
            self.db.autocommit = True
            print("DEBUG: Autocommit enabled")
        except Exception as e:
            print(f"Error enabling foreign key checks: {e}")

    async def _get_state_name(self, state_id: str) -> str:
        """Get state name by ID"""
        if not state_id:
            return ''
        try:
            response = await self._make_request_with_rate_limit(f'/api/states/{state_id}', params={'display': '[name]'})
            state = response.get('state', {})
            return state.get('name', '')
        except:
            return ''
    
    async def _update_order_total_weight(self, order_id: int, total_weight: float):
        """Update order total weight"""
        try:
            from src.repository.order_repository import OrderRepository
            order_repo = OrderRepository(self.db)
            order = order_repo.get_by_id(order_id)
            if order:
                order.total_weight = total_weight
                order_repo.update(order, OrderUpdateSchema(total_weight=total_weight))
        except Exception as e:
            print(f"DEBUG: Error updating order total weight for {order_id}: {str(e)}")
    
    # Incremental sync methods
    async def _get_last_imported_ids(self) -> Dict[str, int]:
        """
        Get the last imported ID origin for each table
        
        Returns:
            Dict with table names as keys and last imported ID as values
        """
        last_ids = {}
        
        # Define table mappings
        table_mappings = {
            'lang': 'lang',
            'country': 'country', 
            'brand': 'brand',
            'category': 'category',
            'carrier': 'carrier',
            'product': 'product',
            'customer': 'customer',
            'address': 'address',
            'order': 'order',
            'order_detail': 'order_detail'
        }
        
        for table_name, model_name in table_mappings.items():
            try:
                # Get the maximum id_origin for each table
                query = f"""
                SELECT MAX(CAST(id_origin AS UNSIGNED)) as max_id 
                FROM {model_name}s 
                WHERE id_origin IS NOT NULL AND id_origin != ''
                """
                result = self.db.execute(text(query)).fetchone()
                last_ids[table_name] = int(result[0]) if result and result[0] else 0
            except Exception as e:
                print(f"Error getting last ID for {table_name}: {e}")
                last_ids[table_name] = 0
        
        return last_ids
    
    # Incremental sync methods for each table
    async def sync_languages_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new languages from ps_lang"""
        try:
            # Get languages from PrestaShop API with filter
            params = {'filter[id]': f'[{last_id + 1},]', 'display': '[id,name,iso_code]'}  # Get IDs greater than last_id
            response = await self._make_request_with_rate_limit('/api/languages', params)
            languages = self._extract_items_from_response(response, 'languages')
            
            results = []
            for lang in languages:
                lang_data = {
                    'lang_name': lang.get('name', ''),
                    'iso_code': lang.get('iso_code', ''),
                    'id_origin': lang.get('id', '')
                }
                
                result = await self._upsert_language(lang_data)
                results.append(result)
            
            self._log_sync_result(f"Languages (Incremental from ID {last_id})", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Languages (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_countries_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new countries from ps_country_lang"""
        try:
            # Get only new countries with all necessary fields in one call
            params = {
                'filter[id]': f'[{last_id + 1},]',
                'display': '[id,iso_code,name]'  # Get all necessary fields in one call
            }
            response = await self._make_request_with_rate_limit('/api/countries', params)
            countries = self._extract_items_from_response(response, 'countries')
            
            # Prepare all country data (no need for additional API calls)
            country_data_list = []
            for country in countries:
                id_origin = country.get('id', '')
                
                # Skip if id_origin is 0 or empty
                if not id_origin or id_origin == '0':
                    continue
                
                # Check if country already exists by id_origin
                existing_country = self._get_country_id_by_origin(id_origin)
                if existing_country:
                    continue  # Skip existing country
                
                countries_name_list = country.get('name', {})
                country['name'] = next((item['value'] for item in countries_name_list if item.get('id') == str(self.default_language_id)), '')
                country_data = {
                    'id_origin': id_origin,
                    'name': country.get('name', ''),
                    'iso_code': country.get('iso_code', '')
                }
                country_data_list.append(country_data)
            
            # Process all upserts concurrently
            if country_data_list:
                results = await asyncio.gather(*[self._upsert_country(data) for data in country_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Country {country_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result(f"Countries (Incremental from ID {last_id})", len(successful_results), errors)
                else:
                    self._log_sync_result(f"Countries (Incremental from ID {last_id})", len(successful_results))
                
                return successful_results
            else:
                self._log_sync_result(f"Countries (Incremental from ID {last_id})", 0)
                return []
            
        except Exception as e:
            self._log_sync_result(f"Countries (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_brands_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new brands from ps_manufacturer (Italian language only)"""
        try:
            # Get Italian language ID
            
            print(f"DEBUG: Using Italian language ID for incremental brands: {self.default_language_id}")
            
            # Get only new manufacturers with only necessary fields
            params = {
                'filter[id]': f'[{last_id + 1},]',
                'display': '[id,name]'  # Only necessary fields
            }
            response = await self._make_request_with_rate_limit('/api/manufacturers', params)
            manufacturers = self._extract_items_from_response(response, 'manufacturers')
            
            results = []
            
            for manufacturer in manufacturers:
                # Since we filtered by Italian language, we can directly use the name
                brand_name = manufacturer.get('name', '')
                
                # Skip brands without name
                if not brand_name or not brand_name.strip():
                    print(f"DEBUG: Skipping incremental brand {manufacturer.get('id', 'unknown')} - no name found")
                    continue
                
                brand_data = {
                    'id_origin': manufacturer.get('id', ''),
                    'name': brand_name
                }
                
                result = await self._upsert_brand(brand_data)
                results.append(result)
            
            print(f"DEBUG: Processed {len(results)} Italian brands (API filtered incremental)")
            self._log_sync_result(f"Brands (Incremental from ID {last_id}) - Italian", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Brands (Incremental from ID {last_id}) - Italian", 0, [str(e)])
            raise
    
        """Synchronize only new categories from ps_category (Italian language only)"""
        try:
            # Get Italian language ID
            
            print(f"DEBUG: Using Italian language ID for incremental categories: {self.default_language_id}")
            
            # Get only new categories with only necessary fields
            params = {
                'filter[id]': f'[{last_id + 1},]',
                'display': '[id,name]'  # Only necessary fields
            }
            response = await self._make_request_with_rate_limit('/api/categories', params)
            categories = self._extract_items_from_response(response, 'categories')
            
            results = []
            
            for category in categories:
                # Handle name field - it might be a list or string
                category_name = (next((str(i).strip() for i in category.get('name', []) if i and str(i).strip()), '') 
                 if isinstance(category.get('name', ''), list) 
                 else str(category.get('name', '')).strip())
                
                # Skip categories without name
                if not category_name:
                    print(f"DEBUG: Skipping incremental category {category.get('id', 'unknown')} - no name found")
                    continue
                
                category_data = {
                    'id_origin': category.get('id', ''),
                    'name': category_name
                }
                
                result = await self._upsert_category(category_data)
                results.append(result)
            
            print(f"DEBUG: Processed {len(results)} Italian categories (API filtered incremental)")
            self._log_sync_result(f"Categories (Incremental from ID {last_id}) - Italian", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Categories (Incremental from ID {last_id}) - Italian", 0, [str(e)])
            raise

    def _extract_items_from_response(self, response: Any, key: str) -> List[Dict[str, Any]]:
        """Extract items from API response, handling both list and dict formats"""
        
        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
        
            # Try different possible structures
            if key in response:
                items = response[key]
                
                if isinstance(items, dict):
                    # Handle nested structure like {'languages': {'language': [...]}}
                    singular_key = key.rstrip('s')  # languages -> language
                    if singular_key in items:
                        items = items[singular_key]
                        print(f"DEBUG: Found {singular_key} in nested dict")
                    else:
                        # Try other possible keys
                        for possible_key in items.keys():
                            if isinstance(items[possible_key], list):
                                items = items[possible_key]
                                break
                
                if not isinstance(items, list):
                    items = [items] if items else []
                
                return items
            else:
                # Try to find the key in a different case or similar
                for response_key in response.keys():
                    if response_key.lower() == key.lower():
                        return self._extract_items_from_response(response, response_key)
                    elif key.rstrip('s') in response_key.lower():
                        return self._extract_items_from_response(response, response_key)
                
                return []
        else:
            return []
    
    async def _get_orders_data(self) -> List[Dict[str, Any]]:
        """Get orders data with pagination to avoid server overload"""
        print("DEBUG: Fetching fresh orders data...")

        
        all_orders = []
        limit = 5000  
        offset = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        date_range_filter = self._get_date_range_filter()
        one_year_ago = self._get_one_year_ago_date()
        
        while True:
            try:
                params = {
                    'display': 'full',
                    'limit': f'{offset},{limit}'
                }

                # Always use date filter for orders sync to avoid old data
                self.new_elements = False # DEBUG, DA TOGLIERE
                if self.new_elements:
                    last_id = self.db.execute(text("SELECT MAX(id_origin) FROM orders WHERE id_origin IS NOT NULL")).scalar()
                    last_id = last_id if last_id else 0
                    params['filter[id]'] = f'>[{last_id}]'
                else:
                    params['date'] = 1
                    params['filter[date_add]'] = date_range_filter
                
                # Add timeout to prevent indefinite blocking
                try:
                    # Print complete URL with parameters
                    url_params = '&'.join([f"{k}={v}" for k, v in params.items()])
                    complete_url = f"{self.base_url}/api/orders?{url_params}&output_format=JSON"
                    print(f"PRESTASHOP ORDERS URL: {complete_url}")
                    
                    response = await asyncio.wait_for(
                        self._make_request_with_rate_limit('/api/orders', params),
                        timeout=60.0  # 60 second timeout
                    )
                except asyncio.TimeoutError:
                    raise Exception("API request timed out")
            
                
                orders_batch = self._extract_items_from_response(response, 'orders')
                if not orders_batch:
                    break
                
                
                all_orders.extend(orders_batch)
                offset += limit
                consecutive_errors = 0  # Reset error counter on success
                
                
                # Small delay between batches to be gentle with the server
                await asyncio.sleep(1)
                
            except Exception as e:
                consecutive_errors += 1
                print(f"DEBUG: Error {consecutive_errors}/{max_consecutive_errors} at offset {offset}")
                print(f"DEBUG: Error type: {type(e).__name__}")
                print(f"DEBUG: Error message: {str(e)}")
                print(f"DEBUG: Error args: {e.args if hasattr(e, 'args') else 'No args'}")
                
                # If too many consecutive errors, give up
                if consecutive_errors >= max_consecutive_errors:
                    print(f"DEBUG: Too many consecutive errors ({consecutive_errors}), stopping order fetch")
                    break
                
                error_msg = str(e).lower()
                
                # Check for memory exhaustion errors first
                if any(keyword in error_msg for keyword in ['memory', 'exhausted', 'fatal error', 'allowed memory size']):
                    print(f"DEBUG: Memory exhaustion error - reducing batch size from {limit} to {max(5, limit // 4)}")
                    limit = max(5, limit // 4)  # Reduce batch size more aggressively
                    await asyncio.sleep(15)  # Wait longer before retry
                    continue
                elif any(keyword in error_msg for keyword in ['500', 'server', 'timeout', 'connection reset', 'disconnected']):
                    print(f"DEBUG: Server error - reducing batch size from {limit} to {max(10, limit // 2)}")
                    limit = max(10, limit // 2)  # Reduce batch size
                    await asyncio.sleep(8)  # Wait before retry
                    continue
                else:
                    print(f"DEBUG: Non-server error - continuing with next batch...")
                    # Don't break, try to continue with next batch
                    offset += limit
                    await asyncio.sleep(2)
                    continue
        
        print(f"DEBUG: Fetched {len(all_orders)} orders total")
    
        
        return all_orders

    async def _process_all_orders_and_create_sql(self, all_orders: List[Dict]) -> int:
        """Process all orders and create SQL file for bulk insert"""
        try:
            
            from datetime import date
            from src.repository.shipping_repository import ShippingRepository
            from src.schemas.shipping_schema import ShippingSchema
            
            # Initialize shipping repository
            shipping_repo = ShippingRepository(self.db)
            
            # OPTIMIZATION: Two-pass approach for maximum performance
            # Pass 1: Collect all unique IDs from orders (no database queries)
            customer_origins = set()
            product_origins = set()
            address_origins = set()
            carrier_origins = set()
            # Note: payments are handled dynamically during order processing
            for order in all_orders:
                # Collect customer origins
                customer_origin = order['id_customer']
                if customer_origin and customer_origin != '0':
                    try:
                        customer_origins.add(int(customer_origin))
                    except (ValueError, TypeError):
                        pass
   
                # Collect address origins
                delivery_address = order.get('id_address_delivery',0)
                invoice_address = order.get('id_address_invoice',0)
                for addr_id in [delivery_address, invoice_address]:
                    address_origins.add(int(addr_id))
                
                # Collect carrier origins
                carrier_origin = order.get('id_carrier')
                if carrier_origin and carrier_origin != '0':
                    try:
                        carrier_origins.add(int(carrier_origin))
                    except (ValueError, TypeError):
                        pass
                
                # Collect product origins from order details (if available)
                order_details = order.get('associations', {}).get('order_rows', {})
                
                # Handle different data structures: could be dict with 'order_row' key or direct list
                if isinstance(order_details, dict):
                    if 'order_row' in order_details:
                        order_details = order_details.get('order_row', [])
                    else:
                        # If it's a dict but no 'order_row' key, treat as single item
                        order_details = [order_details] if order_details else []
                elif not isinstance(order_details, list):
                    order_details = [order_details] if order_details else []

                for detail in order_details:
                    product_origin = detail.get('product_id')
                    if product_origin and product_origin != '0':
                        try:
                            product_origins.add(int(product_origin))
                        except (ValueError, TypeError):
                            pass
                

            
            # Now pre-fetch all mappings using raw SQL queries
            all_customers = {}
            if customer_origins:
                placeholders = ','.join([':id_origin_' + str(i) for i in range(len(customer_origins))])
                params = {f'id_origin_{i}': origin for i, origin in enumerate(customer_origins)}
                query = text(f"SELECT id_customer, id_origin FROM customers WHERE id_origin IN ({placeholders})")
                result = self.db.execute(query, params)
                all_customers = {int(row.id_origin): row.id_customer for row in result}
            
            all_products = {}
            if product_origins:
                placeholders = ','.join([':id_origin_' + str(i) for i in range(len(product_origins))])
                params = {f'id_origin_{i}': origin for i, origin in enumerate(product_origins)}
                query = text(f"SELECT id_product, id_origin FROM products WHERE id_origin IN ({placeholders})")
                result = self.db.execute(query, params)
                all_products = {int(row.id_origin): row.id_product for row in result}
            
            # Note: payments are handled dynamically during order processing
            
            all_addresses = {}
            if address_origins:
                placeholders = ','.join([':id_origin_' + str(i) for i in range(len(address_origins))])
                params = {f'id_origin_{i}': origin for i, origin in enumerate(address_origins)}
                query = text(f"SELECT id_address, id_origin FROM addresses WHERE id_origin IN ({placeholders})")
                result = self.db.execute(query, params)
                all_addresses = {int(row.id_origin): row.id_address for row in result}
            
            # Pre-fetch carrier mappings (id_carrier PrestaShop = id_origin Carrier)
            all_carriers = {}
            print(f"🚚 Carrier origins found in orders: {sorted(list(carrier_origins)) if carrier_origins else 'NONE'}")
            if carrier_origins:
                placeholders = ','.join([':id_origin_' + str(i) for i in range(len(carrier_origins))])
                params = {f'id_origin_{i}': origin for i, origin in enumerate(carrier_origins)}
                query = text(f"SELECT id_carrier, id_origin FROM carriers WHERE id_origin IN ({placeholders})")
                result = self.db.execute(query, params)
                all_carriers = {int(row.id_origin): row.id_carrier for row in result}
                print(f"🚚 Pre-fetched {len(all_carriers)} carrier mappings: {all_carriers}")
                
                # Check for missing carriers
                missing_carriers = carrier_origins - set(all_carriers.keys())
                if missing_carriers:
                    print(f"⚠️ {len(missing_carriers)} carriers NOT in DB: {sorted(list(missing_carriers))}")
            else:
                print("⚠️ No carrier origins collected from orders!")
            
            # Pre-fetch all taxes using raw SQL
            all_taxes = {}
            default_tax_id = self._get_default_tax_id()
            query = text("SELECT id_tax, id_country, is_default FROM taxes")
            result = self.db.execute(query)
            for row in result:
                if row.id_country is not None:
                    all_taxes[row.id_country] = row.id_tax
            print(f"DEBUG: Default tax ID: {default_tax_id}")

            # Pre-fetch product weights using raw SQL
            product_weight_mapping = {}
            if product_origins:
                placeholders = ','.join([':id_origin_' + str(i) for i in range(len(product_origins))])
                params = {f'id_origin_{i}': origin for i, origin in enumerate(product_origins)}
                query = text(f"SELECT id_origin, weight FROM products WHERE id_origin IN ({placeholders})")
                result = self.db.execute(query, params)
                product_weight_mapping = {int(row.id_origin): float(row.weight) if row.weight else 0.0 for row in result}
                        
            # Pass 2: Process orders using pre-fetched mappings (fast in-memory lookups)
            valid_order_data = []
            valid_order_detail_data = []
            order_detail_to_order_mapping = []  # Track which order each detail belongs to
            total_errors = 0
            
            # Initialize payment repository once for all orders
            from src.repository.payment_repository import PaymentRepository
            payment_repo = PaymentRepository(self.db)
            
            for order in all_orders:
                try:
                    # Get order data
                    order_id_origin = safe_int(order.get('id', 0))
                    customer_origin = safe_int(order.get('id_customer', 0))
                    delivery_address_origin = safe_int(order.get('id_address_delivery', 0))
                    invoice_address_origin = safe_int(order.get('id_address_invoice', 0))
                    payment_name = order.get('payment', '')
                    reference = order.get('reference', None)
                    
                    # Validate required fields
                    if not order_id_origin or not customer_origin:
                        total_errors += 1
                        continue
                    
                    # Get mapped IDs
                    customer_id = all_customers.get(customer_origin)
                    delivery_address_id = all_addresses.get(delivery_address_origin)
                    invoice_address_id = all_addresses.get(invoice_address_origin)
                    payment_id = await self._get_or_create_payment_id(payment_name, payment_repo)
                    total_paid_tax_excl = safe_float(order.get('total_paid_tax_excl', 0))
                    total_paid = safe_float(order.get('total_paid', 0))
                    
                    # Extract shipping data
                    total_shipping_tax_escl = safe_float(order.get('total_shipping_tax_excl', 0))
                    shipping_tax_rate = safe_float(order.get('carrier_tax_rate', 0))
        
                    
                    # Calculate total shipping price with tax included
                    # total_shipping_price deve essere il prezzo finale comprensivo di tassa
                    # Formula: price_tax_incl = total_shipping_tax_escl + (total_shipping_tax_escl * shipping_tax_rate / 100)
                    # Simplified: price_tax_incl = total_shipping_tax_escl * (1 + shipping_tax_rate / 100)
                    # Esempio: 10€ senza tassa + 22% tassa = 10 * (1 + 22/100) = 10 * 1.22 = 12.20€
                    total_shipping_price = total_shipping_tax_escl * (1 + shipping_tax_rate / 100)
                    if not customer_id:
                        total_errors += 1
                        continue
                    
                    # Get country ID from delivery address for tax calculation
                    id_country = self._get_country_id_by_address_id(delivery_address_id) if delivery_address_id else None
                    is_payed = self._get_payment_complete_status(payment_name)
                    # Get tax ID: first try country-specific, then default
                    if id_country and id_country in all_taxes:
                        id_tax = all_taxes[id_country]
                    else:
                        id_tax = default_tax_id
                    
                    # Final fallback if no default tax is configured
                    if id_tax is None:
                        id_tax = 1

                    # Map carrier (id_carrier PrestaShop = id_origin Carrier)
                    carrier_id = 0  # Default
                    carrier_origin = safe_int(order.get('id_carrier', 0))
                    if carrier_origin and carrier_origin > 0:
                        if carrier_origin in all_carriers:
                            carrier_id = all_carriers[carrier_origin]
                        else:
                            print(f"⚠️ Order {order_id_origin}: Carrier origin {carrier_origin} NOT found in DB")

                    # Prepare complete order data
                    order_data = {
                        'id_origin': order_id_origin,
                        'reference': reference,
                        'address_delivery': delivery_address_id,
                        'address_invoice': invoice_address_id,
                        'customer': customer_id,
                        'id_platform': self.platform_id,
                        'id_payment': payment_id,
                        'id_carrier': carrier_id,
                        'sectional': 1,  # Default
                        'id_order_state': 1,  # Default
                        'is_invoice_requested': order.get('fattura', 0),
                        'payed': is_payed,
                        'date_payment': None,  # Default
                        'total_price_tax_excl': total_paid_tax_excl,
                        'total_paid': total_paid,
                        'total_discounts': safe_float(order.get('total_discounts', 0.0)),
                        'cash_on_delivery': 0,  #TODO: controllare
                        'insured_value': 0,  # Default
                        'privacy_note': None,
                        'note': order.get('order_note', ''),
                        'delivery_date': None,
                        'date_add': str(self._parse_prestashop_datetime(order.get('date_add', '')))
                    }
                    
                    order_total_weight = 0.0
                    
                    order_details = order.get('associations', {}).get('order_rows', {})
                    # Process order details for order_detail_data creation
                    for detail in order_details:
                        try:
                            product_origin = safe_int(detail.get('product_id', 0))
                            product_quantity = safe_int(detail.get('product_quantity', 0))
                            
                            # Get product weight from mapping using id_origin
                            product_weight = product_weight_mapping.get(product_origin, 0.0)
                            
                            if not product_origin:
                                continue
                            
                            product_id = all_products.get(product_origin)
                            if not product_id:
                                continue
                            
                            # Get product weight from mapping
                            order_total_weight += product_weight * product_quantity
                            
                            # Get tax information for the country from pre-fetched dictionary
                            if id_tax is None:
                                id_tax = 1  # Fallback
                            
                            # Recupera prezzi da order_rows
                            # product_price: prezzo unitario ORIGINALE (no sconto, no IVA)
                            # unit_price_tax_excl: prezzo unitario SCONTATO (con sconto, no IVA)
                            product_price_original = safe_float(detail.get('product_price', 0.0))
                            unit_price_tax_excl = safe_float(detail.get('unit_price_tax_excl', 0.0))
                            price_difference = product_price_original - unit_price_tax_excl
                            
                            # Inizializza valori sconto
                            reduction_percent = 0.0
                            reduction_amount = 0.0
                            
                            # Se c'è differenza di prezzo, cerca sconti nell'API order_details
                            if price_difference > 0:
                                try:
                                    # Chiama API order_details per questo ordine
                                    order_details_response = await self._get_order_details_discounts(order_id_origin)
                                    if order_details_response:
                                        # Cerca il prodotto specifico nella risposta
                                        product_reference = detail.get('product_reference', '')
                                        for order_detail in order_details_response:
                                            if order_detail.get('product_reference') == product_reference:
                                                reduction_percent = safe_float(order_detail.get('reduction_percent', 0.0))
                                                reduction_amount = safe_float(order_detail.get('reduction_amount_tax_excl', 0.0))
                                                break
                                except Exception as e:
                                    print(f"⚠️ Errore nel recupero sconti per ordine {order_id_origin}: {e}")
                            
                            # Prepare complete order detail data
                            # IMPORTANTE: product_price deve essere il prezzo ORIGINALE senza sconto
                            order_detail_data = {
                                'id_origin': detail.get('id', 0),
                                'id_order': None,  # Will be set after order insert
                                'id_order_document': 0,
                                'id_product': product_id,
                                'product_name': detail.get('product_name', 'ND'),
                                'product_reference': detail.get('product_reference', 'ND'),
                                'product_qty': product_quantity,
                                'product_weight': product_weight,
                                'product_price': product_price_original,  # Prezzo ORIGINALE senza sconto
                                'id_tax': id_tax,
                                'reduction_percent': reduction_percent,
                                'reduction_amount': reduction_amount,
                                'rda': None
                            }

                            valid_order_detail_data.append(order_detail_data)
                            order_detail_to_order_mapping.append(order_data['id_origin'])  # Track which order this detail belongs to
                            
                        except Exception as e:
                            print(f"DEBUG: Error processing order detail: {str(e)}")
                            continue
                    
                    order_data['total_weight'] = order_total_weight
                    
                    # Automatic carrier assignment logic
                    assigned_carrier_api_id = await self._assign_carrier_api(
                        order=order,
                        order_total_weight=order_total_weight,
                        delivery_address_id=order_data.get('id_address_delivery')
                    )
                    
                    order_data['shipping'] = shipping_repo.create_and_get_id(ShippingSchema(
                        id_carrier_api=assigned_carrier_api_id,
                        id_shipping_state=1,
                        id_tax=default_tax_id,
                        tracking=None,
                        weight=order_total_weight,
                        price_tax_incl=total_shipping_price, 
                        price_tax_excl=safe_float(order.get('total_shipping_tax_excl', 0))
                    ))
                    valid_order_data.append(order_data)
                                        
                except Exception as e:
                    print(f"DEBUG: Error processing order {order.get('id', 'unknown')}: {str(e)}")
                    total_errors += 1
                    continue

            if not valid_order_data:
                print("DEBUG: No valid orders to insert - valid_order_data is empty")
                return 0
            
            # Create SQL file for orders
            orders_sql_file = "temp_orders_insert.sql"
            with open(orders_sql_file, 'w', encoding='utf-8') as f:
                f.write("-- Orders bulk insert\n")
                f.write("INSERT INTO orders (id_origin, reference, id_address_delivery, id_address_invoice, id_customer, id_platform, id_payment, id_carrier, id_shipping, id_sectional, id_order_state, is_invoice_requested, is_payed, payment_date, total_weight, total_price_tax_excl, total_paid, total_discounts, cash_on_delivery, insured_value, privacy_note, general_note, delivery_date, date_add) VALUES\n")
                
                for i, order_data in enumerate(valid_order_data):
                    comma = "," if i < len(valid_order_data) - 1 else ";"
                    f.write(f"({order_data['id_origin']}, {sql_value(order_data['reference'])}, {sql_value(order_data['address_delivery'])}, {sql_value(order_data['address_invoice'])}, {order_data['customer']}, {order_data['id_platform']}, {sql_value(order_data['id_payment'])}, {order_data.get('id_carrier', 0)}, {order_data['shipping']}, {order_data['sectional']}, {order_data['id_order_state']}, {order_data['is_invoice_requested']}, {order_data['payed']}, {sql_value(order_data['date_payment'])}, {order_data['total_weight']}, {order_data['total_price_tax_excl']}, {order_data['total_paid']}, {order_data['total_discounts']}, {order_data['cash_on_delivery']}, {order_data['insured_value']}, {sql_value(order_data['privacy_note'])}, {sql_value(order_data['note'])}, {sql_value(order_data['delivery_date'])}, {sql_value(order_data['date_add'])}){comma}\n")
            
            # Execute orders SQL file
            with open(orders_sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
                # Temporarily disable echo to prevent SQL output
                original_echo = self.db.bind.echo
                self.db.bind.echo = False
                try:
                    self.db.execute(text(sql_content))
                    self.db.commit()
                finally:
                    self.db.bind.echo = original_echo
            
            # Get the inserted order IDs
            inserted_orders = self.db.execute(text("SELECT id_order, id_origin FROM orders WHERE id_origin IN :origins"), 
                                            {"origins": [order['id_origin'] for order in valid_order_data]}).fetchall()
            order_id_mapping = {row.id_origin: row.id_order for row in inserted_orders}
            
            # Create order history entries
            self._create_order_history(order_id_mapping, valid_order_data)
            
            # Create order packages
            self._create_order_packages(order_id_mapping, valid_order_data)
            
            # Update order detail data with order IDs using the tracking mapping
            for i, detail in enumerate(valid_order_detail_data):
                if i < len(order_detail_to_order_mapping):
                    order_origin_id = order_detail_to_order_mapping[i]
                    if order_origin_id in order_id_mapping:
                        detail['id_order'] = order_id_mapping[order_origin_id]
                    else:
                        print(f"DEBUG: Warning - Could not find order ID for detail {detail['id_origin']} (order origin {order_origin_id})")
                else:
                    print(f"DEBUG: Warning - No mapping found for order detail {detail['id_origin']}")
            
            # Create SQL file for order details
            if valid_order_detail_data:
                details_sql_file = "temp_order_details_insert.sql"
                with open(details_sql_file, 'w', encoding='utf-8') as f:
                    f.write("-- Order details bulk insert\n")
                    f.write("INSERT INTO order_details (id_origin, id_order, id_order_document, id_product, product_name, product_reference, product_qty, product_weight, product_price, id_tax, reduction_percent, reduction_amount, rda) VALUES\n")
                    
                    for i, detail_data in enumerate(valid_order_detail_data):
                        if detail_data['id_order']:  # Only include details with valid order IDs
                            comma = "," if i < len(valid_order_detail_data) - 1 else ";"
                            f.write(f"({detail_data['id_origin']}, {detail_data['id_order']}, {sql_value(detail_data['id_order_document'])}, {detail_data['id_product']}, {sql_value(detail_data['product_name'])}, {sql_value(detail_data['product_reference'])}, {detail_data['product_qty']}, {detail_data['product_weight']}, {detail_data['product_price']}, {sql_value(detail_data['id_tax'])}, {detail_data['reduction_percent']}, {detail_data['reduction_amount']}, {sql_value(detail_data['rda'])}){comma}\n")
                
                # Execute order details SQL file
                with open(details_sql_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                    # Temporarily disable echo to prevent SQL output
                    original_echo = self.db.bind.echo
                    self.db.bind.echo = False
                    try:
                        self.db.execute(text(sql_content))
                        self.db.commit()
                    finally:
                        self.db.bind.echo = original_echo
                
                # Clean up order details SQL file
                import os
                if os.path.exists(details_sql_file):
                    os.remove(details_sql_file)
            
            # Clean up orders SQL file
            import os
            if os.path.exists(orders_sql_file):
                os.remove(orders_sql_file)
            
            print(f"DEBUG: Successfully inserted {len(valid_order_data)} orders, {len(valid_order_data)} shipments, {len(valid_order_data)} order history entries, {len(valid_order_data)} order packages, and {len(valid_order_detail_data)} order details")
            
            return len(valid_order_data)
            
        except Exception as e:
            print(f"DEBUG: Error in _process_all_orders_and_create_sql: {str(e)}")
            raise

    async def _get_payments_data(self) -> List[Dict[str, Any]]:
        """Get orders data with only payment field for payment method extraction"""
        try:            
            all_orders = []
            limit = 2500  # Start with smaller batch size to avoid memory issues
            offset = 0
            
            while True:
                try:
                    # Request only the payment field to optimize the API call
                    params = {
                        'display': '[payment]',
                        'limit': f'{offset},{limit}'  # Add pagination
                    }
                    

                    response = await self._make_request_with_rate_limit('/api/orders', params)
                    orders_batch = self._extract_items_from_response(response, 'orders')
                    
                    if not orders_batch:
                        print(f"DEBUG: No more orders found at offset {offset}")
                        break
                    
                    all_orders.extend(orders_batch)
                    offset += limit
                    
                    
                    # Longer delay between batches to be gentle with the server
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    # Debug: Print full error details
                    print(f"DEBUG: Full error details for payment data at offset {offset}:")
                    print(f"DEBUG: Error type: {type(e).__name__}")
                    print(f"DEBUG: Error message: {str(e)}")
                    print(f"DEBUG: Error args: {e.args if hasattr(e, 'args') else 'No args'}")
                    
                    error_msg = str(e).lower()
                    
                    # Check for memory exhaustion errors
                    if any(keyword in error_msg for keyword in ['memory', 'exhausted', 'fatal error', 'allowed memory size']):
                        print(f"DEBUG: Memory exhaustion error at offset {offset}, reducing batch size significantly...")
                        limit = max(10, limit // 4)  # Reduce batch size more aggressively
                        await asyncio.sleep(5)  # Wait longer before retry
                        continue
                    elif any(keyword in error_msg for keyword in ['500', 'server', 'timeout', 'connection reset', 'disconnected']):
                        print(f"DEBUG: Server error at offset {offset}, retrying with smaller batch...")
                        limit = max(10, limit // 2)  # Reduce batch size
                        await asyncio.sleep(3)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Non-server error at offset {offset}, continuing with next batch...")
                        # Don't break, try to continue with next batch
                        offset += limit
                        await asyncio.sleep(1)
                        continue
            
            print(f"DEBUG: Total orders fetched for payment extraction: {len(all_orders)}")
            return all_orders
            
        except Exception as e:
            print(f"DEBUG: Error in _get_payments_data: {str(e)}")
            raise
        
    def _filter_orders_by_date(self, orders: List[Dict[str, Any]], cutoff_date: str) -> List[Dict[str, Any]]:
        """Filter orders by date on client side if API filter doesn't work"""
        from datetime import datetime
        
        try:
            cutoff_datetime = datetime.strptime(cutoff_date, '%Y-%m-%d')
            filtered_orders = []
            
            for order in orders:
                order_date_str = order.get('date_add', '')
                if order_date_str:
                    try:
                        # Handle different date formats
                        if ' ' in order_date_str:
                            order_date = datetime.strptime(order_date_str.split(' ')[0], '%Y-%m-%d')
                        else:
                            order_date = datetime.strptime(order_date_str, '%Y-%m-%d')
                        
                        if order_date >= cutoff_datetime:
                            filtered_orders.append(order)
                    except ValueError:
                        # Skip orders with invalid date format
                        continue
            
            print(f"DEBUG: Client-side filtering: {len(orders)} -> {len(filtered_orders)} orders (cutoff: {cutoff_date})")
            return filtered_orders
            
        except Exception as e:
            print(f"DEBUG: Error in client-side date filtering: {str(e)}")
            return orders
    
    
    async def sync_order_details(self) -> List[Dict[str, Any]]:
        """Synchronize order details"""
        pass
    
    async def _get_order_details_discounts(self, order_id_origin: int) -> List[Dict[str, Any]]:
        """
        Recupera i dati di sconto per un ordine specifico dall'API order_details
        
        Args:
            order_id_origin (int): ID dell'ordine in PrestaShop
            
        Returns:
            List[Dict[str, Any]]: Lista dei dettagli ordine con sconti
        """
        try:
            # Costruisce i parametri per l'API order_details
            params = {
                'filter[id_order]': f'[{order_id_origin}]',
                'display': '[product_reference,reduction_amount,reduction_percent,reduction_amount_tax_excl]',
                'output_format': 'JSON'
            }
            
            # Utilizza la funzione esistente con rate limiting (passa solo l'endpoint)
            response = await self._make_request_with_rate_limit('/api/order_details', params)
            if response and 'order_details' in response:
                return response['order_details']
            else:
                return []
                
        except Exception as e:
            print(f"⚠️ Errore nella chiamata API order_details per ordine {order_id_origin}: {e}")
            return []
    def _print_final_sync_summary(self, sync_results: Dict[str, Any], is_incremental: bool = False):
        """Print a comprehensive summary of the synchronization results"""
        sync_type = "INCREMENTAL" if is_incremental else "FULL"
        
        print("\n" + "="*80)
        print(f"🔄 PRESTASHOP {sync_type} SYNC COMPLETED")
        print("="*80)
        
        # Overall status
        status_emoji = "✅" if sync_results['status'] == 'SUCCESS' else "⚠️" if sync_results['status'] == 'PARTIAL' else "❌"
        print(f"{status_emoji} Status: {sync_results['status']}")
        
        # Timing
        start_time = datetime.fromisoformat(sync_results['start_time'])
        end_time = datetime.fromisoformat(sync_results['end_time'])
        duration = end_time - start_time
        
        print(f"⏱️  Duration: {duration}")
        print(f"🕐 Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Totals
        print(f"\n📊 TOTALS:")
        print(f"   📈 Records Processed: {sync_results['total_processed']:,}")
        print(f"   ❌ Errors: {sync_results['total_errors']}")
        
        # Phase breakdown
        print(f"\n📋 PHASE BREAKDOWN:")
        for i, phase in enumerate(sync_results['phases'], 1):
            phase_emoji = "✅" if phase['total_errors'] == 0 else "⚠️"
            phase_name = phase.get('phase_name', f'Phase {i}')
            print(f"   {phase_emoji} {phase_name}")
            print(f"      📈 Processed: {phase['total_processed']:,}")
            print(f"      ❌ Errors: {phase['total_errors']}")
            
            # Show individual table results
            if 'results' in phase:
                for table_result in phase['results']:
                    table_emoji = "✅" if table_result['errors'] == 0 else "❌"
                    print(f"      {table_emoji} {table_result['table_name']}: {table_result['processed']:,} records")
                    if table_result['errors'] > 0:
                        for error in table_result['error_details']:
                            print(f"         ⚠️  {error}")
        
        # Last IDs for incremental sync
        if is_incremental and 'last_ids' in sync_results:
            print(f"\n🆔 LAST IMPORTED IDs:")
            for table, last_id in sync_results['last_ids'].items():
                print(f"   {table}: {last_id}")
        
        # Error summary if any
        if sync_results['total_errors'] > 0:
            print(f"\n⚠️  ERROR SUMMARY:")
            for i, phase in enumerate(sync_results['phases'], 1):
                if phase['total_errors'] > 0:
                    phase_name = phase.get('phase_name', f'Phase {i}')
                    print(f"   📋 {phase_name}:")
                    if 'results' in phase:
                        for table_result in phase['results']:
                            if table_result['errors'] > 0:
                                print(f"      ❌ {table_result['table_name']}: {table_result['errors']} errors")
                                for error in table_result['error_details']:
                                    print(f"         • {error}")
        
        print("="*80)
        print(f"🎯 {sync_type} SYNC SUMMARY COMPLETE")
        print("="*80 + "\n")
    
    def _print_error_summary(self, sync_results: Dict[str, Any], error_message: str):
        """Print error summary when sync fails completely"""
        print("\n" + "="*80)
        print("❌ PRESTASHOP SYNC FAILED")
        print("="*80)
        print(f"💥 Error: {error_message}")
        
        if 'start_time' in sync_results:
            start_time = datetime.fromisoformat(sync_results['start_time'])
            end_time = datetime.fromisoformat(sync_results['end_time'])
            duration = end_time - start_time
            print(f"⏱️  Duration before failure: {duration}")
        
        if sync_results.get('total_processed', 0) > 0:
            print(f"📈 Records processed before failure: {sync_results['total_processed']:,}")
        
        print("="*80 + "\n")

    async def _assign_carrier_api(self, order: Dict, order_total_weight: float, 
                                delivery_address_id: Optional[int] = None) -> int:
        """
        Assegna automaticamente un carrier API basato sulle regole di CarrierAssignment
        
        Args:
            order: Dati dell'ordine da PrestaShop
            order_total_weight: Peso totale dell'ordine
            delivery_address_id: ID dell'indirizzo di consegna
            invoice_address_id: ID dell'indirizzo di fatturazione
            
        Returns:
            int: ID del carrier API assegnato (default: 1 se nessuna regola corrisponde)
        """
        try:
            from src.repository.carrier_assignment_repository import CarrierAssignmentRepository
            
            
            # Inizializza la repository
            carrier_assignment_repo = CarrierAssignmentRepository(self.db)
            
            # Estrai informazioni dall'ordine per la ricerca
            postal_code = None
            country_id = None
            origin_carrier_id = None
            
            # Prova a ottenere il codice postale dall'indirizzo di consegna
            if delivery_address_id:
                try:
                    query = text("SELECT postcode, id_country FROM addresses WHERE id_address = :address_id")
                    result = self.db.execute(query, {"address_id": delivery_address_id}).fetchone()
                    print(result)
                    if result:
                        postal_code = result.postcode
                        country_id = result.id_country
                except Exception as e:
                    pass
            
            
            # Estrai l'ID del corriere di origine dall'ordine PrestaShop
            origin_carrier_id = order.get('id_carrier')
            if origin_carrier_id:
                try:
                    origin_carrier_id = int(origin_carrier_id)
                except (ValueError, TypeError):
                    origin_carrier_id = None
            
            # Cerca un'assegnazione che corrisponde ai criteri
            assignment = carrier_assignment_repo.find_matching_assignment(
                postal_code=postal_code,
                country_id=country_id,
                origin_carrier_id=origin_carrier_id,
                weight=order_total_weight
            )
            
            if assignment:
                return assignment.id_carrier_api
            else:
                return None  # Nessuna assegnazione trovata
                
        except Exception as e:
            print(f"DEBUG: Error in carrier assignment logic: {str(e)}")
            return None  # Nessuna assegnazione in caso di errore
