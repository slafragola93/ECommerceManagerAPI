import httpx
import asyncio
import json
from typing import Dict, Any, Optional, Tuple, Type
from sqlalchemy.engine import Row
import logging

from src.core.settings import get_carrier_integration_settings

logger = logging.getLogger(__name__)

# Mapping dei codici di errore BRT: (message, category)
# Le eccezioni vengono determinate dinamicamente in base alla categoria
BRT_ERROR_MAPPING: Dict[int, Tuple[str, str]] = {
    # Authentication errors
    -7: ("BRT login failed", "authentication"),
    -57: ("BRT login parameter missing", "authentication"),
    
    # Validation errors
    -5: ("BRT invalid parameter", "validation"),
    -10: ("BRT shipment number required", "validation"),
    -11: ("BRT shipment not found", "validation"),
    -21: ("BRT client code required", "validation"),
    -22: ("BRT non-unique reference", "validation"),
    -30: ("BRT parcel ID required", "validation"),
    -68: ("BRT wrong or inconsistent data", "validation"),
    -69: ("BRT invalid or non-existent pudoId", "validation"),
    
    # Infrastructure errors
    -3: ("BRT database connection problem", "infrastructure"),
    
    # Business rule errors
    -1: ("BRT generic error", "business"),
    -63: ("BRT routing calculation error", "business"),
    -64: ("BRT parcel numbering error", "business"),
    -65: ("BRT label printing error", "business"),
    -67: ("BRT user/account error: senderCustomerCode not linked to account.userId", "business"),
    -101: ("BRT shipment cannot be confirmed", "business"),
    -102: ("BRT shipment already confirmed", "business"),
    -151: ("BRT shipment never created or created more than 40 days ago", "business"),
    -152: ("BRT shipment already being processed by depot", "business"),
    -153: ("BRT shipment being processed, try again", "business"),
    -154: ("BRT multiple shipments found with same identifiers", "business"),
    -155: ("BRT record allocated for cancellation", "business"),
}

# Codici di warning che non devono sollevare eccezioni
BRT_WARNING_CODES = {4, 5, 6}

# Descriptions for warning codes
BRT_WARNING_DESCRIPTIONS = {
    4: "Normalizzazione dati eseguita (City/ZIP code/Province abb.)",
    5: "Indirizzo destinatario modificato con l'indirizzo del BRTfermopoint pudo",
    6: "Impostati i dati del destinatario con i dati del depot di ritorno"
}


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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._make_request_with_retry(
                client, "GET", url, headers=headers
            )
        
        # Se c'è un errore 401, logga i dettagli
        if response.status_code == 401:
            logger.error(f"BRT Tracking authentication failed. Response: {response.text}")
            try:
                error_data = response.json()
                logger.error(f"BRT Tracking error details: {json.dumps(error_data, indent=2)}")
            except:
                pass
        
        response_data = response.json()
        
        # Check for BRT API errors in response
        self._check_brt_response_errors(response_data)
        
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
        
        return headers
    
    def _check_brt_response_errors(self, response_data: Dict[str, Any]) -> None:
        """
        Check for BRT API errors in response and handle them appropriately
        
        - Warning codes (4, 5, 6) are logged but don't raise exceptions
        - Error codes (< 0) are mapped to appropriate exceptions based on BRT_ERROR_MAPPING
        
        Args:
            response_data: BRT API response dict
            
        Raises:
            AuthenticationException: For authentication errors (-7, -57)
            ValidationException: For validation errors (-5, -10, -11, -21, -22, -30, -68, -69)
            InfrastructureException: For infrastructure errors (-3)
            BusinessRuleException: For business rule errors (all other negative codes)
        """
        from src.core.exceptions import (
            BusinessRuleException,
            AuthenticationException,
            ValidationException,
            InfrastructureException
        )
        
        if not isinstance(response_data, dict):
            return
        
        # Check for executionMessage in createResponse, routingData, confirmResponse, deleteResponse, trackingResponse, ttParcelIdResponse, etc.
        response_keys = ["createResponse", "routingData", "confirmResponse", "deleteResponse", "trackingResponse", "ttParcelIdResponse"]
        
        for key in response_keys:
            if key in response_data:
                exec_message = response_data[key].get("executionMessage", {})
                if not exec_message:
                    continue
                
                severity = exec_message.get("severity", "")
                error_code = exec_message.get("code")
                error_message = exec_message.get("message", "Unknown BRT error")
                code_desc = exec_message.get("codeDesc", "")
                
                # Handle warnings (4, 5, 6) - log but don't raise exception
                if error_code in BRT_WARNING_CODES:
                    warning_desc = BRT_WARNING_DESCRIPTIONS.get(error_code, f"Warning code {error_code}")
                    logger.info(
                        f"BRT API Warning (Code: {error_code}, {warning_desc}): {error_message}"
                    )
                    continue
                
                # Handle errors (negative codes or ERROR severity)
                is_error = False
                if error_code is not None and error_code < 0:
                    is_error = True
                elif severity and severity.upper() == "ERROR":
                    is_error = True
                
                if is_error:
                    # Get exception type and message from mapping
                    exception_type = BusinessRuleException
                    base_message = "BRT API error"
                    error_category = "business"
                    
                    if error_code in BRT_ERROR_MAPPING:
                        base_message, error_category = BRT_ERROR_MAPPING[error_code]
                        
                        # Map to appropriate exception type based on category
                        if error_category == "authentication":
                            exception_type = AuthenticationException
                        elif error_category == "validation":
                            exception_type = ValidationException
                        elif error_category == "infrastructure":
                            exception_type = InfrastructureException
                        else:
                            exception_type = BusinessRuleException
                    
                    # Build detailed error message
                    error_details = f"{base_message} (Code: {error_code}"
                    if code_desc:
                        error_details += f", {code_desc}"
                    error_details += f"): {error_message}"
                    
                    logger.error(f"BRT API returned error: {error_details}")
                    
                    # Raise appropriate exception with details using generic convention
                    raise exception_type(
                        error_details,
                        details={
                            "carrier_error_code": error_code,
                            "carrier_error_description": code_desc or error_message,
                            "carrier_name": "BRT",
                            "error_category": error_category
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

