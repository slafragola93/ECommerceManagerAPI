"""
PrestaShop synchronization service
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import base64
import asyncio
from datetime import datetime

from .base_ecommerce_service import BaseEcommerceService
from ...repository.platform_repository import PlatformRepository


class PrestaShopService(BaseEcommerceService):
    """
    PrestaShop synchronization service implementation
    """
    
    def __init__(self, db: Session, platform_id: int = 1, batch_size: int = 5000, max_concurrent_requests: int = 10, default_language_id: int = 1):
        super().__init__(db, platform_id, batch_size)
        self.platform_repo = PlatformRepository(db)
        self._orders_cache = None  # Cache for orders data
        self.max_concurrent_requests = max_concurrent_requests
        self._semaphore = None  # Will be initialized in async context
        self.default_language_id = default_language_id
    
    def _get_six_months_ago_date(self) -> str:
        """Get date string for six months ago in YYYY-MM-DD format"""
        from datetime import timedelta
        six_months_ago = datetime.now() - timedelta(days=180)  # 6 months
        return six_months_ago.strftime('%Y-%m-%d')
    
    def _get_date_range_filter(self) -> str:
        """Get date range filter string for PrestaShop API [start_date,end_date]"""
        from datetime import timedelta
        six_months_ago = datetime.now() - timedelta(days=180)  # 6 months ago
        today = datetime.now()
        
        start_date = six_months_ago.strftime('%Y-%m-%d')
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
            return await self._make_request(endpoint, params)
    
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
            
            # Phase 1: Base tables (no dependencies)
            phase1_results = await self._sync_phase("Phase 1 - Base Tables", [
                #self.sync_languages,
                #self.sync_countries,
                #self.sync_brands,
                #self.sync_categories,
                #self.sync_carriers,
                #self.sync_tags
            ])
            sync_results['phases'].append(phase1_results)
            
            # Phase 2: Dependent tables
            phase2_results = await self._sync_phase("Phase 2 - Dependent Tables", [
                #self.sync_products,
                #self.sync_customers,
                #self.sync_payments,
                #lambda: self.sync_addresses()
            ])
            sync_results['phases'].append(phase2_results)
            
            # Phase 3: Complex tables
            phase3_results = await self._sync_phase("Phase 3 - Complex Tables", [
                self.sync_orders,
                #self.sync_product_tags,
                #self.sync_order_details
            ])
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
    
    async def sync_incremental_data(self) -> Dict[str, Any]:
        """
        Synchronize only new data from PrestaShop based on last imported ID origin
        """
        sync_results = {
            'start_time': datetime.now().isoformat(),
            'phases': [],
            'total_processed': 0,
            'total_errors': 0,
            'incremental': True
        }
        
        try:
            # Disable foreign key checks for the entire incremental synchronization
            self._disable_foreign_key_checks()
            
            # Get last imported IDs for each table
            last_ids = await self._get_last_imported_ids()
            
            print(f"Starting incremental sync with last IDs: {last_ids}")
            
            # Phase 1: Base tables (no dependencies) - incremental
            phase1_results = await self._sync_phase("Phase 1 - Base Tables (Incremental)", [
                lambda: self.sync_languages_incremental(last_ids.get('lang', 0)),
                lambda: self.sync_countries_incremental(last_ids.get('country', 0)),
                lambda: self.sync_brands_incremental(last_ids.get('brand', 0)),
                lambda: self.sync_categories_incremental(last_ids.get('category', 0)),
                lambda: self.sync_carriers_incremental(last_ids.get('carrier', 0)),
                lambda: self.sync_tags_incremental(last_ids.get('tag', 0))
            ])
            sync_results['phases'].append(phase1_results)
            
            # Phase 2: Dependent tables - incremental
            phase2_results = await self._sync_phase("Phase 2 - Dependent Tables (Incremental)", [
                lambda: self.sync_products_incremental(last_ids.get('product', 0)),
                lambda: self.sync_customers_incremental(last_ids.get('customer', 0)),
                lambda: self.sync_payments_incremental(),  # Payments don't have incremental logic
                lambda: self.sync_addresses_incremental(last_ids.get('address', 0))
            ])
            sync_results['phases'].append(phase2_results)
            
            # Phase 3: Complex tables - incremental
            phase3_results = await self._sync_phase("Phase 3 - Complex Tables (Incremental)", [
                lambda: self.sync_orders_incremental(last_ids.get('order', 0)),
                lambda: self.sync_product_tags_incremental(last_ids.get('product_tag', 0)),
                lambda: self.sync_order_details_incremental(last_ids.get('order_detail', 0))
            ])
            sync_results['phases'].append(phase3_results)
            
            # Calculate totals
            for phase in sync_results['phases']:
                sync_results['total_processed'] += phase['total_processed']
                sync_results['total_errors'] += phase['total_errors']
            
            sync_results['end_time'] = datetime.now().isoformat()
            sync_results['status'] = 'SUCCESS' if sync_results['total_errors'] == 0 else 'PARTIAL'
            sync_results['last_ids'] = last_ids
            
            # Add final debug summary for incremental sync
            self._print_final_sync_summary(sync_results, is_incremental=True)
            
        except Exception as e:
            sync_results['end_time'] = datetime.now().isoformat()
            sync_results['status'] = 'ERROR'
            sync_results['error'] = str(e)
            raise
        finally:
            # Re-enable foreign key checks
            self._enable_foreign_key_checks()
        
        return sync_results
    
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
                'display': '[id,iso_code,name]'  # Get all necessary fields in one call
            }
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
            response = await self._make_request_with_rate_limit('/api/carriers', params={'display': '[id,name]'})
            carriers = self._extract_items_from_response(response, 'carriers')
            
            # Prepare all carrier data
            carrier_data_list = []
            for carrier in carriers:
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
                self._log_sync_result("Carriers", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Carriers", 0, [str(e)])
            raise
    
    async def sync_tags(self) -> List[Dict[str, Any]]:
        """Synchronize tags from ps_tag"""
        try:
            response = await self._make_request_with_rate_limit('/api/tags', params={'display': '[id,name]'})
            tags = self._extract_items_from_response(response, 'tags')
            # Prepare all tag data
            tag_data_list = []
            for tag in tags:
                tag_data = {
                    'id_origin': tag.get('id', ''),
                    'name': tag.get('name', '')
                }
                tag_data_list.append(tag_data)
            
            # Process all upserts concurrently
            if tag_data_list:
                results = await asyncio.gather(*[self._upsert_tag(data) for data in tag_data_list], return_exceptions=True)
                
                # Filter out exceptions and log them
                successful_results = []
                errors = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Tag {tag_data_list[i].get('id_origin', 'unknown')}: {str(result)}")
                    else:
                        successful_results.append(result)
                
                if errors:
                    self._log_sync_result("Tags", len(successful_results), errors)
                else:
                    self._log_sync_result("Tags", len(successful_results))
                
                return successful_results
            else:
                self._log_sync_result("Tags", 0)
                return []
            
        except Exception as e:
            self._log_sync_result("Tags", 0, [str(e)])
            raise
    
    async def sync_products(self) -> List[Dict[str, Any]]:
        """Synchronize products from ps_product (Italian language only)"""
        try:
            # Get Italian language ID
            
            
            # Try with pagination to avoid server disconnection
            all_products = []
            limit = 1000  # Smaller batch size
            offset = 0
            
            while True:
                try:
                    # Include only necessary fields to reduce response size
                    # Use PrestaShop format: limit=[offset,]limit
                    params = {
                        'limit': f'{offset},{limit}',
                        'display': '[id,id_manufacturer,id_category_default,name,reference]'  # Only necessary fields
                    }
                    response = await self._make_request_with_rate_limit('/api/products', params)
                    products = self._extract_items_from_response(response, 'products')
                    
                    if not products:
                        break
                        
                    all_products.extend(products)
                    offset += limit
                    
                    # Small delay to avoid overwhelming the server
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['server disconnected', '500', 'timeout', 'connection reset']):
                        print(f"DEBUG: Server error for products, retrying with smaller batch...")
                        limit = max(10, limit // 2)  # Reduce batch size
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Error fetching products at offset {offset}: {str(e)}")
                        raise
            
            # Deduplicate products by ID and filter for Italian language
            unique_products = {}
            for product in all_products:
                product_name_list = product.get('name', {})
                product['name'] = next((item['value'] for item in product_name_list if item.get('id') == str(self.default_language_id)), '')
                product_id = product.get('id', '')
                if not product_id:
                    continue
                

                unique_products[product_id] = product
            
            products = list(unique_products.values())
            
            # Prepare all product data with async lookups
            async def prepare_product_data(product):                
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
                
                return {
                    'id_origin': product.get('id', ''),
                    'id_platform': 1,  # TODO: review this logic
                    'id_category': int(category_id),
                    'id_brand': int(brand_id),
                    'name': product['name'],
                    'sku': product.get('reference', ''),
                    'type': product_type
                }
                
            # Prepare all product data concurrently
            product_data_list = await asyncio.gather(*[prepare_product_data(product) for product in products], return_exceptions=True)
            
            # Filter out None values and exceptions
            valid_product_data = []
            errors = []
            for i, result in enumerate(product_data_list):
                if isinstance(result, Exception):
                    errors.append(f"Product {products[i].get('id', 'unknown')}: {str(result)}")
                elif result is not None:
                    valid_product_data.append(result)
            
            # Bulk insert products for better performance
            if valid_product_data:
                from src.repository.product_repository import ProductRepository
                from src.schemas.product_schema import ProductSchema
                
                product_repo = ProductRepository(self.db)
                
                # Convert to ProductSchema objects
                product_schemas = []
                for data in valid_product_data:
                    product_schema = ProductSchema(
                        id_origin=data.get('id_origin', 0),
                        id_platform=data.get('id_platform', 1),
                        id_category=data.get('id_category', 1),
                        id_brand=data.get('id_brand', 1),
                        name=data.get('name', ''),
                        sku=data.get('sku', ''),
                        type=data.get('type', 'standard')
                    )
                    product_schemas.append(product_schema)
                
                # Bulk insert
                total_inserted = product_repo.bulk_create(product_schemas, batch_size=10000)
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
    
    async def sync_customers(self) -> List[Dict[str, Any]]:
        """Synchronize customers from ps_customer"""
        try:
            all_customers = []
            limit = 5000
            offset = 0
            
            while True:
                params = {
                    'display': '[id,firstname,lastname,email]',
                    'limit': f'{offset},{limit}'
                }
                
                response = await self._make_request_with_rate_limit('/api/customers', params)
                customers = self._extract_items_from_response(response, 'customers')
                
                if not customers:
                    break
                    
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
                from src.repository.customer_repository import CustomerRepository
                from src.schemas.customer_schema import CustomerSchema
                
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
        try:
            orders = await self._get_orders_data()  # Use cached data
            
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
                    'is_complete_payment': 1  #TODO: Review this logic
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
                country_origin_id = str(address.get('id_country', ''))
                country_data = all_countries.get(country_origin_id, {})
                country_id = int(country_data.get('id')) if country_data.get('id') else None
                
                # Get customer ID (still need to call this as it's not pre-fetched)
                customer_id = int(self._get_customer_id_by_origin(address.get('id_customer', '')) if self._get_customer_id_by_origin(address.get('id_customer', '')) is not None else None)
                return {
                    'id_origin': address.get('id', 0),
                    'id_country': country_id,
                    'id_customer': customer_id,
                    'company': address.get('company', ''),
                    'firstname': address.get('firstname', ''),
                    'lastname': address.get('lastname', ''),
                    'address1': address.get('address1', ''),
                    'address2': address.get('address2', ''),
                    'state': state_name,
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
            import tempfile
            import os
            from sqlalchemy import text
            from datetime import date
            
            print("DEBUG: Processing all addresses and creating SQL file...")
            
            # Pre-fetch all customer IDs to avoid repeated DB calls
            print("DEBUG: Pre-fetching customer IDs...")
            customer_origins = set()
            for address in all_addresses:
                customer_origin = address.get('id_customer', '')
                if customer_origin:
                    customer_origins.add(str(customer_origin))
            
            # Get all customer IDs in one query
            all_customers = {}
            if customer_origins:
                from src.repository.customer_repository import CustomerRepository
                from src.models.customer import Customer
                customer_repo = CustomerRepository(self.db)
                customers = customer_repo.session.query(Customer).filter(
                    Customer.id_origin.in_(customer_origins)
                ).all()
                all_customers = {str(customer.id_origin): customer.id_customer for customer in customers}
            
            print(f"DEBUG: Pre-fetched {len(all_customers)} customer IDs")
            
            # Optimized prepare address data function
            def prepare_address_data_optimized(address):
                # Get state name from the pre-fetched dictionary
                state_id = int(address.get('id_state', ''))
                state_name = all_states[state_id] if state_id != 0 else 'ND'
                
                # Get country ID from pre-fetched dictionary
                country_origin_id = str(address.get('id_country', ''))
                country_data = all_countries.get(country_origin_id, {})
                country_id = int(country_data.get('id')) if country_data.get('id') else None
                
                # Get customer ID from pre-fetched dictionary
                customer_origin = str(address.get('id_customer', ''))
                customer_id = all_customers.get(customer_origin)
                
                return {
                    'id_origin': address.get('id', 0),
                    'id_country': country_id,
                    'id_customer': customer_id,
                    'company': address.get('company', ''),
                    'firstname': address.get('firstname', ''),
                    'lastname': address.get('lastname', ''),
                    'address1': address.get('address1', ''),
                    'address2': address.get('address2', ''),
                    'state': state_name,
                    'postcode': address.get('postcode', ''),
                    'city': address.get('city', ''),
                    'phone': address.get('phone_mobile', None),
                    'vat': address.get('vat', ''),
                    'dni': address.get('dni', ''),
                    'pec': address.get('pec', ''),
                    'sdi': address.get('sdi', ''),
                    'date_add': date.today()
                }
            
            # Prepare all address data in batches for better performance
            print("DEBUG: Preparing address data in batches...")
            valid_address_data = []
            errors = []
            
            # Process in batches of 5000 for better memory management and performance
            batch_size = 5000
            total_batches = (len(all_addresses) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(all_addresses))
                batch_addresses = all_addresses[start_idx:end_idx]
                
                print(f"DEBUG: Processing batch {batch_num + 1}/{total_batches} ({len(batch_addresses)} addresses)")
                
                # Process batch
                for address in batch_addresses:
                    try:
                        result = prepare_address_data_optimized(address)
                        valid_address_data.append(result)
                    except Exception as e:
                        errors.append(f"Address {address.get('id', 'unknown')}: {str(e)}")
                
                print(f"DEBUG: Batch {batch_num + 1} completed. Total processed: {len(valid_address_data)}")
            
            print(f"DEBUG: Prepared {len(valid_address_data)} valid addresses, {len(errors)} errors")
            
            if not valid_address_data:
                print("DEBUG: No valid addresses to insert")
                return 0
            
            # Use executemany for bulk insert (more reliable than SQL file)
            print("DEBUG: Starting bulk insert with executemany...")
            
            # Get existing address origin IDs to avoid duplicates
            print("DEBUG: Checking existing addresses...")
            existing_origins = set()
            existing_addresses = self.db.execute(text("SELECT id_origin FROM addresses WHERE id_origin IS NOT NULL")).fetchall()
            existing_origins = {str(row[0]) for row in existing_addresses}
            print(f"DEBUG: Found {len(existing_origins)} existing addresses")
            
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
            
            print(f"DEBUG: Skipped {skipped_count} existing addresses, {len(insert_data)} new addresses to insert")
            
            if not insert_data:
                print("DEBUG: No new addresses to insert")
                return 0
            
            # Execute bulk insert in batches
            insert_sql = text("""
                INSERT INTO addresses (
                    id_origin, id_country, id_customer, company, firstname, lastname,
                    address1, address2, state, postcode, city, phone, vat, dni, pec, sdi, date_add
                ) VALUES (
                    :id_origin, :id_country, :id_customer, :company, :firstname, :lastname,
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
                print(f"DEBUG: Inserted batch {i//batch_size + 1}/{(len(insert_data) + batch_size - 1)//batch_size} ({len(batch)} addresses)")
            
            print(f"DEBUG: Successfully inserted {total_inserted} addresses via executemany")
            
            return len(valid_address_data)
            
        except Exception as e:
            print(f"DEBUG: Error processing addresses: {str(e)}")
            raise
    
    async def sync_addresses(self) -> List[Dict[str, Any]]:
        """Synchronize addresses from ps_address"""
        try:
            limit = 50000  # 50k addresses per API call
            offset = 0
            parallel_batches = 1  # Single call per batch since we're getting 50k at once

            # Fetch all states at once for efficient lookup
            all_states = await self._get_all_states()
            all_countries = self._get_all_countries()
            print(f"DEBUG: Starting address sync with {len(all_states)} states and {len(all_countries)} countries")
            
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
                    tasks.append(self._make_request_with_rate_limit('/api/addresses', params=params))
                
                # Execute parallel requests
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                '''
                #### DEBUG ####
                if offset >= 1:
                    break'''
                
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
                        print(f"DEBUG: Batch {i} fetched {len(addresses)} addresses")
                
                print(f"DEBUG: Total addresses in this batch: {len(batch_addresses)}")
                
                if not batch_addresses:
                    break
                
                # Collect addresses instead of processing immediately
                all_addresses.extend(batch_addresses)
                total_processed += len(batch_addresses)
                
                print(f"DEBUG: Collected {len(batch_addresses)} addresses. Total collected: {len(all_addresses)}")
                
                # If we got less than expected, we've reached the end
                if len(batch_addresses) < limit:
                    break
                    
                offset += limit
                # Small delay between batches
                await asyncio.sleep(0.1)  # Reduced delay for faster processing
            
            # All addresses collected, now process them all at once
            print(f"DEBUG: All addresses collected: {len(all_addresses)}")
            
            if not all_addresses:
                print("DEBUG: No addresses to process")
                self._log_sync_result("Addresses", 0)
                return []
            
            # Process all addresses and create SQL file
            total_successful = await self._process_all_addresses_and_create_sql(
                all_addresses, all_states, all_countries
            )
            
            print(f"DEBUG: Address sync completed - Total processed: {total_processed}, Successful: {total_successful}")
            
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
        try:
            orders = await self._get_orders_data()  # Use cached data with order_rows associations
            
            from sqlalchemy import text
            existing_orders = self.db.execute(text("SELECT id_origin FROM orders WHERE id_origin IS NOT NULL")).fetchall()
            existing_order_origins = {str(row[0]) for row in existing_orders}
            
            results = []
            order_details_results = []
            total_weight = 0
            
            for order in orders:
                order_id = order.get('id', 0)
 
                # Check if order already exists to avoid duplicates
                if str(order_id) in existing_order_origins:
                    print(f"DEBUG: Order {order_id} already exists, skipping...")
                    continue
                # Process order data
                id_address_delivery = self._get_address_id_by_origin(int(order.get('id_address_delivery', 0)))
                id_address_invoice = self._get_address_id_by_origin(int(order.get('id_address_invoice', 0)))
                id_customer = self._get_customer_id_by_origin(int(order.get('id_customer', 0)))
                id_payment = self._get_payment_id_by_name(order.get('payment', 0))
                is_payed = self._get_payment_complete_status(order.get('payment', 0))
                order_data = {
                    'id_origin': order_id,
                    'address_delivery': id_address_delivery,
                    'address_invoice': id_address_invoice,
                    'customer': id_customer,
                    'id_platform': 1,  # PrestaShop default - TODO: Review
                    'id_payment': id_payment,
                    'shipping': 1,  # Default - TODO: Review
                    'sectional': 1,  # Default
                    'id_order_state': 1,  # Default
                    'is_invoice_requested': order.get('fattura', 0),
                    'payed': is_payed,
                    'date_payment': None,  # Default
                    'total_weight': 0,  # Will be calculated from order_details
                    'total_price': order.get('total_paid_tax_excl', 0),
                    'cash_on_delivery': 0,  # Default - TODO: Review
                    'insured_value': 0,  # Default - TODO: Review
                    'privacy_note': None,
                    'note': order.get('order_note', ''),
                    'delivery_date': None,
                    'date_add': order.get('date_add', None)
                }
                
                result = await self._upsert_order(order_data)
                print(result)
                '''results.append(result)
                
                # Process order details from associations
                associations = order.get('associations', {})
                order_rows = associations.get('order_rows', {})
                
                
                # Handle both single order_row and multiple order_rows
                if isinstance(order_rows, dict):
                    if 'order_row' in order_rows:
                        rows = order_rows['order_row']
                        if not isinstance(rows, list):
                            rows = [rows]  # Convert single item to list
                    else:
                        rows = []
                else:
                    rows = []
                
                
                # Process each order row
                for row in rows:
                    if isinstance(row, dict):
                        order_detail_data = {
                            'id_origin': row.get('id', f"{order_id}_{row.get('product_id', 'unknown')}"),
                            'id_order': await self._get_order_id_by_origin(order_id),
                            'id_invoice': 0,  # Default
                            'id_order_document': 0,  # Default
                            'id_product': await self._get_product_id_by_origin(row.get('product_id', '')),
                            'product_name': row.get('product_name', ''),
                            'product_reference': row.get('product_reference', ''),
                            'product_quantity': int(row.get('product_quantity', 1)) if row.get('product_quantity') else 1,
                            'product_weight': 0,  # Not available in order_rows
                            'product_price': float(row.get('product_price', 0)) if row.get('product_price') else 0,
                            'id_tax': await self._get_default_tax_id(),
                            'reduction_percent': 0,  # Default
                            'reduction_amount': 0,  # Default
                            'rda': None  # Default
                        }
                        
                        detail_result = await self._upsert_order_detail(order_detail_data)
                        order_details_results.append(detail_result)
                        
                        # Add weight to total (product_weight * quantity)
                        total_weight += order_detail_data['product_weight'] * order_detail_data['product_quantity']
                
            
            # Update order total weight
            if results and total_weight > 0:
                # Update the first order's total weight (this could be improved to update each order individually)
                await self._update_order_total_weight(results[0].get('id_origin', ''), total_weight)
            
                print(f"DEBUG: Final counts - Orders: {len(results)}, Order Details: {len(order_details_results)}")
                print(f"DEBUG: Orders processed: {len([r for r in results if r.get('status') == 'success'])}")
                print(f"DEBUG: Order Details processed: {len([r for r in order_details_results if r.get('status') == 'success'])}")
            self._log_sync_result("Orders", len(results))
            self._log_sync_result("Order Details", len(order_details_results))'''
            
            # Return both orders and order details results
            return {
                'orders': results,
                'order_details': order_details_results
            }
            
        except Exception as e:
            self._log_sync_result("Orders", 0, [str(e)])
            raise
    
    async def sync_product_tags(self) -> List[Dict[str, Any]]:
        """Synchronize product-tag relationships from products endpoint"""
        try:
            # Get all products to extract tags
            response = await self._make_request_with_rate_limit('/api/products', params={'display': '[id,id_category_default,id_manufacturer,name,reference]'})
            products = self._extract_items_from_response(response, 'products')
            
            results = []
            for product in products:
                if 'tags' in product and product['tags']:
                    # Handle both single language and multi-language tag formats
                    if isinstance(product['tags'], list):
                        # Multi-language format: [{"id": "1", "value": "tag1,tag2"}]
                        for tag_entry in product['tags']:
                            if tag_entry.get('value'):
                                tags = tag_entry['value'].split(',')
                                for tag in tags:
                                    tag = tag.strip()
                                    if tag:
                                        # Get or create tag
                                        tag_id = await self._get_or_create_tag(tag, tag_entry['id'])
                                        product_id = await self._get_product_id_by_origin(product.get('id', ''))
                                        
                                        if tag_id and product_id:
                                            product_tag_data = {
                                                'id_tag': tag_id,
                                                'id_product': product_id
                                            }
                                            
                                            result = await self._upsert_product_tag(product_tag_data)
                                            results.append(result)
                    else:
                        # Single language format: "tag1,tag2"
                        tags = product['tags'].split(',')
                        for tag in tags:
                            tag = tag.strip()
                            if tag:
                                # Get or create tag
                                tag_id = await self._get_or_create_tag(tag, '1')  # Default language
                                product_id = await self._get_product_id_by_origin(product.get('id', ''))
                                
                                if tag_id and product_id:
                                    product_tag_data = {
                                        'id_tag': tag_id,
                                        'id_product': product_id
                                    }
                                    
                                    result = await self._upsert_product_tag(product_tag_data)
                                    results.append(result)
            
            self._log_sync_result("Product Tags", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result("Product Tags", 0, [str(e)])
            raise
    
    async def sync_order_details(self) -> List[Dict[str, Any]]:
        """Order details are now synchronized together with orders to avoid duplicate API calls"""
        try:
            print("DEBUG: Order details are synchronized together with orders in sync_orders method")
            print("DEBUG: This method is kept for compatibility but does not perform separate synchronization")
            
            # Return empty list since order details are handled in sync_orders
            self._log_sync_result("Order Details", 0, ["Synchronized together with orders"])
            return []
            
        except Exception as e:
            self._log_sync_result("Order Details", 0, [str(e)])
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
            print(data)
            
            # Skip if both fields are empty (invalid language data)
            if not lang_name and not iso_code:
                print(f"DEBUG: Skipping language {data.get('id_origin', 'unknown')} - empty name and iso_code")
                return {"status": "skipped", "id_origin": data.get('id_origin', 'unknown')}
            
            # Use defaults if fields are empty
            if not lang_name:
                lang_name = f"Language_{data.get('id_origin', 'unknown')}"
            if not iso_code:
                iso_code = "XX"
            
            # Create LangSchema
            lang_schema = LangSchema(
                name=lang_name,
                iso_code=iso_code
            )
            
            # Create language in database
            lang_repo.create(lang_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting language {data.get('id_origin', 'unknown')}: {str(e)}")
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
            
            # Convert data to BrandSchema
            brand_schema = BrandSchema(**data)
            
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
            
            # Create CategorySchema
            category_schema = CategorySchema(
                id_origin=data.get('id_origin', 0),
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
            
            # Create carrier in database
            carrier_repo.create(carrier_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting carrier {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_tag(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert tag record"""
        try:
            from src.repository.tag_repository import TagRepository
            
            tag_repo = TagRepository(self.db)
            
            # Extract data from PrestaShop format
            tag_name = data.get('name', '')
            
            if isinstance(tag_name, dict):
                if 'value' in tag_name:
                    tag_name = tag_name['value']
                else:
                    # If it's a dict but no 'value' key, try to get the first string value
                    tag_name = str(list(tag_name.values())[0]) if tag_name else ''
            elif isinstance(tag_name, list) and tag_name:
                if isinstance(tag_name[0], dict):
                    if 'value' in tag_name[0]:
                        tag_name = tag_name[0]['value']
                    else:
                        # If it's a list of dicts but no 'value' key, try to get the first string value
                        tag_name = str(list(tag_name[0].values())[0]) if tag_name[0] else ''
                else:
                    tag_name = str(tag_name[0])
            
            
            # Create tag using repository
            tag_repo.create(tag_name, data.get('id_origin', 0))
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting tag {data.get('id_origin', 'unknown')}: {str(e)}")
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
            from src.repository.customer_repository import CustomerRepository
            from src.schemas.customer_schema import CustomerSchema
            
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
            print(f"DEBUG: Error upserting address {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert order record"""
        try:
            from src.repository.order_repository import OrderRepository
            from src.schemas.order_schema import OrderSchema
            
            order_repo = OrderRepository(self.db)
            
            # Convert data to OrderSchema
            print(f"DEBUG: Creating OrderSchema with data: {data}")
            order_schema = OrderSchema(**data)
            # Create order in database
            order_repo.create(order_schema)
            
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting order {data.get('id_origin', 'unknown')}: {str(e)}")
            return {"status": "error", "error": str(e), "id_origin": data.get('id_origin', 'unknown')}
    
    async def _upsert_product_tag(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert product-tag relationship"""
        try:
            # Per ora implementiamo una versione semplificata
            # In futuro si può creare una tabella di relazione dedicata
            return {"status": "success", "id_origin": data.get('id_origin', 'unknown')}
        except Exception as e:
            print(f"DEBUG: Error upserting product-tag {data.get('id_origin', 'unknown')}: {str(e)}")
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
    
    def _get_address_id_by_origin(self, origin_id) -> Optional[int]:
        """Get address ID by origin ID"""
        try:
            # Convert to string and check for empty/zero values               
            from src.repository.address_repository import AddressRepository
            address_repo = AddressRepository(self.db)
            address_id = address_repo.get_id_by_id_origin(origin_id)
            
            if address_id:
                return address_id
            else:
                print(f"DEBUG: No address found for origin {origin_id}")
                return 0
        except Exception as e:
            print(f"DEBUG: Error getting address ID by origin {origin_id}: {str(e)}")
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
    
    async def _get_tag_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get tag ID by origin ID"""
        try:
            from src.repository.tag_repository import TagRepository
            tag_repo = TagRepository(self.db)
            tag = tag_repo.get_by_origin_id(origin_id)
            return tag.id_tag if tag else None
        except Exception as e:
            print(f"DEBUG: Error getting tag ID by origin {origin_id}: {str(e)}")
            return None
    
    async def _get_product_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get product ID by origin ID"""
        try:
            from src.repository.product_repository import ProductRepository
            product_repo = ProductRepository(self.db)
            product = product_repo.get_by_origin_id(origin_id)
            return product.id_product if product else None
        except Exception as e:
            print(f"DEBUG: Error getting product ID by origin {origin_id}: {str(e)}")
            return None
    
    async def _get_order_id_by_origin(self, origin_id: str) -> Optional[int]:
        """Get order ID by origin ID"""
        try:
            from src.repository.order_repository import OrderRepository
            order_repo = OrderRepository(self.db)
            order = order_repo.get_by_origin_id(origin_id)
            return order.id_order if order else None
        except Exception as e:
            print(f"DEBUG: Error getting order ID by origin {origin_id}: {str(e)}")
            return None
    
    async def _get_default_tax_id(self) -> int:
        """Get default tax ID"""
        try:
            from src.repository.tax_repository import TaxRepository
            tax_repo = TaxRepository(self.db)
            # Get first available tax or default to 1
            tax = tax_repo.get_all()
            return tax[0].id_tax if tax else 1
        except Exception as e:
            print(f"DEBUG: Error getting default tax ID: {str(e)}")
            return 1  # Default fallback
    
    
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

    def _get_all_countries(self) -> Dict[str, Dict[str, str]]:
        """Get all countries from our database and return as dictionary {id_origin: {id: db_id, name: country_name}}"""
        try:
            from src.repository.country_repository import CountryRepository
            
            all_countries = {}
            country_repo = CountryRepository(self.db)
            
            # Get all countries from our database (limit=0 returns query.all())
            countries = country_repo.get_all()  # This returns a list, not a query
            
            for country in countries:
                country_id_origin = str(country.id_origin) if country.id_origin else None
                if country_id_origin:
                    all_countries[country_id_origin] = {
                        'id': str(country.id_country)
                    }
                
            return all_countries
        except Exception as e:
            print(f"DEBUG: Error fetching all countries from database: {str(e)}")
            return {}

    def _disable_foreign_key_checks(self):
        """Disable foreign key checks temporarily"""
        try:
            # Use raw SQL to disable foreign key checks
            from sqlalchemy import text
            result = self.db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            print(f"Foreign key checks disabled - Result: {result}")
            
            # Verify that FK checks are disabled
            check_result = self.db.execute(text("SELECT @@FOREIGN_KEY_CHECKS")).fetchone()
            print(f"DEBUG: FOREIGN_KEY_CHECKS status: {check_result}")
            
            # Also disable autocommit to ensure the setting persists
            self.db.autocommit = False
            print("DEBUG: Autocommit disabled")
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
    
    async def _update_order_total_weight(self, order_origin_id: str, total_weight: float):
        """Update order total weight"""
        try:
            from src.repository.order_repository import OrderRepository
            order_repo = OrderRepository(self.db)
            order = order_repo.get_by_origin_id(order_origin_id)
            if order:
                order.total_weight = total_weight
                order_repo.update(order)
                print(f"DEBUG: Updated order {order_origin_id} total weight to {total_weight}")
        except Exception as e:
            print(f"DEBUG: Error updating order total weight for {order_origin_id}: {str(e)}")
    
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
            'tag': 'tag',
            'product': 'product',
            'customer': 'customer',
            'address': 'address',
            'order': 'order',
            'product_tag': 'producttag',
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
                print(country_data)
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
    
    async def sync_categories_incremental(self, last_id: int) -> List[Dict[str, Any]]:
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
    
    async def sync_carriers_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new carriers from ps_carrier"""
        try:
            params = {'filter[id]': f'[{last_id + 1},]'}
            response = await self._make_request_with_rate_limit('/api/carriers', params)
            carriers = self._extract_items_from_response(response, 'carriers')
            
            results = []
            for carrier in carriers:
                carrier_data = {
                    'id_origin': carrier.get('id', ''),
                    'name': carrier.get('name', '')
                }
                
                result = await self._upsert_carrier(carrier_data)
                results.append(result)
            
            self._log_sync_result(f"Carriers (Incremental from ID {last_id})", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Carriers (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_tags_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new tags from ps_tag"""
        try:
            params = {'filter[id]': f'[{last_id + 1},]'}
            response = await self._make_request_with_rate_limit('/api/tags', params)
            tags = response.get('tags', {}).get('tag', [])
            
            if not isinstance(tags, list):
                tags = [tags]
            
            results = []
            for tag in tags:
                tag_data = {
                    'id_origin': tag.get('id', ''),
                    'name': tag.get('name', '')
                }
                
                result = await self._upsert_tag(tag_data)
                results.append(result)
            
            self._log_sync_result(f"Tags (Incremental from ID {last_id})", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Tags (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_products_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new products from ps_product (Italian language only)"""
        try:
            # Get Italian language ID
            
            print(f"DEBUG: Using Italian language ID: {self.default_language_id}")
            
            # Get only new products with only necessary fields
            params = {
                'filter[id]': f'[{last_id + 1},]',
                'display': '[id,id_manufacturer,id_category_default,name,reference]'  # Only necessary fields
            }
            response = await self._make_request_with_rate_limit('/api/products', params)
            products = self._extract_items_from_response(response, 'products')
            
            if not isinstance(products, list):
                products = [products] if products else []
            
            # Deduplicate products by ID and filter for Italian language
            unique_products = {}
            for product in products:
                product_id = product.get('id', '')
                if not product_id:
                    continue
                
                # Handle name field - it might be a list or string
                product_name_raw = product.get('name', '')
                product_name = ''
                
                if isinstance(product_name_raw, list):
                    # If it's a list, take the first non-empty value
                    for name_item in product_name_raw:
                        if name_item and str(name_item).strip():
                            product_name = str(name_item).strip()
                            break
                elif isinstance(product_name_raw, str):
                    product_name = product_name_raw.strip()
                
                # Skip products without name or with empty name
                if not product_name:
                    continue
                
                # If we already have this product, prefer the one with better Italian data
                if product_id in unique_products:
                    current_product = unique_products[product_id]
                    current_name_raw = current_product.get('name', '')
                    current_name = ''
                    
                    # Handle current product name the same way
                    if isinstance(current_name_raw, list):
                        for name_item in current_name_raw:
                            if name_item and str(name_item).strip():
                                current_name = str(name_item).strip()
                                break
                    elif isinstance(current_name_raw, str):
                        current_name = current_name_raw.strip()
                    
                    # Prefer the product with Italian name if available
                    if 'italian' in product_name.lower() or (product_name and not current_name):
                        unique_products[product_id] = product
                else:
                    # First time seeing this product, add it
                    unique_products[product_id] = product
            
            products = list(unique_products.values())
            print(f"DEBUG: Deduplicated incremental products: {len(products)} unique products")
            
            results = []
            
            for product in products:
                
                # Extract type from name (dual/trial logic)
                product_type = self._extract_product_type(product_name)
                
                product_data = {
                    'id_origin': product.get('id', ''),
                    'id_platform': 1,
                    'id_category': await self._get_category_id_by_origin(product.get('id_category_default', '')),
                    'id_brand': await self._get_brand_id_by_origin(product.get('id_manufacturer', '')),
                    'name': product_name,
                    'sku': product.get('reference', ''),
                    'type': product_type
                }
                
                
                result = await self._upsert_product(product_data)
                results.append(result)
            
            print(f"DEBUG: Processed {len(results)} Italian products (API filtered incremental)")
            self._log_sync_result(f"Products (Incremental from ID {last_id}) - Italian", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Products (Incremental from ID {last_id}) - Italian", 0, [str(e)])
            raise
    
    async def sync_customers_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new customers from ps_customer"""
        try:
            params = {'filter[id]': f'[{last_id + 1},]'}
            response = await self._make_request_with_rate_limit('/api/customers', params)
            customers = response.get('customers', {}).get('customer', [])
            
            if not isinstance(customers, list):
                customers = [customers]
            
            results = []
            for customer in customers:
                customer_data = {
                    'id_origin': customer.get('id', ''),
                    'firstname': customer.get('firstname', ''),
                    'lastname': customer.get('lastname', ''),
                    'email': customer.get('email', ''),
                    'date_add': datetime.now()
                }
                
                result = await self._upsert_customer(customer_data)
                results.append(result)
            
            self._log_sync_result(f"Customers (Incremental from ID {last_id})", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Customers (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_payments_incremental(self) -> List[Dict[str, Any]]:
        """Synchronize payment methods (no incremental logic needed)"""
        # Payments don't have incremental logic as they're extracted from orders
        return await self.sync_payments()
    
    async def sync_addresses_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new addresses from ps_address"""
        try:
            params = {'filter[id]': f'[{last_id + 1},]'}
            response = await self._make_request_with_rate_limit('/api/addresses', params)
            addresses = response.get('addresses', {}).get('address', [])
            
            if not isinstance(addresses, list):
                addresses = [addresses]
            
            # Fetch all states and countries at once for efficient lookup
            print("DEBUG: Fetching all states and countries for incremental sync...")
            all_states = await self._get_all_states()
            all_countries = self._get_all_countries()
            print(f"DEBUG: Fetched {len(all_states)} states and {len(all_countries)} countries")
            
            results = []
            for address in addresses:
                # Get state name from the pre-fetched dictionary
                state_id = address.get('id_state', '')
                state_name = all_states.get(state_id, '') if state_id else ''
                
                # Get country ID from pre-fetched dictionary
                country_origin_id = str(address.get('id_country', ''))
                country_data = all_countries.get(country_origin_id, {})
                country_id = int(country_data.get('id')) if country_data.get('id') else None
                
                # Get customer ID (still need to call this as it's not pre-fetched)
                customer_id = self._get_customer_id_by_origin(address.get('id_customer', 0))
                
                address_data = {
                    'id_origin': address.get('id', ''),
                    'id_country': country_id,
                    'id_customer': int(customer_id) if customer_id is not None else None,
                    'company': address.get('company', ''),
                    'firstname': address.get('firstname', ''),
                    'lastname': address.get('lastname', ''),
                    'address1': address.get('address1', ''),
                    'address2': address.get('address2', ''),
                    'state': state_name,
                    'postcode': address.get('postcode', ''),
                    'city': address.get('city', ''),
                    'phone': address.get('phone_mobile', ''),
                    'vat': address.get('vat', ''),
                    'dni': address.get('dni', ''),
                    'pec': address.get('pec', ''),
                    'sdi': address.get('sdi', ''),
                    'date_add': datetime.now()
                }
                
                result = await self._upsert_address(address_data)
                results.append(result)
            
            self._log_sync_result(f"Addresses (Incremental from ID {last_id})", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Addresses (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_orders_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new orders and order details from ps_orders with associations"""
        try:
            # Get only new orders with associations using pagination
            date_range_filter = self._get_date_range_filter()

            all_orders = []
            limit = 1000  # Batch size
            offset = 0
            
            while True:
                try:
                    # Filter orders not older than 2 years
                    # Filter orders for the last 6 months using date range filter
                    params = {
                        'filter[id]': f'[{last_id + 1},]', 
                        'filter[date_add]': date_range_filter,  # Orders from 6 months ago to today
                        'display': 'full',
                        'limit': f'{offset},{limit}'
                    }
                    
                    print(f"DEBUG: Fetching incremental orders batch {offset//limit + 1} (offset: {offset}, limit: {limit})")
                    
                    # Debug: Print the complete URL with parameters
                    import urllib.parse
                    base_url = f"{self.base_url}/api/orders"
                    query_string = urllib.parse.urlencode(params)
                    full_url = f"{base_url}?{query_string}"
                    print(f"DEBUG: Incremental Orders API Request URL: {full_url}")
                    
                    response = await self._make_request_with_rate_limit('/api/orders', params)
                    orders_batch = self._extract_items_from_response(response, 'orders')
                    
                    if not orders_batch:
                        print(f"DEBUG: No more incremental orders found at offset {offset}")
                        break
                    
                    all_orders.extend(orders_batch)
                    offset += limit
                    
                    # Debug: Show last order ID in this batch
                    last_order_id = orders_batch[-1].get('id', 'unknown') if orders_batch else 'none'
                    print(f"DEBUG: Fetched {len(orders_batch)} incremental orders (total: {len(all_orders)}) - Last ID: {last_order_id}")
                    
                    # Small delay between batches
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    # Debug: Print full error details
                    print(f"DEBUG: Full error details for incremental orders at offset {offset}:")
                    print(f"DEBUG: Error type: {type(e).__name__}")
                    print(f"DEBUG: Error message: {str(e)}")
                    print(f"DEBUG: Error args: {e.args if hasattr(e, 'args') else 'No args'}")
                    
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['500', 'server', 'timeout', 'connection reset', 'disconnected']):
                        print(f"DEBUG: Server error at offset {offset}, retrying with smaller batch...")
                        limit = max(100, limit // 2)  # Reduce batch size
                        await asyncio.sleep(3)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Non-server error at offset {offset}, continuing with next batch...")
                        # Don't break, try to continue with next batch
                        offset += limit
                        await asyncio.sleep(1)
                        continue
            
            orders = all_orders
            
            # Pre-fetch all existing order origin IDs to avoid repeated queries
            print("DEBUG: Checking existing orders for incremental sync...")
            from sqlalchemy import text
            existing_orders = self.db.execute(text("SELECT id_origin FROM orders WHERE id_origin IS NOT NULL")).fetchall()
            existing_order_origins = {str(row[0]) for row in existing_orders}
            print(f"DEBUG: Found {len(existing_order_origins)} existing orders")
            
            results = []
            order_details_results = []
            total_weight = 0
            
            for order in orders:
                order_id = order.get('id', '')
                
                # Check if order already exists to avoid duplicates
                if str(order_id) in existing_order_origins:
                    print(f"DEBUG: Order {order_id} already exists, skipping...")
                    continue
                # Process order data
                print(order.get('fattura', 0))
                order_data = {
                    'id_origin': order_id,
                    'id_address_delivery': self._get_address_id_by_origin(order.get('id_address_delivery')),
                    'id_address_invoice': self._get_address_id_by_origin(order.get('id_address_invoice')),
                    'id_customer': self._get_customer_id_by_origin(order.get('id_customer', '')),
                    'id_platform': 1,
                    'id_payment': await self._get_payment_id_by_name(order.get('payment', '')),
                    'id_order_state': 1,
                    'is_invoice_requested': order.get('fattura', 0),
                    'payed': self._get_payment_complete_status(order.get('payment', '')),
                    'date_payment': None,
                    'total_weight': 0,
                    'total_price': order.get('total_paid_tax_excl', 0),
                    'cash_on_delivery': 0,
                    'insured_value': 0,
                    'privacy_note': None,
                    'note': order.get('order_note', ''),
                    'delivery_date': None,
                    'date_add': order.get('date_add', None)
                }
                
                result = await self._upsert_order(order_data)
                results.append(result)
                
                # Process order details from associations
                associations = order.get('associations', {})
                order_rows = associations.get('order_rows', {})
                
                
                # Handle both single order_row and multiple order_rows
                if isinstance(order_rows, dict):
                    if 'order_row' in order_rows:
                        rows = order_rows['order_row']
                        if not isinstance(rows, list):
                            rows = [rows]  # Convert single item to list
                    else:
                        rows = []
                else:
                    rows = []
                
                print(f"DEBUG: Order {order.get('id', 'unknown')} processed rows: {len(rows)}")
                
                # Process each order row
                for row in rows:
                    if isinstance(row, dict):
                        order_detail_data = {
                            'id_origin': row.get('id', f"{order_id}_{row.get('product_id', 'unknown')}"),
                            'id_order': await self._get_order_id_by_origin(order_id),
                            'id_invoice': 0,  # Default
                            'id_order_document': 0,  # Default
                            'id_product': await self._get_product_id_by_origin(row.get('product_id', '')),
                            'product_name': row.get('product_name', ''),
                            'product_reference': row.get('product_reference', ''),
                            'product_quantity': int(row.get('product_quantity', 1)) if row.get('product_quantity') else 1,
                            'product_weight': 0,  # Not available in order_rows
                            'product_price': float(row.get('product_price', 0)) if row.get('product_price') else 0,
                            'id_tax': await self._get_default_tax_id(),
                            'reduction_percent': 0,  # Default
                            'reduction_amount': 0,  # Default
                            'rda': None  # Default
                        }
                        
                        detail_result = await self._upsert_order_detail(order_detail_data)
                        order_details_results.append(detail_result)
                        
                        # Add weight to total (product_weight * quantity)
                        total_weight += order_detail_data['product_weight'] * order_detail_data['product_quantity']
                
                # If no order_rows found, create a basic entry
                if not rows:
                    order_detail_data = {
                        'id_origin': f"{order_id}_basic",
                        'id_order': await self._get_order_id_by_origin(order_id),
                        'id_invoice': 0,  # Default
                        'id_order_document': 0,  # Default
                        'id_product': 0,  # Default
                        'product_name': 'Order Products',
                        'product_reference': '',
                        'product_quantity': 1,
                        'product_weight': 0,
                        'product_price': float(order.get('total_products', 0)),
                        'id_tax': await self._get_default_tax_id(),
                        'reduction_percent': 0,  # Default
                        'reduction_amount': 0,  # Default
                        'rda': None  # Default
                    }
                    
                    detail_result = await self._upsert_order_detail(order_detail_data)
                    order_details_results.append(detail_result)
            
            # Update order total weight
            if results and total_weight > 0:
                # Update the first order's total weight (this could be improved to update each order individually)
                await self._update_order_total_weight(results[0].get('id_origin', ''), total_weight)
            
            self._log_sync_result(f"Orders (Incremental from ID {last_id})", len(results))
            self._log_sync_result(f"Order Details (Incremental from ID {last_id})", len(order_details_results))
            
            # Return both orders and order details results
            return {
                'orders': results,
                'order_details': order_details_results
            }
            
        except Exception as e:
            self._log_sync_result(f"Orders (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_product_tags_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Synchronize only new product-tag relationships from products endpoint"""
        try:
            # Get only new products (incremental)
            params = {'filter[id]': f'[{last_id + 1},]'}
            response = await self._make_request_with_rate_limit('/api/products', params)
            products = self._extract_items_from_response(response, 'products')
            
            results = []
            for product in products:
                if 'tags' in product and product['tags']:
                    # Handle both single language and multi-language tag formats
                    if isinstance(product['tags'], list):
                        # Multi-language format: [{"id": "1", "value": "tag1,tag2"}]
                        for tag_entry in product['tags']:
                            if tag_entry.get('value'):
                                tags = tag_entry['value'].split(',')
                                for tag in tags:
                                    tag = tag.strip()
                                    if tag:
                                        # Get or create tag
                                        tag_id = await self._get_or_create_tag(tag, tag_entry['id'])
                                        product_id = await self._get_product_id_by_origin(product.get('id', ''))
                                        
                                        if tag_id and product_id:
                                            product_tag_data = {
                                                'id_tag': tag_id,
                                                'id_product': product_id
                                            }
                                            
                                            result = await self._upsert_product_tag(product_tag_data)
                                            results.append(result)
                    else:
                        # Single language format: "tag1,tag2"
                        tags = product['tags'].split(',')
                        for tag in tags:
                            tag = tag.strip()
                            if tag:
                                # Get or create tag
                                tag_id = await self._get_or_create_tag(tag, '1')  # Default language
                                product_id = await self._get_product_id_by_origin(product.get('id', ''))
                                
                                if tag_id and product_id:
                                    product_tag_data = {
                                        'id_tag': tag_id,
                                        'id_product': product_id
                                    }
                                    
                                    result = await self._upsert_product_tag(product_tag_data)
                                    results.append(result)
            
            self._log_sync_result(f"Product Tags (Incremental from ID {last_id})", len(results))
            return results
            
        except Exception as e:
            self._log_sync_result(f"Product Tags (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    async def sync_order_details_incremental(self, last_id: int) -> List[Dict[str, Any]]:
        """Order details are now synchronized together with orders to avoid duplicate API calls"""
        try:
            print(f"DEBUG: Order details incremental sync is handled together with orders in sync_orders_incremental method")
            print(f"DEBUG: This method is kept for compatibility but does not perform separate synchronization (from ID {last_id})")
            
            # Return empty list since order details are handled in sync_orders_incremental
            self._log_sync_result("Order Details Incremental", 0, ["Synchronized together with orders"])
            return []
            
        except Exception as e:
            self._log_sync_result(f"Order Details (Incremental from ID {last_id})", 0, [str(e)])
            raise
    
    def _extract_items_from_response(self, response: Any, key: str) -> List[Dict[str, Any]]:
        """Extract items from API response, handling both list and dict formats"""
        print(f"DEBUG: Extracting {key} from response type: {type(response)}")
        
        if isinstance(response, list):
            print(f"DEBUG: Response is a list with {len(response)} items")
            return response
        elif isinstance(response, dict):
            print(f"DEBUG: Response keys: {list(response.keys())}")
            
            # Try different possible structures
            if key in response:
                items = response[key]
                print(f"DEBUG: Found {key} in response, type: {type(items)}")
                
                if isinstance(items, dict):
                    print(f"DEBUG: {key} is a dict with keys: {list(items.keys())}")
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
                                print(f"DEBUG: Found list in key: {possible_key}")
                                break
                
                if not isinstance(items, list):
                    items = [items] if items else []
                    print(f"DEBUG: Converted to list with {len(items)} items")
                else:
                    print(f"DEBUG: Items is already a list with {len(items)} items")
                    
                return items
            else:
                # Try to find the key in a different case or similar
                print(f"DEBUG: Key {key} not found in response, trying alternatives...")
                for response_key in response.keys():
                    if response_key.lower() == key.lower():
                        print(f"DEBUG: Found case-insensitive match: {response_key}")
                        return self._extract_items_from_response(response, response_key)
                    elif key.rstrip('s') in response_key.lower():
                        print(f"DEBUG: Found partial match: {response_key}")
                        return self._extract_items_from_response(response, response_key)
                
                print(f"DEBUG: No alternative keys found for {key}")
                return []
        else:
            print(f"DEBUG: Unexpected response type: {type(response)}")
            return []
    
    async def _get_orders_data(self) -> List[Dict[str, Any]]:
        """Get orders data with caching and pagination to avoid server overload"""
        if self._orders_cache is None:
            date_range_filter = self._get_date_range_filter()
            six_months_ago = self._get_six_months_ago_date()
            

            all_orders = []
            limit = 5000  # Batch size
            offset = 0
            
            while True:
                try:
            # Include order_rows associations to get order details
                    # Use PrestaShop format: limit=[offset,]limit
                    # Filter orders for the last 6 months using date range filter
                    params = {
                        'display': 'full',
                        'filter[date_add]': date_range_filter,  # Orders from 6 months ago to today
                        'date': 1,
                        'limit': f'{offset},{limit}'
                    }
                    
                    print(f"DEBUG: Fetching orders batch {offset//limit + 1} (offset: {offset}, limit: {limit})")
                    
                    # Debug: Print the complete URL with parameters
                    import urllib.parse
                    base_url = f"{self.base_url}/api/orders"
                    query_string = urllib.parse.urlencode(params)
                    full_url = f"{base_url}?{query_string}"
                    print(f"DEBUG: Orders API Request URL: {full_url}")
                    
                    response = await self._make_request_with_rate_limit('/api/orders', params)
                    orders_batch = self._extract_items_from_response(response, 'orders')
                    
                    if not orders_batch:
                        print(f"DEBUG: No more orders found at offset {offset}")
                        break
                    
                    all_orders.extend(orders_batch)
                    offset += limit
                    
                    # Debug: Show last order ID and date in this batch
                    last_order_id = orders_batch[-1].get('id', 'unknown') if orders_batch else 'none'
                    last_order_date = orders_batch[-1].get('date_add', 'unknown') if orders_batch else 'none'
                    print(f"DEBUG: Fetched {len(orders_batch)} orders (total: {len(all_orders)}) - Last ID: {last_order_id}, Date: {last_order_date}")
                    
                    # Small delay between batches to be gentle with the server
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    # Debug: Print full error details
                    print(f"DEBUG: Full error details for orders at offset {offset}:")
                    print(f"DEBUG: Error type: {type(e).__name__}")
                    print(f"DEBUG: Error message: {str(e)}")
                    print(f"DEBUG: Error args: {e.args if hasattr(e, 'args') else 'No args'}")
                    
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['500', 'server', 'timeout', 'connection reset', 'disconnected']):
                        print(f"DEBUG: Server error at offset {offset}, retrying with smaller batch...")
                        limit = max(100, limit // 2)  # Reduce batch size
                        await asyncio.sleep(3)  # Wait before retry
                        continue
                    else:
                        print(f"DEBUG: Non-server error at offset {offset}, continuing with next batch...")
                        # Don't break, try to continue with next batch
                        offset += limit
                        await asyncio.sleep(1)
                        continue
            
                self._orders_cache = all_orders
                
                # Debug: Check if orders respect the date filter
                if all_orders:
                    first_order_date = all_orders[0].get('date_add', 'unknown')
                    last_order_date = all_orders[-1].get('date_add', 'unknown')
                    print(f"DEBUG: Date range of cached orders: {first_order_date} to {last_order_date}")
                    print(f"DEBUG: Filter was: filter[date_add]={date_range_filter}")
                    
                    # Check if filter is working - if we get old dates, the filter is not working
                    if '2017' in str(first_order_date) or '2018' in str(first_order_date) or '2019' in str(first_order_date):
                        print(f"WARNING: Date filter is NOT working! Getting orders from {first_order_date}")
                        print(f"WARNING: Expected orders from {six_months_ago} onwards")
                        print(f"WARNING: Applying client-side date filtering...")
                        
                        # Apply client-side filtering
                        all_orders = self._filter_orders_by_date(all_orders, six_months_ago)
                        self._orders_cache = all_orders
        else:
            print("DEBUG: Using cached orders data")
        
        return self._orders_cache
    
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
    
    async def _get_or_create_tag(self, tag_name: str, lang_id: str) -> int:
        """Get or create a tag by name and language"""
        try:
            from ...repository.tag_repository import TagRepository
            tag_repo = TagRepository(self.db)
            
            # Try to find existing tag
            existing_tag = tag_repo.get_by_name_and_lang(tag_name, int(lang_id))
            if existing_tag:
                return existing_tag.id_tag
            
            # Create new tag if not found
            new_tag = tag_repo.create(
                name=tag_name,
                id_lang=int(lang_id)
            )
            return new_tag.id_tag
            
        except Exception as e:
            print(f"Error getting/creating tag '{tag_name}': {str(e)}")
            return None
    
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
