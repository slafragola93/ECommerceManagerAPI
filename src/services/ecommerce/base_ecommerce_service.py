"""
Base class for e-commerce synchronization services
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
import asyncio
import aiohttp
from datetime import datetime


class BaseEcommerceService(ABC):
    """
    Base class for e-commerce synchronization services.
    Provides common functionality and defines the interface for all e-commerce integrations.
    """
    
    def __init__(self, db: Session, store_id: int, batch_size: int = 5000):
        """
        Initialize the e-commerce service
        
        Args:
            db: Database session
            store_id: ID of the store in the stores table
            batch_size: Number of records to process in each batch
        """
        self.db = db
        self.store_id = store_id
        self.batch_size = batch_size
        self.session = None
        self._store_config = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        await self._load_store_data()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _load_store_data(self):
        """Load store configuration (URL, API key, P.IVA)"""
        from ...repository.store_repository import StoreRepository
        store_repo = StoreRepository(self.db)
        store = store_repo.get_by_id(self.store_id)
        
        if not store:
            raise ValueError(f"Store with ID {self.store_id} not found")
        
        if not store.is_active:
            raise ValueError(f"Store {store.name} is not active")
        
        self._store_config = {
            'base_url': store.base_url,
            'api_key': store.api_key,
            'vat_number': store.vat_number,
            'country_code': store.country_code,
            'name': store.name
        }
    
    @property
    def api_key(self) -> str:
        """Get API key from store configuration"""
        if not self._store_config:
            raise RuntimeError("Store configuration not loaded. Use async context manager.")
        return self._store_config.get('api_key')
    
    @property
    def base_url(self) -> str:
        """Get base URL from store configuration"""
        if not self._store_config:
            raise RuntimeError("Store configuration not loaded. Use async context manager.")
        return self._store_config.get('base_url').rstrip('/')
    
    @property
    def vat_number(self) -> Optional[str]:
        """Get VAT number from store configuration"""
        if not self._store_config:
            raise RuntimeError("Store configuration not loaded. Use async context manager.")
        return self._store_config.get('vat_number')
    
    @property
    def country_code(self) -> Optional[str]:
        """Get country code from store configuration"""
        if not self._store_config:
            raise RuntimeError("Store configuration not loaded. Use async context manager.")
        return self._store_config.get('country_code')
    
    @abstractmethod
    async def sync_all_data(self) -> Dict[str, Any]:
        """
        Synchronize all data from the e-commerce platform
        
        Returns:
            Dict containing sync results and statistics
        """
        pass
    
    @abstractmethod
    async def sync_languages(self) -> List[Dict[str, Any]]:
        """Synchronize languages"""
        pass
    
    @abstractmethod
    async def sync_countries(self) -> List[Dict[str, Any]]:
        """Synchronize countries"""
        pass
    
    @abstractmethod
    async def sync_brands(self) -> List[Dict[str, Any]]:
        """Synchronize brands/manufacturers"""
        pass
    
    @abstractmethod
    async def sync_categories(self) -> List[Dict[str, Any]]:
        """Synchronize categories"""
        pass
    
    @abstractmethod
    async def sync_carriers(self) -> List[Dict[str, Any]]:
        """Synchronize carriers"""
        pass
    
    
    @abstractmethod
    async def sync_products(self) -> List[Dict[str, Any]]:
        """Synchronize products"""
        pass
    
    @abstractmethod
    async def sync_customers(self) -> List[Dict[str, Any]]:
        """Synchronize customers"""
        pass
    
    @abstractmethod
    async def sync_payments(self) -> List[Dict[str, Any]]:
        """Synchronize payment methods"""
        pass
    
    @abstractmethod
    async def sync_addresses(self) -> List[Dict[str, Any]]:
        """Synchronize addresses"""
        pass
    
    @abstractmethod
    async def sync_orders(self) -> List[Dict[str, Any]]:
        """Synchronize orders"""
        pass

    
    @abstractmethod
    async def sync_order_details(self) -> List[Dict[str, Any]]:
        """Synchronize order details"""
        pass
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None, max_retries: int = 3) -> Dict[str, Any]:
        """
        Make HTTP request to the e-commerce API with retry mechanism
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            API response data
        """
        if not self.session:
            raise RuntimeError("Service not initialized. Use async context manager.")
            
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_auth_headers()
        
        # Ensure JSON output format for PrestaShop
        if params is None:
            params = {}
        params['output_format'] = 'JSON'
        
        
        # Retry mechanism with exponential backoff
        for attempt in range(max_retries + 1):
            try:
                # Add timeout to prevent hanging requests
                timeout = aiohttp.ClientTimeout(total=30, connect=10)
                
                # Use a more conservative approach to prevent file descriptor issues
                async with self.session.get(url, headers=headers, params=params, timeout=timeout) as response:
                    # Check if response is successful
                    if response.status >= 400:
                        error_text = await response.text()
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}: {error_text}"
                        )
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/json' in content_type:
                        return await response.json()
                    elif 'text/xml' in content_type or 'application/xml' in content_type:
                        # Handle XML response (fallback if output_format=JSON doesn't work)
                        xml_text = await response.text()
                        print(f"Warning: Received XML response for {endpoint} despite output_format=JSON. Content: {xml_text[:200]}...")
                        # Try to parse as JSON anyway (sometimes XML contains JSON)
                        try:
                            import json
                            # Look for JSON-like content in XML
                            if '{' in xml_text and '}' in xml_text:
                                # Extract JSON from XML
                                start = xml_text.find('{')
                                end = xml_text.rfind('}') + 1
                                json_text = xml_text[start:end]
                                return json.loads(json_text)
                            else:
                                raise ValueError("No JSON content found in XML response")
                        except (json.JSONDecodeError, ValueError):
                            raise ValueError(f"Expected JSON but received XML: {xml_text[:200]}...")
                    else:
                        # Try to parse as JSON anyway
                        try:
                            return await response.json()
                        except:
                            text_content = await response.text()
                            raise ValueError(f"Unexpected content type '{content_type}': {text_content[:200]}...")
                            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error_msg = str(e).lower()
                
                # Check if it's a file descriptor error
                if "too many file descriptors" in error_msg:
                    if attempt < max_retries:
                        # Wait longer for file descriptor issues
                        wait_time = 5 + (2 ** attempt)  # 6s, 7s, 9s, etc.
                        print(f"File descriptor limit reached for {url}, waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"Max retries exceeded for file descriptor error on {url}: {str(e)}")
                        raise
                # Check if it's a server disconnection or timeout
                elif any(keyword in error_msg for keyword in ['server disconnected', 'timeout', 'connection reset', 'connection aborted']):
                    if attempt < max_retries:
                        # Exponential backoff: wait 1s, 2s, 4s, etc.
                        wait_time = 2 ** attempt
                        print(f"Server disconnected for {url}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"Max retries exceeded for {url}: {str(e)}")
                        raise
                else:
                    # For other errors, don't retry
                    print(f"Request error for {url}: {str(e)}")
                    raise
                    
            except aiohttp.ClientResponseError as e:
                # Don't retry for HTTP errors (4xx, 5xx)
                print(f"HTTP Error {e.status} for {url}: {e.message}")
                raise
            except Exception as e:
                # Don't retry for other exceptions
                print(f"Request error for {url}: {str(e)}")
                raise
        
        # This should never be reached, but just in case
        raise Exception(f"Unexpected error: max retries exceeded for {url}")
    
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        pass
    
    async def _process_batch(self, items: List[Any], process_func) -> List[Dict[str, Any]]:
        """
        Process items in batches
        
        Args:
            items: List of items to process
            process_func: Function to process each batch
            
        Returns:
            List of results
        """
        results = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_results = await process_func(batch)
            results.extend(batch_results)
        return results
    
    def _log_sync_result(self, operation: str, count: int, errors: List[str] = None):
        """
        Log synchronization result
        
        Args:
            operation: Operation name
            count: Number of records processed
            errors: List of errors (if any)
        """
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if not errors else "ERROR"
        
        # Log removed - use logging framework if needed
        '''if errors:
            for error in errors:
                print(f"  ERROR: {error}")'''
    
    async def _sync_phase(self, phase_name: str, sync_functions: List[callable]) -> Dict[str, Any]:
        """
        Execute a synchronization phase with multiple functions
        
        Args:
            phase_name: Name of the synchronization phase
            sync_functions: List of sync functions to execute
            
        Returns:
            Phase results
        """
        print(f"Starting {phase_name}...")
        start_time = datetime.now()
        
        # Execute all sync functions concurrently
        results = await asyncio.gather(*[func() for func in sync_functions], return_exceptions=True)
        
        # Process results
        phase_results = {
            'phase': phase_name,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'functions': []
        }
        
        total_processed = 0
        total_errors = 0
        
        for i, result in enumerate(results):
            function_name = sync_functions[i].__name__
            if isinstance(result, Exception):
                phase_results['functions'].append({
                    'function': function_name,
                    'table_name': function_name.replace('sync_', '').replace('_', ' ').title(),
                    'status': 'ERROR',
                    'error': str(result),
                    'processed': 0,
                    'errors': 1,
                    'error_details': [str(result)]
                })
                total_errors += 1
            else:
                processed = len(result) if isinstance(result, list) else 1
                phase_results['functions'].append({
                    'function': function_name,
                    'table_name': function_name.replace('sync_', '').replace('_', ' ').title(),
                    'status': 'SUCCESS',
                    'processed': processed,
                    'errors': 0,
                    'error_details': []
                })
                total_processed += processed
        
        phase_results['total_processed'] = total_processed
        phase_results['total_errors'] = total_errors
        phase_results['phase_name'] = phase_name
        phase_results['results'] = phase_results['functions']  # Alias for compatibility
        
        print(f"Completed {phase_name}: {total_processed} records processed, {total_errors} errors")
        return phase_results
