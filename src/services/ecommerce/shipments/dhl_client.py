import httpx
import base64
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.engine import Row
import logging

from src.core.settings import get_cache_settings

logger = logging.getLogger(__name__)


class DhlClient:
    """DHL MyDHL API HTTP client with Basic Auth and idempotency support"""
    
    def __init__(self):
        self.settings = get_cache_settings()
        self.base_url_prod = self.settings.dhl_base_url_prod
        self.base_url_sandbox = self.settings.dhl_base_url_sandbox
    
    async def create_shipment(
        self, 
        payload: Dict[str, Any], 
        credentials: Row, 
        message_ref: str
    ) -> Dict[str, Any]:
        """
        Create DHL shipment via MyDHL API
        
        Args:
            payload: DHL shipment request payload
            credentials: CarrierApi row with auth details
            message_ref: Message reference for idempotency
            
        Returns:
            DHL API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/shipments"
        headers = self._get_headers(credentials, message_ref)
        
        logger.info(f"Creating DHL shipment for AWB: {payload.get('customerReferences', [{}])[0].get('value', 'N/A')}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "POST", url, headers=headers, json=payload
            )
            
        return response.json()
    
    async def get_tracking_multi(
        self, 
        tracking_numbers: list[str], 
        credentials: Row
    ) -> Dict[str, Any]:
        """
        Get tracking information for multiple shipments
        
        Args:
            tracking_numbers: List of tracking numbers to track
            credentials: CarrierApi row with auth details
            
        Returns:
            DHL API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/tracking"
        headers = self._get_headers(credentials)
        
        # Build query parameters
        params = {
            "trackingNumber": ",".join(tracking_numbers),
            "trackingView": "shipment-details",
            "levelOfDetail": "shipment"
        }
        
        logger.info(f"Getting DHL tracking for {len(tracking_numbers)} shipments")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "GET", url, headers=headers, params=params
            )
            
        return response.json()
    
    def _get_headers(self, credentials: Row, message_ref: Optional[str] = None) -> Dict[str, str]:
        """
        Generate HTTP headers for DHL API requests
        
        Args:
            credentials: CarrierApi row with auth details
            message_ref: Message reference for idempotency (optional)
            
        Returns:
            Headers dict
        """
        # Select credentials based on sandbox flag
        username = credentials.sandbox_api_username if credentials.use_sandbox else credentials.api_username
        password = credentials.sandbox_api_password if credentials.use_sandbox else credentials.api_password
        
        if not username or not password:
            raise ValueError(f"Missing credentials for {'sandbox' if credentials.use_sandbox else 'production'} environment")
        
        # Generate Basic Auth header
        auth_string = f"{username}:{password}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Add idempotency headers if message_ref provided
        if message_ref:
            headers["Message-Reference"] = message_ref
            headers["Message-Reference-Date"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        return headers
    
    def _get_base_url(self, use_sandbox: bool) -> str:
        """
        Get base URL based on environment
        
        Args:
            use_sandbox: Whether to use sandbox environment
            
        Returns:
            Base URL string
        """
        return self.base_url_sandbox if use_sandbox else self.base_url_prod
    
    async def _make_request_with_retry(
        self, 
        client: httpx.AsyncClient, 
        method: str, 
        url: str, 
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic for 429 and 5xx errors
        
        Args:
            client: httpx client instance
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            httpx Response object
        """
        max_retries = 3
        base_delay = 1.0  # seconds
        
        for attempt in range(max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                
                # Success or client error (4xx except 429)
                if response.status_code < 500 and response.status_code != 429:
                    return response
                
                # Rate limit (429) or server error (5xx) - retry
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"DHL API request failed with status {response.status_code}, "
                            f"retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"DHL API request failed after {max_retries} retries")
                        response.raise_for_status()
                
                # Other 4xx errors - don't retry
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"DHL API request timeout, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error("DHL API request timeout after all retries")
                    raise
            except httpx.RequestError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"DHL API request error: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"DHL API request error after all retries: {e}")
                    raise
        
        # This should never be reached
        raise RuntimeError("Unexpected retry loop exit")


# Utility functions for external use
def generate_message_reference() -> str:
    """Generate unique message reference for idempotency"""
    return str(uuid.uuid4())


def format_planned_shipping_date(delta_hours: int = 1) -> str:
    """
    Format planned shipping date for DHL API
    
    Args:
        delta_hours: Hours to add to current time (default 1)
        
    Returns:
        Formatted date string for DHL API
    """
    now = datetime.now(timezone.utc)
    shipping_time = now.replace(hour=now.hour + delta_hours, minute=0, second=0, microsecond=0)
    return shipping_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
