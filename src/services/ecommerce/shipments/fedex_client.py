import httpx
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.engine import Row
import logging

from src.core.settings import get_carrier_integration_settings
from src.services.core.tool import convert_decimals_to_float

logger = logging.getLogger(__name__)


class FedexClient:
    """FedEx Ship API HTTP client with OAuth 2.0 authentication support"""
    
    def __init__(self):
        self.settings = get_carrier_integration_settings()
        self.base_url_prod = self.settings.fedex_base_url_prod
        self.base_url_sandbox = self.settings.fedex_base_url_sandbox
        
        # Token cache: {carrier_api_id: {"token": "...", "expires_at": datetime}}
        self._token_cache: Dict[int, Dict[str, Any]] = {}
    
    async def get_access_token(
        self,
        credentials: Row,
        fedex_config: Row
    ) -> str:
        """
        Get OAuth 2.0 access token with caching and auto-refresh
        
        Args:
            credentials: CarrierApi row with use_sandbox flag
            fedex_config: FedexConfiguration row with OAuth credentials
            
        Returns:
            Access token string
        """
        carrier_api_id = getattr(credentials, 'id_carrier_api', None)
        if not carrier_api_id:
            raise ValueError("Missing id_carrier_api in credentials")
        
        # Check cache
        if carrier_api_id in self._token_cache:
            cached = self._token_cache[carrier_api_id]
            expires_at = cached.get("expires_at")
            
            # Refresh if expires in less than 5 minutes
            if expires_at and expires_at > datetime.now() + timedelta(minutes=5):
                logger.debug(f"Using cached FedEx token for carrier_api_id {carrier_api_id}")
                return cached["token"]
        
        # Get new token
        url = f"{self._get_base_url(credentials.use_sandbox)}/oauth/token"
        
        # Use client_credentials grant type (simplified)
        client_id = getattr(fedex_config, 'client_id', None)
        client_secret = getattr(fedex_config, 'client_secret', None)
        
        if not client_id or not client_secret:
            raise ValueError("Missing client_id or client_secret in FedexConfiguration")
        
        # Build form data for client_credentials grant type
        form_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        logger.info(f"FedEx OAuth Request URL: {url}")
        logger.info(f"FedEx OAuth Grant Type: client_credentials")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=headers, data=form_data)
                
                # Check for errors
                if response.status_code == 401:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_code = error_data.get("errors", [{}])[0].get("code", "NOT.AUTHORIZED.ERROR")
                    error_message = error_data.get("errors", [{}])[0].get("message", "Invalid credentials")
                    raise ValueError(f"FedEx OAuth Error (401): {error_code} - {error_message}")
                
                if response.status_code >= 500:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_code = error_data.get("errors", [{}])[0].get("code", "INTERNAL.SERVER.ERROR")
                    error_message = error_data.get("errors", [{}])[0].get("message", "Server error")
                    raise RuntimeError(f"FedEx OAuth Error ({response.status_code}): {error_code} - {error_message}")
                
                response.raise_for_status()
                response_data = response.json()
                
                access_token = response_data.get("access_token")
                expires_in = response_data.get("expires_in", 3600)  # Default 1 hour
                
                if not access_token:
                    raise ValueError("FedEx OAuth response missing access_token")
                
                # Cache token
                expires_at = datetime.now() + timedelta(seconds=expires_in)
                self._token_cache[carrier_api_id] = {
                    "token": access_token,
                    "expires_at": expires_at
                }
                
                logger.info(f"FedEx OAuth token obtained successfully, expires in {expires_in}s")
                return access_token
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    error_data = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
                    error_code = error_data.get("errors", [{}])[0].get("code", "SERVICE.UNAVAILABLE.ERROR")
                    error_message = error_data.get("errors", [{}])[0].get("message", "Service unavailable")
                    raise RuntimeError(f"FedEx OAuth Error (503): {error_code} - {error_message}")
                raise
    
    async def create_shipment(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        fedex_config: Row
    ) -> Dict[str, Any]:
        """
        Create FedEx shipment via Ship API
        
        Args:
            payload: FedEx shipment request payload
            credentials: CarrierApi row with use_sandbox flag
            fedex_config: FedexConfiguration row
            
        Returns:
            FedEx API response as dict
        """
        # Get access token
        access_token = await self.get_access_token(credentials, fedex_config)
        
        url = f"{self._get_base_url(credentials.use_sandbox)}/ship/v1/shipments"
        headers = self._get_headers(access_token)
        
        # Convert Decimal objects to float for JSON serialization
        payload_serializable = convert_decimals_to_float(payload)
        
        logger.info(f"FedEx Create Shipment Request URL: {url}")
        logger.info(f"FedEx Create Shipment Request Method: POST")
        logger.info(f"FedEx Create Shipment Request Payload: {json.dumps(payload_serializable, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await self._make_request_with_retry(
                client, "POST", url, headers=headers, json=payload_serializable
            )
        
        response_data = response.json()
        logger.info(f"FedEx Create Shipment Response Status: {response.status_code}")
        logger.info(f"FedEx Create Shipment Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        # Check for errors
        self._check_fedex_errors(response_data, response.status_code)
        
        return response_data
    
    async def validate_shipment(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        fedex_config: Row
    ) -> Dict[str, Any]:
        """
        Validate FedEx shipment before creation
        
        Args:
            payload: FedEx shipment validation request payload (same structure as create)
            credentials: CarrierApi row with use_sandbox flag
            fedex_config: FedexConfiguration row
            
        Returns:
            FedEx API validation response as dict
        """
        # Get access token
        access_token = await self.get_access_token(credentials, fedex_config)
        
        url = f"{self._get_base_url(credentials.use_sandbox)}/ship/v1/shipments/packages/validate"
        headers = self._get_headers(access_token)
        
        # Convert Decimal objects to float for JSON serialization
        payload_serializable = convert_decimals_to_float(payload)
        
        logger.info(f"FedEx Validate Shipment Request URL: {url}")
        logger.info(f"FedEx Validate Shipment Request Method: POST")
        logger.info(f"FedEx Validate Shipment Request Payload: {json.dumps(payload_serializable, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "POST", url, headers=headers, json=payload_serializable
            )
        
        response_data = response.json()
        logger.info(f"FedEx Validate Shipment Response Status: {response.status_code}")
        logger.info(f"FedEx Validate Shipment Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        # Check for errors
        self._check_fedex_errors(response_data, response.status_code)
        
        return response_data
    
    async def get_async_results(
        self,
        job_id: str,
        account_number: str,
        credentials: Row,
        fedex_config: Row
    ) -> Dict[str, Any]:
        """
        Get async shipment results
        
        Args:
            job_id: Job ID from async shipment creation
            account_number: FedEx account number
            credentials: CarrierApi row with use_sandbox flag
            fedex_config: FedexConfiguration row
            
        Returns:
            FedEx API async results response as dict
        """
        # Get access token
        access_token = await self.get_access_token(credentials, fedex_config)
        
        url = f"{self._get_base_url(credentials.use_sandbox)}/ship/v1/shipments/results"
        headers = self._get_headers(access_token)
        
        payload = {
            "jobId": job_id,
            "accountNumber": account_number
        }
        
        logger.info(f"FedEx Get Async Results Request URL: {url}")
        logger.info(f"FedEx Get Async Results Request Method: POST")
        logger.info(f"FedEx Get Async Results Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "POST", url, headers=headers, json=payload
            )
        
        response_data = response.json()
        logger.info(f"FedEx Get Async Results Response Status: {response.status_code}")
        logger.info(f"FedEx Get Async Results Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        # Check for errors
        self._check_fedex_errors(response_data, response.status_code)
        
        return response_data
    
    async def cancel_shipment(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        fedex_config: Row
    ) -> Dict[str, Any]:
        """
        Cancel FedEx shipment
        
        Args:
            payload: FedEx cancel request payload with trackingNumber and accountNumber
            credentials: CarrierApi row with use_sandbox flag
            fedex_config: FedexConfiguration row
            
        Returns:
            FedEx API cancel response as dict
        """
        # Get access token
        access_token = await self.get_access_token(credentials, fedex_config)
        
        url = f"{self._get_base_url(credentials.use_sandbox)}/ship/v1/shipments/cancel"
        headers = self._get_headers(access_token)
        
        logger.info(f"FedEx Cancel Shipment Request URL: {url}")
        logger.info(f"FedEx Cancel Shipment Request Method: PUT")
        logger.info(f"FedEx Cancel Shipment Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "PUT", url, headers=headers, json=payload
            )
        
        response_data = response.json()
        logger.info(f"FedEx Cancel Shipment Response Status: {response.status_code}")
        logger.info(f"FedEx Cancel Shipment Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        # Check for errors
        self._check_fedex_errors(response_data, response.status_code)
        
        return response_data
    
    def _get_base_url(self, use_sandbox: bool) -> str:
        """
        Get base URL based on environment
        
        Args:
            use_sandbox: Whether to use sandbox environment
            
        Returns:
            Base URL string
        """
        return self.base_url_sandbox if use_sandbox else self.base_url_prod
    
    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """
        Generate HTTP headers for FedEx API requests
        
        Args:
            access_token: OAuth 2.0 access token
            
        Returns:
            Headers dict
        """
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _check_fedex_errors(self, response_data: Dict[str, Any], status_code: int) -> None:
        """
        Check for FedEx API errors in response and raise appropriate exceptions
        
        Args:
            response_data: FedEx API response dict
            status_code: HTTP status code
            
        Raises:
            ValueError: For client errors (400, 401, 403, 404, 422)
            RuntimeError: For server errors (500, 503)
        """
        if status_code < 400:
            return  # No errors
        
        errors = response_data.get("errors", [])
        transaction_id = response_data.get("transactionId", "N/A")
        
        if not errors:
            # No error details, use generic message
            if status_code == 400:
                raise ValueError(f"FedEx Bad Request (400): Invalid request format")
            elif status_code == 401:
                raise ValueError(f"FedEx Unauthorized (401): Authentication failed")
            elif status_code == 403:
                raise ValueError(f"FedEx Forbidden (403): Access denied")
            elif status_code == 404:
                raise ValueError(f"FedEx Not Found (404): Resource not found")
            elif status_code == 500:
                raise RuntimeError(f"FedEx Internal Server Error (500): Server error")
            elif status_code == 503:
                raise RuntimeError(f"FedEx Service Unavailable (503): Service temporarily unavailable")
            else:
                raise RuntimeError(f"FedEx API Error ({status_code}): Unknown error")
            return
        
        # Collect all error messages
        error_messages = []
        error_codes = []
        
        for error in errors:
            error_code = error.get("code", "UNKNOWN_ERROR")
            error_message = error.get("message", "Unknown error")
            error_codes.append(error_code)
            error_messages.append(f"{error_code}: {error_message}")
        
        # Build combined error message
        combined_message = " | ".join(error_messages)
        
        # Map status codes to appropriate exceptions
        if status_code == 400:
            # Bad Request - Validation errors
            # Common codes: ACCOUNTNUMBER.REGISTRATION.REQUIRED, etc.
            raise ValueError(f"FedEx Validation Error (400): {combined_message} [TransactionId: {transaction_id}]")
        
        elif status_code == 401:
            # Unauthorized - Authentication failed
            # Common code: NOT.AUTHORIZED.ERROR
            raise ValueError(f"FedEx Authorization Error (401): {combined_message} [TransactionId: {transaction_id}]")
        
        elif status_code == 403:
            # Forbidden - Access denied
            # Common code: FORBIDDEN.ERROR
            raise ValueError(f"FedEx Forbidden (403): {combined_message} [TransactionId: {transaction_id}]")
        
        elif status_code == 404:
            # Not Found - Resource not available
            # Common code: NOT.FOUND.ERROR
            raise ValueError(f"FedEx Not Found (404): {combined_message} [TransactionId: {transaction_id}]")
        
        elif status_code == 422:
            # Unprocessable Entity - Validation errors
            raise ValueError(f"FedEx Validation Error (422): {combined_message} [TransactionId: {transaction_id}]")
        
        elif status_code == 500:
            # Internal Server Error
            # Common code: INTERNAL.SERVER.ERROR
            raise RuntimeError(f"FedEx Internal Server Error (500): {combined_message} [TransactionId: {transaction_id}]")
        
        elif status_code == 503:
            # Service Unavailable
            # Common code: SERVICE.UNAVAILABLE.ERROR
            raise RuntimeError(f"FedEx Service Unavailable (503): {combined_message} [TransactionId: {transaction_id}]")
        
        else:
            # Other 4xx/5xx errors
            if 400 <= status_code < 500:
                raise ValueError(f"FedEx Client Error ({status_code}): {combined_message} [TransactionId: {transaction_id}]")
            else:
                raise RuntimeError(f"FedEx Server Error ({status_code}): {combined_message} [TransactionId: {transaction_id}]")
    
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
                            f"FedEx API request failed with status {response.status_code}, "
                            f"retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"FedEx API request failed after {max_retries} retries")
                        response.raise_for_status()
                
                # Other 4xx errors - don't retry
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"FedEx API request timeout, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error("FedEx API request timeout after all retries")
                    raise
            except httpx.RequestError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"FedEx API request error: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"FedEx API request error after all retries: {e}")
                    raise
        
        # This should never be reached
        raise RuntimeError("Unexpected retry loop exit")

