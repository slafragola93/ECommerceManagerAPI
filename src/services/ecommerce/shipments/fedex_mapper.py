from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy.engine import Row
from src.models.fedex_configuration import FedexConfiguration
from src.core.exceptions import ValidationException
import logging

logger = logging.getLogger(__name__)


class FedexMapper:
    """
    Mapper for converting Order data to FedEx Ship API payload
    
    FedEx Ship API structure:
    - labelResponseOptions: "URL_ONLY"
    - requestedShipment: Complete shipment details
    - accountNumber: FedEx account number
    """
    
    def build_shipment_request(
        self,
        order_data: Row,
        fedex_config: FedexConfiguration,
        receiver_address: Row,
        receiver_country_iso: str,
        packages: List[Row],
        reference: Optional[str] = None,
        shipping_price_tax_incl: Optional[float] = None,
        order_details: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Build FedEx shipment request payload from order and configuration data
        
        Args:
            order_data: Order row with shipment data
            fedex_config: FedEx configuration
            receiver_address: Receiver address row
            receiver_country_iso: Receiver country ISO code (2 letters)
            packages: List of package rows for the order
            reference: Order reference (optional)
            
        Returns:
            FedEx API payload dict
        """
        # Get account number
        account_number = str(fedex_config.account_number) if fedex_config.account_number else ""
        
        # Build shipper contact and address
        shipper_contact = self._build_shipper_contact(fedex_config)
        shipper_address = self._build_shipper_address(fedex_config)
        
        # Build recipient contact and address
        recipient_contact = self._build_recipient_contact(receiver_address)
        recipient_address = self._build_recipient_address(receiver_address, receiver_country_iso)
        
        # Build package line items (without customsValue - it goes in commodities)
        package_line_items = self._build_package_line_items(packages, fedex_config)
        
        # Calculate total weight from package line items
        total_weight = sum(
            float(item.get("weight", {}).get("value", 0))
            for item in package_line_items
        )
        
        # Get service type and packaging type from config
        service_type = fedex_config.service_type  # Required field from fedex_configurations.service_type
        print(f"SERVICE TYPE: {service_type}")
        if not service_type:
            raise ValidationException(
                "service_type is required in FedEx configuration",
                details={"field": "service_type", "config_id": fedex_config.id_fedex_configuration if hasattr(fedex_config, 'id_fedex_configuration') else None}
            )
        packaging_type = fedex_config.packaging_type or "YOUR_PACKAGING"
        pickup_type = fedex_config.pickup_type or "DROPOFF_AT_FEDEX_LOCATION"
        payment_type = fedex_config.customs_charges or "SENDER"  # Use customs_charges for paymentType
        
        # Get label specification
        label_spec = self._build_label_specification(fedex_config)
        
        # Ship date (today or tomorrow)
        ship_datestamp = datetime.now().strftime("%Y-%m-%d")
        
        # Build customsClearanceDetail with dutiesPayment, commodities and totalCustomsValue if shipping price is provided
        customs_clearance_detail = None
        if shipping_price_tax_incl is not None and shipping_price_tax_incl > 0:
            # Build dutiesPayment
            duties_payment = self._build_duties_payment(fedex_config)
            
            # Build commodities from order details or packages
            commodities = self._build_commodities(
                order_details=order_details,
                packages=packages,
                shipping_price_tax_incl=shipping_price_tax_incl,
                fedex_config=fedex_config,
                receiver_country_iso=receiver_country_iso
            )
            
            customs_clearance_detail = {
                "dutiesPayment": duties_payment,
                "commodities": commodities,
                "totalCustomsValue": {
                    "amount": round(float(shipping_price_tax_incl), 2),
                    "currency": "EUR"
                }
            }
        
        # Build payload
        payload = {
            "labelResponseOptions": "URL_ONLY",
            "requestedShipment": {
                "shipper": {
                    "contact": shipper_contact,
                    "address": shipper_address
                },
                "recipients": [{
                    "contact": recipient_contact,
                    "address": recipient_address
                }],
                "shipDatestamp": ship_datestamp,
                "serviceType": service_type,
                "packagingType": packaging_type,
                "pickupType": pickup_type,
                "totalWeight": round(total_weight, 2),
                "blockInsightVisibility": False,
                "shippingChargesPayment": {
                    "paymentType": payment_type
                },
                "labelSpecification": label_spec,
                "requestedPackageLineItems": package_line_items
            },
            "accountNumber": {
                "value": account_number
            }
        }
        
        # Add customsClearanceDetail if available
        if customs_clearance_detail:
            payload["requestedShipment"]["customsClearanceDetail"] = customs_clearance_detail
        
        # Validate required fields
        self._validate_required_fields(payload)
        
        logger.debug(f"FedEx Shipment Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        return payload
    
    def build_validate_request(
        self,
        order_data: Row,
        fedex_config: FedexConfiguration,
        receiver_address: Row,
        receiver_country_iso: str,
        packages: List[Row],
        reference: Optional[str] = None,
        shipping_price_tax_incl: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Build FedEx validation request payload (same structure as shipment)
        
        Args:
            order_data: Order row with shipment data
            fedex_config: FedEx configuration
            receiver_address: Receiver address row
            receiver_country_iso: Receiver country ISO code
            packages: List of package rows
            reference: Order reference (optional)
            shipping_price_tax_incl: Shipping price with tax included (optional)
            
        Returns:
            FedEx validation payload dict (same as shipment)
        """
        # Validation uses the same structure as create shipment
        return self.build_shipment_request(
            order_data, fedex_config, receiver_address, receiver_country_iso, packages, reference, shipping_price_tax_incl
        )
    
    def build_cancel_request(
        self,
        tracking_number: str,
        account_number: str,
        deletion_control: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build FedEx cancel shipment request payload
        
        Args:
            tracking_number: FedEx tracking number
            account_number: FedEx account number
            deletion_control: Deletion control (DELETE_ONE_PACKAGE, DELETE_ALL_PACKAGES)
            
        Returns:
            FedEx cancel payload dict
        """
        payload = {
            "accountNumber": {
                "value": account_number
            },
            "trackingNumber": tracking_number
        }
        
        if deletion_control:
            payload["deletionControl"] = deletion_control
        
        logger.debug(f"FedEx Cancel Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        return payload
    
    def extract_label_from_response(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract label (base64 PDF) from FedEx API response
        
        Args:
            response: FedEx API response dict
            
        Returns:
            Base64 encoded label string or None
        """
        try:
            output = response.get("output", {})
            transaction_shipments = output.get("transactionShipments", [])
            
            if not transaction_shipments:
                logger.warning("No transactionShipments in FedEx response")
                return None
            
            # Get first shipment
            shipment = transaction_shipments[0]
            shipment_documents = shipment.get("shipmentDocuments", [])
            
            if not shipment_documents:
                logger.warning("No shipmentDocuments in FedEx response")
                return None
            
            # Find label document (usually first one)
            for doc in shipment_documents:
                doc_type = doc.get("documentType", "")
                if doc_type in ["LABEL", "COMMERCIAL_INVOICE"]:
                    # Try different possible fields for label content
                    content = doc.get("content") or doc.get("encodedLabel") or doc.get("stream")
                    if content:
                        return str(content)
            
            logger.warning("No label content found in shipmentDocuments")
            return None
            
        except (KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error extracting label from FedEx response: {e}")
            return None
    
    def extract_label_url_from_response(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract label URL from FedEx API response
        
        Args:
            response: FedEx API response dict
            
        Returns:
            URL string or None
        """
        try:
            output = response.get("output", {})
            transaction_shipments = output.get("transactionShipments", [])
            
            if not transaction_shipments:
                return None
            
            # Get first shipment
            shipment = transaction_shipments[0]
            shipment_documents = shipment.get("shipmentDocuments", [])
            
            if not shipment_documents:
                return None
            
            # Find document with URL (FedEx uses contentType and docType)
            # Accept any document with URL and docType="PDF" or contentType containing "LABEL"
            for doc in shipment_documents:
                url = doc.get("url")
                if url:
                    # Check if it's a PDF document (label)
                    doc_type = doc.get("docType", "").upper()
                    content_type = doc.get("contentType", "").upper()
                    # Accept PDF documents or any document with LABEL in contentType
                    if doc_type == "PDF" or "LABEL" in content_type:
                        logger.info(f"Found label URL in shipmentDocuments: {url} (docType: {doc_type}, contentType: {content_type})")
                        return str(url)
            
            return None
            
        except (KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error extracting label URL from FedEx response: {e}")
            return None
    
    def extract_tracking_from_response(self, response: Dict[str, Any]) -> List[str]:
        """
        Extract tracking numbers from FedEx API response
        
        Args:
            response: FedEx API response dict
            
        Returns:
            List of tracking numbers
        """
        tracking_numbers = []
        try:
            output = response.get("output", {})
            transaction_shipments = output.get("transactionShipments", [])
            
            for shipment in transaction_shipments:
                # Master tracking number
                master_tracking = shipment.get("masterTrackingNumber")
                if master_tracking:
                    tracking_numbers.append(str(master_tracking))
                
                # Piece tracking numbers
                piece_responses = shipment.get("pieceResponses", [])
                for piece in piece_responses:
                    tracking = piece.get("trackingNumber")
                    if tracking and str(tracking) not in tracking_numbers:
                        tracking_numbers.append(str(tracking))
            
        except (KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error extracting tracking from FedEx response: {e}")
        
        return tracking_numbers
    
    def _build_shipper_contact(self, fedex_config: FedexConfiguration) -> Dict[str, Any]:
        """Build shipper contact information"""
        contact = {
            "personName": fedex_config.person_name or "",
            "phoneNumber": fedex_config.phone_number or "",
            "companyName": fedex_config.company_name or "",
            "phoneExtension": ""  # Leave empty as requested
        }
        
        # Add email if available
        if hasattr(fedex_config, 'contact_email') and fedex_config.contact_email:
            contact["emailAddress"] = fedex_config.contact_email
        
        return contact
    
    def _build_shipper_address(self, fedex_config: FedexConfiguration) -> Dict[str, Any]:
        """Build shipper address"""
        address_lines = []
        if fedex_config.address and fedex_config.address.strip():
            address_lines.append(fedex_config.address.strip())
        
        # Ensure streetLines is not empty - will be caught by validation if empty
        if not address_lines:
            address_lines = [""]
        
        return {
            "streetLines": address_lines,
            "city": fedex_config.city or "",
            "stateOrProvinceCode": fedex_config.state_or_province_code or "",
            "postalCode": fedex_config.postal_code or "",
            "countryCode": fedex_config.country_code or ""
        }
    
    def _build_recipient_contact(self, receiver_address: Row) -> Dict[str, Any]:
        """Build recipient contact information"""
        # Build full name from firstname and lastname
        firstname = getattr(receiver_address, 'firstname', '') or ''
        lastname = getattr(receiver_address, 'lastname', '') or ''
        person_name = f"{firstname} {lastname}".strip()
        
        # Get company name
        company_name = getattr(receiver_address, 'company', '') or ''
        
        # Get phone
        phone = getattr(receiver_address, 'phone', '') or getattr(receiver_address, 'mobile_phone', '') or ''
        
        return {
            "personName": person_name or company_name or "Recipient",
            "phoneNumber": phone,
            "companyName": company_name
        }
    
    def _build_recipient_address(self, receiver_address: Row, country_iso: str) -> Dict[str, Any]:
        """Build recipient address"""
        address_lines = []
        address1 = getattr(receiver_address, 'address1', '') or ''
        address2 = getattr(receiver_address, 'address2', '') or ''
        
        if address1:
            address_lines.append(address1)
        if address2:
            address_lines.append(address2)
        
        # Get state/province
        state = getattr(receiver_address, 'state', '') or getattr(receiver_address, 'province_code', '') or ''
        
        # Ensure streetLines is not empty - at least one non-empty line required
        if not address_lines or not any(line.strip() for line in address_lines):
            address_lines = [""]  # Will be caught by validation
        
        return {
            "streetLines": address_lines,
            "city": getattr(receiver_address, 'city', '') or '',
            "stateOrProvinceCode": state,
            "postalCode": getattr(receiver_address, 'postcode', '') or '',
            "countryCode": country_iso.upper() if country_iso else ""
        }
    
    def _build_duties_payment(self, fedex_config: FedexConfiguration) -> Dict[str, Any]:
        """Build dutiesPayment structure for customsClearanceDetail"""
        # Build address from shipper config
        address_lines = []
        if fedex_config.address and fedex_config.address.strip():
            address_lines.append(fedex_config.address.strip())
        
        if not address_lines:
            address_lines = [""]
        
        responsible_party_address = {
            "streetLines": address_lines,
            "city": fedex_config.city or "",
            "stateOrProvinceCode": fedex_config.state_or_province_code or "",
            "postalCode": fedex_config.postal_code or "",
            "countryCode": fedex_config.country_code or "",
            "residential": False
        }
        
        # Build contact from shipper config
        responsible_party_contact = {
            "personName": fedex_config.person_name or "",
            "companyName": fedex_config.company_name or "",
            "phoneNumber": fedex_config.phone_number or "",
            "phoneExtension": ""  # Leave empty
        }
        
        # Add email if available
        if hasattr(fedex_config, 'contact_email') and fedex_config.contact_email:
            responsible_party_contact["emailAddress"] = fedex_config.contact_email
        
        # Build account number
        account_number_value = str(fedex_config.account_number) if fedex_config.account_number else ""
        
        # Build responsible party
        responsible_party = {
            "address": responsible_party_address,
            "contact": responsible_party_contact,
            "accountNumber": {
                "value": account_number_value
            }
            # Note: tins is NOT included as requested
        }
        
        # Build billing details (using account number and country code)
        billing_details = {
            "accountNumber": account_number_value,
            "accountNumberCountryCode": fedex_config.country_code or ""
        }
        
        # Get payment type from customs_charges or default to SENDER
        payment_type = fedex_config.customs_charges or "SENDER"
        
        # Build dutiesPayment
        duties_payment = {
            "payor": {
                "responsibleParty": responsible_party
            },
            "billingDetails": billing_details,
            "paymentType": payment_type
        }
        
        return duties_payment
    
    def _build_package_line_items(
        self,
        packages: List[Row],
        fedex_config: FedexConfiguration
    ) -> List[Dict[str, Any]]:
        """Build package line items from packages or use defaults"""
        items = []
        
        if packages:
            for package in packages:
                weight = float(getattr(package, 'weight', None) or fedex_config.default_weight or 1.0)
                
                item = {
                    "weight": {
                        "units": "KG",
                        "value": round(weight, 2)
                    }
                }
                
                # Add dimensions if available
                length = getattr(package, 'length', None) or fedex_config.package_depth
                width = getattr(package, 'width', None) or fedex_config.package_width
                height = getattr(package, 'height', None) or fedex_config.package_height
                
                if length and width and height:
                    item["dimensions"] = {
                        "length": int(length),
                        "width": int(width),
                        "height": int(height),
                        "units": "CM"
                    }
                
                items.append(item)
        else:
            # Default single package
            weight = float(fedex_config.default_weight or 1.0)
            items.append({
                "weight": {
                    "units": "KG",
                    "value": round(weight, 2)
                }
            })
        
        return items
    
    def _build_commodities(
        self,
        order_details: Optional[List],
        packages: List[Row],
        shipping_price_tax_incl: float,
        fedex_config: FedexConfiguration,
        receiver_country_iso: str
    ) -> List[Dict[str, Any]]:
        """
        Build commodities array for customsClearanceDetail
        
        If order_details are available, create one commodity per product.
        Otherwise, create one commodity per package.
        """
        commodities = []
        
        # Get country of manufacture (default to shipper country or IT)
        country_of_manufacture = fedex_config.country_code or "IT"
        
        # Calculate total weight and value for distribution
        total_weight = 0.0
        total_value = 0.0
        
        if order_details:
            # Use order details to create commodities
            for detail in order_details:
                product_name = getattr(detail, 'product_name', None) or 'Product'
                product_qty = int(getattr(detail, 'product_qty', None) or 1)
                product_price = float(getattr(detail, 'product_price', None) or 0.0)
                product_weight = float(getattr(detail, 'product_weight', None) or 0.0)
                
                # Calculate total value for this product
                product_total_value = product_price * product_qty
                total_value += product_total_value
                total_weight += product_weight * product_qty
        else:
            # Use packages to calculate total weight
            for package in packages:
                weight = float(getattr(package, 'weight', None) or fedex_config.default_weight or 1.0)
                total_weight += weight
            
            # If no order details, use shipping price as total value
            total_value = shipping_price_tax_incl
        
        # If total_weight is 0, use default
        if total_weight == 0:
            total_weight = float(fedex_config.default_weight or 1.0)
        
        # Build commodities
        if order_details:
            # Create one commodity per product
            for detail in order_details:
                product_name = getattr(detail, 'product_name', None) or 'Product'
                product_qty = int(getattr(detail, 'product_qty', None) or 1)
                product_price = float(getattr(detail, 'product_price', None) or 0.0)
                product_weight = float(getattr(detail, 'product_weight', None) or 0.0)
                
                # Calculate customs value proportionally
                if total_value > 0:
                    product_total_value = product_price * product_qty
                    customs_value_amount = (product_total_value / total_value) * shipping_price_tax_incl
                else:
                    # Distribute by weight if no value
                    if total_weight > 0:
                        product_total_weight = product_weight * product_qty
                        customs_value_amount = (product_total_weight / total_weight) * shipping_price_tax_incl
                    else:
                        customs_value_amount = shipping_price_tax_incl / len(order_details) if order_details else shipping_price_tax_incl
                
                commodity = {
                    "name": product_name[:50],  # Limit to 50 chars
                    "description": product_name[:200],  # Limit to 200 chars
                    "countryOfManufacture": country_of_manufacture,
                    "quantity": product_qty,
                    "quantityUnits": "Ea",
                    "weight": {
                        "units": "KG",
                        "value": round(product_weight * product_qty, 2)
                    },
                    "customsValue": {
                        "amount": round(customs_value_amount, 2),
                        "currency": "EUR"
                    },
                    "unitPrice": {
                        "amount": round(product_price, 2),
                        "currency": "EUR"
                    },
                    "purpose": "BUSINESS"
                }
                
                commodities.append(commodity)
        else:
            # Create one commodity per package or single commodity
            if packages:
                for idx, package in enumerate(packages):
                    weight = float(getattr(package, 'weight', None) or fedex_config.default_weight or 1.0)
                    
                    # Distribute customs value by weight
                    if total_weight > 0:
                        customs_value_amount = (weight / total_weight) * shipping_price_tax_incl
                    else:
                        customs_value_amount = shipping_price_tax_incl / len(packages) if packages else shipping_price_tax_incl
                    
                    commodity = {
                        "name": f"Package {idx + 1}",
                        "description": f"Shipment package {idx + 1}",
                        "countryOfManufacture": country_of_manufacture,
                        "quantity": 1,
                        "quantityUnits": "Ea",
                        "weight": {
                            "units": "KG",
                            "value": round(weight, 2)
                        },
                        "customsValue": {
                            "amount": round(customs_value_amount, 2),
                            "currency": "EUR"
                        },
                        "purpose": "BUSINESS"
                    }
                    
                    commodities.append(commodity)
            else:
                # Single default commodity
                weight = float(fedex_config.default_weight or 1.0)
                commodity = {
                    "name": "Shipment",
                    "description": "Shipment contents",
                    "countryOfManufacture": country_of_manufacture,
                    "quantity": 1,
                    "quantityUnits": "Ea",
                    "weight": {
                        "units": "KG",
                        "value": round(weight, 2)
                    },
                    "customsValue": {
                        "amount": round(shipping_price_tax_incl, 2),
                        "currency": "EUR"
                    },
                    "purpose": "BUSINESS"
                }
                
                commodities.append(commodity)
        
        return commodities
    
    def _build_label_specification(self, fedex_config: FedexConfiguration) -> Dict[str, Any]:
        """Build label specification from config"""
        return {
            "imageType": "PDF",
            "labelStockType": "PAPER_4X6",
            "labelRotation": "UPSIDE_DOWN"
        }
    
    def _validate_required_fields(self, payload: Dict[str, Any]) -> None:
        """
        Validate that all required fields are present in the FedEx payload
        
        Args:
            payload: FedEx API payload dict
            
        Raises:
            ValidationException: If any required field is missing
        """
        errors = []
        
        # Check top-level required fields
        if "labelResponseOptions" not in payload:
            errors.append("labelResponseOptions is required")
        
        if "accountNumber" not in payload:
            errors.append("accountNumber is required")
        elif "value" not in payload.get("accountNumber", {}):
            errors.append("accountNumber.value is required")
        
        if "requestedShipment" not in payload:
            errors.append("requestedShipment is required")
            return  # Can't validate nested fields if requestedShipment is missing
        
        rs = payload["requestedShipment"]
        
        # Check shipper
        if "shipper" not in rs:
            errors.append("requestedShipment.shipper is required")
        else:
            shipper = rs["shipper"]
            if "address" not in shipper:
                errors.append("requestedShipment.shipper.address is required")
            else:
                addr = shipper["address"]
                street_lines = addr.get("streetLines", [])
                if not street_lines or not any(line and line.strip() for line in street_lines):
                    errors.append("requestedShipment.shipper.address.streetLines is required and must contain at least one non-empty line")
                if "city" not in addr or not addr.get("city", "").strip():
                    errors.append("requestedShipment.shipper.address.city is required")
                if "countryCode" not in addr or not addr.get("countryCode", "").strip():
                    errors.append("requestedShipment.shipper.address.countryCode is required")
            
            if "contact" not in shipper:
                errors.append("requestedShipment.shipper.contact is required")
            elif "phoneNumber" not in shipper["contact"] or not shipper["contact"]["phoneNumber"]:
                errors.append("requestedShipment.shipper.contact.phoneNumber is required")
        
        # Check recipients
        if "recipients" not in rs or not rs["recipients"]:
            errors.append("requestedShipment.recipients is required")
        else:
            recipient = rs["recipients"][0]
            if "address" not in recipient:
                errors.append("requestedShipment.recipients[0].address is required")
            else:
                addr = recipient["address"]
                street_lines = addr.get("streetLines", [])
                if not street_lines or not any(line and line.strip() for line in street_lines):
                    errors.append("requestedShipment.recipients[0].address.streetLines is required and must contain at least one non-empty line")
                if "city" not in addr or not addr.get("city", "").strip():
                    errors.append("requestedShipment.recipients[0].address.city is required")
                if "countryCode" not in addr or not addr.get("countryCode", "").strip():
                    errors.append("requestedShipment.recipients[0].address.countryCode is required")
            
            if "contact" not in recipient:
                errors.append("requestedShipment.recipients[0].contact is required")
            elif "phoneNumber" not in recipient["contact"] or not recipient["contact"]["phoneNumber"]:
                errors.append("requestedShipment.recipients[0].contact.phoneNumber is required")
        
        # Check other required fields
        if "pickupType" not in rs or not rs["pickupType"]:
            errors.append("requestedShipment.pickupType is required")
        
        if "serviceType" not in rs or not rs["serviceType"]:
            errors.append("requestedShipment.serviceType is required")
        
        if "packagingType" not in rs or not rs["packagingType"]:
            errors.append("requestedShipment.packagingType is required")
        
        if "totalWeight" not in rs or rs["totalWeight"] is None or rs["totalWeight"] <= 0:
            errors.append("requestedShipment.totalWeight is required and must be greater than 0")
        
        if "shippingChargesPayment" not in rs:
            errors.append("requestedShipment.shippingChargesPayment is required")
        elif "paymentType" not in rs["shippingChargesPayment"]:
            errors.append("requestedShipment.shippingChargesPayment.paymentType is required")
        
        if "labelSpecification" not in rs:
            errors.append("requestedShipment.labelSpecification is required")
        else:
            label_spec = rs["labelSpecification"]
            if "labelStockType" not in label_spec or not label_spec["labelStockType"]:
                errors.append("requestedShipment.labelSpecification.labelStockType is required")
            if "imageType" not in label_spec or not label_spec["imageType"]:
                errors.append("requestedShipment.labelSpecification.imageType is required")
        
        if "requestedPackageLineItems" not in rs or not rs["requestedPackageLineItems"]:
            errors.append("requestedShipment.requestedPackageLineItems is required")
        else:
            for idx, item in enumerate(rs["requestedPackageLineItems"]):
                if "weight" not in item:
                    errors.append(f"requestedShipment.requestedPackageLineItems[{idx}].weight is required")
                else:
                    weight = item["weight"]
                    if "units" not in weight or not weight["units"]:
                        errors.append(f"requestedShipment.requestedPackageLineItems[{idx}].weight.units is required")
                    if "value" not in weight or weight["value"] is None:
                        errors.append(f"requestedShipment.requestedPackageLineItems[{idx}].weight.value is required")
        
        if errors:
            raise ValidationException(
                f"Missing required fields in FedEx payload: {', '.join(errors)}",
                details={"missing_fields": errors}
            )

