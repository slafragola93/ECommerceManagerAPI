import httpx
import base64
import uuid
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.engine import Row
import logging

from src.core.settings import get_cache_settings
from src.services.core.tool import convert_decimals_to_float

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
        dhl_config: Row,
        message_ref: str
    ) -> Dict[str, Any]:
        """
        Create DHL shipment via MyDHL API
        
        Args:
            payload: DHL shipment request payload
            credentials: CarrierApi row with auth details
            dhl_config: DhlConfiguration row with client_id and client_secret
            message_ref: Message reference for idempotency
            
        Returns:
            DHL API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/shipments"
        headers = self._get_headers(credentials, dhl_config, message_ref)
        
        # Convert Decimal objects to float for JSON serialization
        payload_serializable = convert_decimals_to_float(payload)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "POST", url, headers=headers, json=payload_serializable
            )
            
        # Debug: Log response
        response_data = response.json()
        logger.info(f"📥 DHL Response Status: {response.status_code}")
        logger.info(f"📥 DHL Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        # Check for HTTP errors and handle them appropriately
        error_message = response_data.get('detail', response_data.get('message', 'Unknown error'))
        title = response_data.get('title', 'DHL API Error')
            # Handle specific error codes
        if response.status_code == 400:
            raise ValueError(f"DHL Bad Request (400): {title} - {error_message}")
        if response.status_code == 422:
            raise ValueError(f"DHL Validation Error (422): {title} - {error_message}")
        if response.status_code == 500:
            raise RuntimeError(f"DHL Server Error (500): {title} - {error_message}")

        
        return response_data
    
    async def get_tracking_multi(
        self, 
        tracking: list[str], 
        credentials: Row,
        dhl_config: Row
    ) -> Dict[str, Any]:
        """
        Get tracking information for multiple shipments
        
        Args:
            tracking: List of tracking numbers to track
            credentials: CarrierApi row with auth details
            dhl_config: DhlConfiguration row with client_id and client_secret
            
        Returns:
            DHL API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/tracking"
        headers = self._get_headers(credentials, dhl_config)
        
        # Build query parameters
        params = {
            "shipmentTrackingNumber": ",".join(tracking),
            "trackingView": "last-checkpoint",
            "levelOfDetail": "shipment"
        }
        
        # Debug: Log URL and parameters
        logger.info(f"🔍 DHL Tracking URL: {url}")
        logger.info(f"📋 DHL Tracking Params: {json.dumps(params, indent=2)}")
        logger.info(f"🔑 DHL Tracking Headers: {json.dumps({k: v for k, v in headers.items() if k != 'Authorization'}, indent=2)}")
        logger.info(f"🔐 DHL Tracking Auth: Basic {headers.get('Authorization', '').split(' ')[1] if 'Authorization' in headers else 'N/A'}")
        logger.info(f"Getting DHL tracking for {len(tracking)} shipments")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "GET", url, headers=headers, params=params
            )
            
        # Debug: Log response
        response_data = response.json()
        logger.info(f"📥 DHL Tracking Response Status: {response.status_code}")
        logger.info(f"📥 DHL Tracking Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        return response_data
    
    def _get_headers(self, credentials: Row, dhl_config: Row, message_ref: Optional[str] = None) -> Dict[str, str]:
        """
        Generate HTTP headers for DHL API requests
        
        Args:
            credentials: CarrierApi row with auth details
            dhl_config: DhlConfiguration row with client_id and client_secret
            message_ref: Message reference for idempotency (optional)
            
        Returns:
            Headers dict
        """
        # Get DHL credentials from DhlConfiguration
        client_id = dhl_config.client_id
        client_secret = dhl_config.client_secret
        
        if not client_id or not client_secret:
            raise ValueError(f"Missing DHL credentials in DhlConfiguration")
        
        # Generate Basic Auth header with client_id:client_secret (DHL MyDHL API format)
        auth_string = f"{client_id}:{client_secret}"
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
        Formatted date string for DHL API in format: '2010-02-11T17:10:09 GMT+01:00'
    """
    from datetime import timedelta
    
    # Get current time in UTC
    now = datetime.now(timezone.utc)
    
    # Add delta hours
    shipping_time = now + timedelta(hours=delta_hours)
    
    # Round to next hour and set minutes/seconds to 0
    shipping_time = shipping_time.replace(minute=0, second=0, microsecond=0)
    
    # Format as required by DHL: '2010-02-11T17:10:09 GMT+01:00'
    # DHL expects GMT+01:00 format, so we use +01:00 for Italian timezone
    return shipping_time.strftime("%Y-%m-%dT%H:%M:%S GMT+01:00")
