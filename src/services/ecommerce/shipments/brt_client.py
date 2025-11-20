import httpx
import asyncio
import json
from typing import Dict, Any, Optional
from sqlalchemy.engine import Row
import logging

from src.core.settings import get_carrier_integration_settings

logger = logging.getLogger(__name__)


class BrtClient:
    """BRT REST API HTTP client with authentication support"""
    
    def __init__(self):
        self.settings = get_carrier_integration_settings()
        self.base_url_prod = self.settings.brt_base_url_prod
        self.base_url_sandbox = self.settings.brt_base_url_sandbox
    
    async def routing(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        brt_config: Row
    ) -> Dict[str, Any]:
        """
        BRT Routing API - normalizes recipient address
        
        Args:
            payload: Routing request payload with account and routingData
            credentials: CarrierApi row (not used for BRT, but kept for consistency)
            brt_config: BrtConfiguration row
            
        Returns:
            BRT API response with normalized address data
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/rest/v1/shipments/routing"
        headers = self._get_headers(for_tracking=False)
        
        logger.info(f"BRT Routing Request URL: {url}")
        logger.info(f"BRT Routing Request Method: PUT")
        logger.info(f"BRT Routing Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "PUT", url, headers=headers, json=payload
            )
        
        response_data = response.json()
        
        # Check for BRT API errors in response
        self._check_brt_response_errors(response_data)
        
        return response_data
    
    async def create_shipment(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        brt_config: Row
    ) -> Dict[str, Any]:
        """
        Create BRT shipment via REST API
        
        Args:
            payload: BRT shipment request payload
            credentials: CarrierApi row (not used for BRT, but kept for consistency)
            brt_config: BrtConfiguration row
            
        Returns:
            BRT API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/rest/v1/shipments/shipment"
        headers = self._get_headers(for_tracking=False)
        
        logger.info(f"BRT Create Shipment Request URL: {url}")
        logger.info(f"BRT Create Shipment Request Method: POST")
        logger.info(f"BRT Create Shipment Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await self._make_request_with_retry(
                client, "POST", url, headers=headers, json=payload
            )
        
        # Parse JSON response
        try:
            response_data = response.json()
        except Exception as e:
            logger.error(f"BRT Create Shipment Response is not valid JSON: {e}")
            raise ValueError(f"BRT API returned invalid JSON response: {e}")
        
        # Check for HTTP errors
        if response.status_code >= 400:
            error_message = self._extract_error_message(response_data)
            if response.status_code == 400:
                raise ValueError(f"BRT Bad Request (400): {error_message}")
            if response.status_code >= 500:
                raise RuntimeError(f"BRT Server Error ({response.status_code}): {error_message}")
        
        # Check for BRT API errors in response (even if HTTP status is 200)
        self._check_brt_response_errors(response_data)
        
        return response_data
    
    async def confirm_shipment(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        brt_config: Row
    ) -> Dict[str, Any]:
        """
        Confirm BRT shipment (same endpoint as create, but PUT method)
        
        Args:
            payload: BRT confirm request payload
            credentials: CarrierApi row (not used for BRT, but kept for consistency)
            brt_config: BrtConfiguration row
            
        Returns:
            BRT API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/rest/v1/shipments/shipment"
        headers = self._get_headers(for_tracking=False)
        
        logger.info(f"BRT Confirm Shipment Request URL: {url}")
        logger.info(f"BRT Confirm Shipment Request Method: PUT")
        logger.info(f"BRT Confirm Shipment Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "PUT", url, headers=headers, json=payload
            )
        
        response_data = response.json()
        
        # Check for BRT API errors in response
        self._check_brt_response_errors(response_data)
        
        return response_data
    
    async def get_tracking(
        self,
        parcel_id: str,
        credentials: Row,
        brt_config: Row
    ) -> Dict[str, Any]:
        """
        Get BRT tracking information for a parcel
        
        Args:
            parcel_id: BRT parcel ID (tracking number)
            credentials: CarrierApi row (not used for BRT, but kept for consistency)
            brt_config: BrtConfiguration row with api_user and api_password
            
        Returns:
            BRT API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/rest/v1/tracking/parcelID/{parcel_id}"
        headers = self._get_headers(for_tracking=True, brt_config=brt_config)
        
        logger.info(f"BRT Get Tracking Request URL: {url}")
        logger.info(f"BRT Get Tracking Request Method: GET")
        # Log headers (senza password per sicurezza)
        safe_headers = {k: v if k != "password" else "***" for k, v in headers.items()}
        logger.info(f"BRT Get Tracking Request Headers: {json.dumps(safe_headers, indent=2)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "GET", url, headers=headers
            )
        
        # Log response status for debugging
        logger.info(f"BRT Get Tracking Response Status: {response.status_code}")
        
        # Se c'è un errore 401, logga i dettagli
        if response.status_code == 401:
            logger.error(f"BRT Tracking authentication failed. Response: {response.text}")
            try:
                error_data = response.json()
                logger.error(f"BRT Tracking error details: {json.dumps(error_data, indent=2)}")
            except:
                pass
        
        response_data = response.json()
        
        return response_data
    
    async def cancel_shipment(
        self,
        payload: Dict[str, Any],
        credentials: Row,
        brt_config: Row
    ) -> Dict[str, Any]:
        """
        Cancel BRT shipment
        
        Args:
            payload: BRT cancel request payload
            credentials: CarrierApi row (not used for BRT, but kept for consistency)
            brt_config: BrtConfiguration row
            
        Returns:
            BRT API response as dict
        """
        url = f"{self._get_base_url(credentials.use_sandbox)}/rest/v1/shipments/delete"
        headers = self._get_headers(for_tracking=False)
        
        logger.info(f"BRT Cancel Shipment Request URL: {url}")
        logger.info(f"BRT Cancel Shipment Request Method: PUT")
        logger.info(f"BRT Cancel Shipment Request Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "PUT", url, headers=headers, json=payload
            )
        
        response_data = response.json()
        
        # Check for BRT API errors in response
        self._check_brt_response_errors(response_data)
        
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
    
    def _get_headers(self, for_tracking: bool = False, brt_config: Optional[Row] = None) -> Dict[str, str]:
        """
        Generate HTTP headers for BRT API requests
        
        Args:
            for_tracking: If True, add userID/password headers for tracking API
            brt_config: BrtConfiguration row (required if for_tracking=True)
            
        Returns:
            Headers dict
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Tracking API uses headers for authentication
        if for_tracking and brt_config:
            api_user = getattr(brt_config, 'api_user', None)
            api_password = getattr(brt_config, 'api_password', None)
            
            # Verifica che i valori esistano e non siano vuoti
            if api_user is None or api_user == "":
                raise ValueError(
                    f"Missing or empty BRT api_user in BrtConfiguration for carrier_api_id {getattr(brt_config, 'id_carrier_api', 'unknown')}"
                )
            if api_password is None or api_password == "":
                raise ValueError(
                    f"Missing or empty BRT api_password in BrtConfiguration for carrier_api_id {getattr(brt_config, 'id_carrier_api', 'unknown')}"
                )
            
            # BRT tracking API requires userID and password in headers (case-sensitive, as per PHP implementation)
            # PHP uses: 'userID: ' . $this->conf['username']
            headers["userID"] = str(api_user).strip()
            headers["password"] = str(api_password).strip()
            
            logger.info(f"BRT Tracking auth configured - userID: {api_user}, password: {'***' if api_password else 'None'}")
        
        return headers
    
    def _check_brt_response_errors(self, response_data: Dict[str, Any]) -> None:
        """
        Check for BRT API errors in response (severity: ERROR)
        Raises exception if error is found
        
        Args:
            response_data: BRT API response dict
            
        Raises:
            BusinessRuleException: If BRT API returned an error
        """
        from src.core.exceptions import BusinessRuleException
        
        if not isinstance(response_data, dict):
            return
        
        # Check for executionMessage in createResponse, routingData, confirmResponse, etc.
        response_keys = ["createResponse", "routingData", "confirmResponse", "deleteResponse"]
        
        for key in response_keys:
            if key in response_data:
                exec_message = response_data[key].get("executionMessage", {})
                severity = exec_message.get("severity", "")
                
                if severity and severity.upper() == "ERROR":
                    error_code = exec_message.get("code", "")
                    error_message = exec_message.get("message", "Unknown BRT error")
                    code_desc = exec_message.get("codeDesc", "")
                    
                    # Build detailed error message
                    error_details = f"BRT API Error (Code: {error_code}"
                    if code_desc:
                        error_details += f", {code_desc}"
                    error_details += f"): {error_message}"
                    
                    logger.error(f"BRT API returned error: {error_details}")
                    raise BusinessRuleException(
                        error_details,
                        details={
                            "brt_error_code": error_code,
                            "brt_code_desc": code_desc,
                            "brt_message": error_message
                        }
                    )
    
    def _extract_error_message(self, response_data: Dict[str, Any]) -> str:
        """Extract error message from BRT API response"""
        if isinstance(response_data, dict):
            # Try common error paths
            error_paths = [
                ["createResponse", "executionMessage", "message"],
                ["executionMessage", "message"],
                ["error", "message"],
                ["message"],
                ["detail"],
            ]
            
            for path in error_paths:
                value = response_data
                try:
                    for key in path:
                        value = value[key]
                    if isinstance(value, str) and value:
                        return value
                except (KeyError, TypeError):
                    continue
        
        return "Unknown error"
    
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
                            f"BRT API request failed with status {response.status_code}, "
                            f"retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"BRT API request failed after {max_retries} retries")
                        response.raise_for_status()
                
                # Other 4xx errors - don't retry
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"BRT API request timeout, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error("BRT API request timeout after all retries")
                    raise
            except httpx.RequestError as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"BRT API request error: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"BRT API request error after all retries: {e}")
                    raise
        
        # This should never be reached
        raise RuntimeError("Unexpected retry loop exit")

