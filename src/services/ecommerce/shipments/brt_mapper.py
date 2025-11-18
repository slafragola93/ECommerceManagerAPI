from typing import Dict, Any, List, Optional
import json
from sqlalchemy.engine import Row
from src.models.brt_configuration import BrtConfiguration
from src.services.external.province_service import province_service
import logging

logger = logging.getLogger(__name__)


class BrtMapper:
    """
    Mapper for converting Order data to BRT REST API payload
    
    Based on the PHP implementation, BRT requires:
    1. Routing call to normalize address
    2. Create shipment call
    3. Optional confirm call if autoconfirm is enabled
    """
    
    def build_routing_request(
        self,
        brt_config: BrtConfiguration,
        receiver_address: Row,
        packages: List[Row],
        receiver_country_iso: str,
        service_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build BRT routing request payload to normalize recipient address
        
        Args:
            brt_config: BRT configuration
            receiver_address: Receiver address row
            packages: List of package rows
            service_type: Service type code (defaults to brt_config.rate_code)
            
        Returns:
            BRT routing payload dict
        """
        # Calculate total weight
        total_weight = self._calculate_total_weight(packages, brt_config.default_weight)
        
        # Get service type
        service = service_type or str(brt_config.rate_code) if brt_config.rate_code else 'E'
        
        # Get province abbreviation using ProvinceService
        province = ""
        print(f"1 Receiver address: {receiver_address.state}")
        if hasattr(receiver_address, 'state') and receiver_address.state:
            print(f"Receiver address state: {receiver_address.state}")
            province = province_service.get_province_abbreviation(receiver_address.state)
            print(f"Province: {province}")
            if not province:
                # Fallback: use first 2 uppercase letters if service doesn't find it
                province = str(receiver_address.state).upper()[:2]
        elif hasattr(receiver_address, 'province_code') and receiver_address.province_code:
            # If province_code is already an abbreviation, use it directly
            province = str(receiver_address.province_code).upper()[:2]
        
        # Get country code from parameter
        country = receiver_country_iso.upper() if receiver_country_iso else "IT"
        
        payload = {
            "account": {
                "userID": str(brt_config.api_user),
                "password": str(brt_config.api_password)
            },
            "routingData": {
                "network": brt_config.network or "",
                "departureDepot": int(brt_config.departure_depot),
                "senderCustomerCode": int(brt_config.client_code),
                "deliveryFreightTypeCode": "DAP",
                "consigneeCompanyName": receiver_address.company,
                "consigneeAddress": receiver_address.address1 or "",
                "consigneeZIPCode": receiver_address.postcode or "",
                "consigneeCity": receiver_address.city or "",
                "consigneeProvinceAbbreviation": province,
                "consigneeCountryAbbreviationISOAlpha2": country,
                "serviceType": service,
                "numberOfParcels": len(packages) if packages else 1,
                "weightKG": round(total_weight, 3),
                "volumeM3": 0.0,
                "variousParticularitiesManagementCode": "",
                "particularDelivery1": "",
                "particularDelivery2": ""
            }
        }
        
        logger.debug(f"BRT Routing Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        return payload
    
    def build_create_request(
        self,
        brt_config: BrtConfiguration,
        receiver_address: Row,
        packages: List[Row],
        reference: str,
        receiver_country_iso: str,
        normalized_address: Optional[Dict[str, Any]] = None,
        service_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build BRT create shipment request payload
        
        Args:
            brt_config: BRT configuration
            receiver_address: Receiver address row
            packages: List of package rows
            reference: Order reference (internal_reference)
            normalized_address: Normalized address from routing (optional)
            service_type: Service type code (defaults to brt_config.rate_code)
            
        Returns:
            BRT create payload dict
        """
        # Use normalized address if available, otherwise use original
        zip_code = normalized_address.get("consigneeZIPCode") if normalized_address else receiver_address.postcode or ""
        city = normalized_address.get("consigneeCity") if normalized_address else receiver_address.city or ""
        province = normalized_address.get("consigneeProvinceAbbreviation") if normalized_address else ""
        
        if not province:
            # Get province abbreviation using ProvinceService
            if hasattr(receiver_address, 'state') and receiver_address.state:
                print(f"Receiver address state: {receiver_address.state}")
                province = province_service.get_province_abbreviation(receiver_address.state)
                if not province:
                    # Fallback: use first 2 uppercase letters if service doesn't find it
                    province = str(receiver_address.state).upper()[:2]
            elif hasattr(receiver_address, 'province_code') and receiver_address.province_code:
                # If province_code is already an abbreviation, use it directly
                province = str(receiver_address.province_code).upper()[:2]
        
        # Get country code from parameter or normalized address
        print(f"ISO CODE RECEIVER: {receiver_country_iso}")
        if normalized_address and normalized_address.get("consigneeCountryAbbreviationISOAlpha2"):
            country = normalized_address["consigneeCountryAbbreviationISOAlpha2"]
        elif receiver_country_iso:
            country = receiver_country_iso.upper()
        
        # Calculate total weight
        total_weight = self._calculate_total_weight(packages, brt_config.default_weight)
        
        # Get service type
        service = service_type or str(brt_config.rate_code) if brt_config.rate_code else 'E'
        
        # Build recipient name
        recipient_name = ""
        if hasattr(receiver_address, 'firstname') and receiver_address.firstname:
            recipient_name = str(receiver_address.firstname)
        if hasattr(receiver_address, 'lastname') and receiver_address.lastname:
            recipient_name = f"{recipient_name} {receiver_address.lastname}".strip()
        
        # Company name (required)
        company_name = receiver_address.company or recipient_name or "Privato"
        
        # Get recipient contact info
        phone = ""
        if hasattr(receiver_address, 'phone') and receiver_address.phone:
            phone = str(receiver_address.phone)
        else:
            phone = "0000000000"  # Default
        
        email = ""
        if hasattr(receiver_address, 'email') and receiver_address.email:
            email = str(receiver_address.email)
        
        # Numeric reference (use order ID if reference is numeric, otherwise timestamp)
        try:
            numeric_ref = int(reference) if reference and reference.isdigit() else None
        except (ValueError, AttributeError):
            numeric_ref = None
        
        if numeric_ref is None:
            import time
            numeric_ref = int(time.time())
        
        alphanumeric_ref = reference or str(numeric_ref)
        
        # Build createData
        create_data = {
            "network": brt_config.network or "",
            "departureDepot": int(brt_config.departure_depot),
            "senderCustomerCode": int(brt_config.client_code),
            "deliveryFreightTypeCode": "DAP",
            "consigneeCompanyName": company_name,
            "consigneeAddress": receiver_address.address1 or "",
            "consigneeZIPCode": zip_code,
            "consigneeCity": city,
            "consigneeProvinceAbbreviation": province,
            "consigneeCountryAbbreviationISOAlpha2": country,
            "consigneeContactName": recipient_name,
            "consigneeTelephone": phone,
            "consigneeEMail": email,
            "isAlertRequired": "1" if email else "0",
            "serviceType": service,
            "insuranceAmount": 0.0,
            "insuranceAmountCurrency": "",
            "senderParcelType": "",
            "numberOfParcels": len(packages) if packages else 1,
            "weightKG": round(total_weight, 3),
            "volumeM3": 0.0,
            "quantityToBeInvoiced": 0,
            "cashOnDelivery": 0,
            "isCODMandatory": "0",
            "numericSenderReference": numeric_ref,
            "alphanumericSenderReference": alphanumeric_ref,
            "notes": brt_config.notes or "",
            "parcelsHandlingCode": "2"
        }
        
        # Build payload
        payload = {
            "account": {
                "userID": str(brt_config.api_user),
                "password": str(brt_config.api_password)
            },
            "createData": create_data,
            "isLabelRequired": 1,
            "labelParameters": {
                "outputType": (brt_config.label_format or "PDF").upper(),
                "offsetX": 0,
                "offsetY": 0,
                "isBorderRequired": 0,
                "isLogoRequired": 0,
                "isBarcodeControlRowRequired": 0
            }
        }
        
        logger.debug(f"BRT Create Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        return payload
    
    def build_confirm_request(
        self,
        brt_config: BrtConfiguration,
        numeric_reference: int,
        alphanumeric_reference: str
    ) -> Dict[str, Any]:
        """
        Build BRT confirm shipment request payload
        
        Args:
            brt_config: BRT configuration
            numeric_reference: Numeric sender reference
            alphanumeric_reference: Alphanumeric sender reference
            
        Returns:
            BRT confirm payload dict
        """
        payload = {
            "account": {
                "userID": str(brt_config.api_user),
                "password": str(brt_config.api_password)
            },
            "confirmData": {
                "senderCustomerCode": int(brt_config.client_code),
                "numericSenderReference": numeric_reference,
                "alphanumericSenderReference": alphanumeric_reference
            }
        }
        
        logger.debug(f"BRT Confirm Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        return payload
    
    def _calculate_total_weight(self, packages: List[Row], default_weight: Optional[int]) -> float:
        """Calculate total weight from packages or use default"""
        if packages:
            total = 0.0
            for package in packages:
                if hasattr(package, 'weight') and package.weight:
                    total += float(package.weight)
            if total > 0:
                return total
        
        # Use default weight
        if default_weight:
            return float(default_weight)
        
        # Fallback to 1.0 kg
        return 1.0
    
    def extract_tracking_from_response(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract tracking number from BRT create response
        
        Args:
            response: BRT API response
            
        Returns:
            Tracking number or None
        """
        try:
            create_response = response.get("createResponse", {})
            labels = create_response.get("labels", {})
            
            # Check for label array
            label_list = labels.get("label", [])
            if isinstance(label_list, list) and len(label_list) > 0:
                first_label = label_list[0]
                # Try trackingByParcelID first
                tracking = first_label.get("trackingByParcelID")
                if tracking:
                    return str(tracking)
                # Fallback to parcelID
                parcel_id = first_label.get("parcelID")
                if parcel_id:
                    return str(parcel_id)
            
            # Try parcelNumberFrom
            parcel_number = create_response.get("parcelNumberFrom")
            if parcel_number:
                return str(parcel_number)
            
        except (KeyError, AttributeError, TypeError) as e:
            logger.warning(f"Error extracting tracking from BRT response: {e}")
        
        return None
    
    def extract_label_from_response(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract base64 PDF label from BRT create/confirm response
        
        Args:
            response: BRT API response
            
        Returns:
            Base64 encoded PDF string or None
        """
        try:
            create_response = response.get("createResponse", {})
            labels = create_response.get("labels", {})
            
            # Check for label array
            label_list = labels.get("label", [])
            if isinstance(label_list, list):
                # If multiple labels, return the first one
                # (In future, could combine multiple PDFs)
                for label in label_list:
                    stream = label.get("stream")
                    if stream:
                        return str(stream)
            
            # Try other paths
            paths = [
                ["createResponse", "labelPDF"],
                ["label", "content"],
                ["labelPDF"],
            ]
            
            for path in paths:
                value = response
                try:
                    for key in path:
                        value = value[key]
                    if isinstance(value, str) and value:
                        return value
                except (KeyError, TypeError):
                    continue
            
        except (KeyError, AttributeError, TypeError) as e:
            logger.warning(f"Error extracting label from BRT response: {e}")
        
        return None

