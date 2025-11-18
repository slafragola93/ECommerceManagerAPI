from typing import Dict, Any, List, Optional
import json
from decimal import Decimal
from sqlalchemy.engine import Row
from src.models.dhl_configuration import DhlConfiguration
from src.services.ecommerce.shipments.dhl_client import format_planned_shipping_date
# generate_shipment_reference rimosso - ora si usa order.internal_reference
import logging

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


class DhlMapper:
    """
    Mapper for converting Order data to DHL MyDHL API payload
    
    📦 LEGENDA MAPPING CAMPI - DOVE VANNO I DATI NEL JSON DHL
    
    ═══════════════════════════════════════════════════════════════════════════════
    📋 IDENTIFICAZIONE E CONTI
    ═══════════════════════════════════════════════════════════════════════════════
    Campo (DhlConfiguration)              → Dove va nel JSON DHL
    ─────────────────────────────────────────────────────────────────────────────
    shipper_account_number                → accounts[] → {"typeCode": "shipper", "number": "<valore>"}
                                            Conto addebitato per il trasporto. Obbligatorio se fatturi al mittente.
    
    payer_account_number                  → accounts[] → {"typeCode": "payer", "number": "<valore>"}
                                            Chi paga il trasporto se non è il mittente (terzo). Facoltativo.
    
    duties_account_number                 → accounts[] → {"typeCode": "duties", "number": "<valore>"}
                                            Conto per dazi e imposte (es. DDP). Usato se incoterm prevede oneri a carico mittente/payer.
    
    ═══════════════════════════════════════════════════════════════════════════════
    📍 MITTENTE (SHIPPER)
    ═══════════════════════════════════════════════════════════════════════════════
    company_name                          → customerDetails.shipperDetails.contactInformation.companyName
    reference_person                      → customerDetails.shipperDetails.contactInformation.fullName
    phone                                 → customerDetails.shipperDetails.contactInformation.phone
    email                                 → customerDetails.shipperDetails.contactInformation.email
    address                               → customerDetails.shipperDetails.postalAddress.addressLine1
    postal_code                           → customerDetails.shipperDetails.postalAddress.postalCode
    city                                  → customerDetails.shipperDetails.postalAddress.cityName
    country_code                          → customerDetails.shipperDetails.postalAddress.countryCode (ISO 2 lettere)
    province_code                         → customerDetails.shipperDetails.postalAddress.provinceCode (opzionale, es. province IT)
    
    ═══════════════════════════════════════════════════════════════════════════════
    📬 DESTINATARIO (RECEIVER)
    ═══════════════════════════════════════════════════════════════════════════════
    Sorgente: Address (from database)     → Dove va nel JSON DHL
    ─────────────────────────────────────────────────────────────────────────────
    address.company_name                  → customerDetails.receiverDetails.contactInformation.companyName
    address.first_name + last_name        → customerDetails.receiverDetails.contactInformation.fullName
    address.phone                         → customerDetails.receiverDetails.contactInformation.phone
    address.email                         → customerDetails.receiverDetails.contactInformation.email
    address.address1                 → customerDetails.receiverDetails.postalAddress.address1
    address.postal_code                   → customerDetails.receiverDetails.postalAddress.postalCode
    address.city                          → customerDetails.receiverDetails.postalAddress.cityName
    receiver_country_iso                  → customerDetails.receiverDetails.postalAddress.countryCode
    address.province_code                 → customerDetails.receiverDetails.postalAddress.provinceCode (opzionale)
    
    ═══════════════════════════════════════════════════════════════════════════════
    📦 SERVIZI E PRODOTTO
    ═══════════════════════════════════════════════════════════════════════════════
    default_product_code_domestic         → productCode (se shipper_country == receiver_country)
                                            Es. "N" per DHL Domestic Express
    
    default_product_code_international    → productCode (se shipper_country != receiver_country)
                                            Es. "P" per DHL Express Worldwide
    
    ═══════════════════════════════════════════════════════════════════════════════
    📄 ETICHETTE E DOCUMENTI
    ═══════════════════════════════════════════════════════════════════════════════
    label_format                          → outputImageProperties.encodingFormat ("pdf" o "zpl")
                                            Formato etichetta: PDF per stampanti laser, ZPL per stampanti termiche
    
    unit_of_measure                       → content.unitOfMeasurement ("metric" o "imperial")
                                            Sistema di misura: Metric = kg/cm, Imperial = lbs/in
    
    ═══════════════════════════════════════════════════════════════════════════════
    📦 CONTENUTO E DOGANA
    ═══════════════════════════════════════════════════════════════════════════════
    goods_description                     → content.description
                                            Descrizione merce. Default: "General merchandise"
    
    default_is_customs_declarable         → content.isCustomsDeclarable
                                            Se true E spedizione internazionale, allega documenti doganali
    
    default_incoterm                      → content.incoterm (solo se isCustomsDeclarable = true)
                                            Es. "DAP", "DDP", "EXW". Default: "DAP"
    
    tax_id                                → Usato per VAT/EORI in shipperDetails/receiverDetails (se necessario)
    
    ═══════════════════════════════════════════════════════════════════════════════
    📦 PACCHI E DIMENSIONI
    ═══════════════════════════════════════════════════════════════════════════════
    Sorgente: OrderPackage o fallback config → Dove va nel JSON DHL
    ─────────────────────────────────────────────────────────────────────────────
    package.weight (o default_weight)     → content.packages[].weight
    package.length (o package_height)     → content.packages[].dimensions.length
    package.width (o package_width)       → content.packages[].dimensions.width
    package.height (o package_depth)      → content.packages[].dimensions.height
    
    ═══════════════════════════════════════════════════════════════════════════════
    🚚 RITIRO (PICKUP)
    ═══════════════════════════════════════════════════════════════════════════════
    pickup_is_requested                   → pickup.isRequested
                                            Se true, DHL pianifica il ritiro presso il mittente
    
    pickup_close_time                     → pickup.closeTime (formato "HH:mm", es. "18:00")
                                            Orario di chiusura sede per il ritiro
    
    pickup_location                       → pickup.location
                                            Luogo specifico dove effettuare il ritiro (es. "Reception", "Warehouse")
    
    ═══════════════════════════════════════════════════════════════════════════════
    💰 COD (CASH ON DELIVERY) - CONTRASSEGNO
    ═══════════════════════════════════════════════════════════════════════════════
    cod_enabled                           → (futuro) valueAddedServices[] → {"serviceCode": "COD"}
    cod_currency                          → (futuro) valueAddedServices[COD].value.currency
                                            NOTA: Non ancora implementato nel mapper. Da aggiungere se richiesto.
    
    ═══════════════════════════════════════════════════════════════════════════════
    🔖 RIFERIMENTI
    ═══════════════════════════════════════════════════════════════════════════════
    order_data.id_order                   → customerReferences[] → {"typeCode": "CU", "value": "<id_order>"}
                                            Riferimento cliente per tracciare l'ordine
    
    ═══════════════════════════════════════════════════════════════════════════════
    """
    
    def build_shipment_request(
        self,
        order_data: Row,
        dhl_config: DhlConfiguration,
        receiver_address: Row,
        receiver_country_iso: str,
        packages: List[Row],
        reference: str
    ) -> Dict[str, Any]:
        """
        Build DHL shipment request payload from order and configuration data
        
        Args:
            order_data: Order row with shipment data
            dhl_config: DHL configuration
            receiver_address: Receiver address row
            receiver_country_iso: Receiver country ISO code
            packages: List of package rows for the order
            
        Returns:
            DHL API payload dict
        """
        # Determine if international shipment
        is_international = self._is_international_shipment(
            dhl_config.country_code, 
            receiver_country_iso
        )
        
        # Select product code based on domestic/international
        product_code = (
            dhl_config.default_product_code_international 
            if is_international 
            else dhl_config.default_product_code_domestic
        )
        
        # Use provided internal_reference from order 
        internal_reference = reference 
        
        # Build payload
        payload = {
            "productCode": product_code,
            "customerReferences": [
                {
                    "typeCode": "CU",
                    "value": internal_reference
                }
            ],
            "plannedShippingDateAndTime": format_planned_shipping_date(),
            "pickup": {
                "isRequested": dhl_config.pickup_is_requested or False
            },
            "outputImageProperties": {
                "splitTransportAndWaybillDocLabels": True,
                "encodingFormat": dhl_config.label_format.value.lower(),
                "imageOptions": [
                    {
                        "templateName": "ECOM26_84_001",
                        "typeCode": "label"
                    }
                ]
            },
            "getRateEstimates": False,
            "customerDetails": {
                "shipperDetails": self._build_shipper(dhl_config),
                "receiverDetails": self._build_receiver(receiver_address, receiver_country_iso)
            },
            "content": self._build_content(dhl_config, packages, is_international, receiver_country_iso, internal_reference)
        }
        
        # Add pickup details if requested
        if dhl_config.pickup_is_requested:
            payload["pickup"]["closeTime"] = dhl_config.pickup_close_time
            payload["pickup"]["location"] = dhl_config.pickup_location
            payload["pickup"]["pickupDetails"] = payload["customerDetails"]["shipperDetails"]
        
        # Add accounts
        accounts = [{"typeCode": "shipper", "number": dhl_config.shipper_account_number}]
        if dhl_config.duties_account_number:
            accounts.append({"typeCode": "duties", "number": dhl_config.duties_account_number})
        if dhl_config.payer_account_number:
            accounts.append({"typeCode": "payer", "number": dhl_config.payer_account_number})
        
        payload["accounts"] = accounts
        
        # Debug: Log complete payload
        logger.info(f"Built DHL payload for order {order_data.id_order}, international: {is_international}")
        logger.info(f"DHL Mapper Payload: {json.dumps(payload, indent=2, ensure_ascii=False, cls=DecimalEncoder)}")
        
        return payload
    
    def _build_shipper(self, config: DhlConfiguration) -> Dict[str, Any]:
        """Build shipper details from DHL configuration"""
        shipper = {
            "postalAddress": {
                "addressLine1": config.address,
                "postalCode": config.postal_code,
                "cityName": config.city,
                "countryCode": config.country_code
            },
            "contactInformation": {
                "companyName": config.company_name,
                "fullName": config.reference_person,
                "phone": config.phone,
                "email": config.email
            },
            "typeCode": "direct_consumer"
        }
        
        # Add province code if available
        if config.province_code:
            shipper["postalAddress"]["provinceCode"] = config.province_code
        
        return shipper
    
    def _build_receiver(self, address: Row, country_iso: str) -> Dict[str, Any]:
        """Build receiver details from address data"""
        receiver = {
            "postalAddress": {
                "addressLine1": address.address1,
                "postalCode": address.postcode,
                "cityName": address.city,
                "countryCode": country_iso
            },
            "contactInformation": {
                "companyName": address.company   or f"{address.firstname or ''} {address.lastname or ''}".strip(),
                "fullName": f"{address.firstname or ''} {address.lastname or ''}".strip(),
                "phone": address.phone or "0000000000",
                "email": address.email or "noreply@example.com"
            },
            "typeCode": "direct_consumer"
        }
        
        # Add province code if available
        if hasattr(address, 'province_code') and address.province_code:
            receiver["postalAddress"]["provinceCode"] = address.province_code
        
        return receiver
    
    def _build_content(
        self, 
        config: DhlConfiguration, 
        packages: List[Row], 
        is_international: bool,
        country_iso: str,
        internal_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build content details for shipment"""
        content = {
            "unitOfMeasurement": config.unit_of_measure.value.lower(),
            "isCustomsDeclarable": is_international and config.default_is_customs_declarable,
            "description": config.goods_description or "General merchandise",
            "packages": self._build_packages(config, packages, country_iso, internal_reference)
        }
        
        # Add incoterm for international shipments
        if content["isCustomsDeclarable"] and config.default_incoterm:
            content["incoterm"] = config.default_incoterm
        elif content["isCustomsDeclarable"] and not config.default_incoterm:
            # Default incoterm for international shipments
            content["incoterm"] = "DAP"
        
        return content
    
    def _build_packages(self, config: DhlConfiguration, packages: List[Row], country_iso: str, internal_reference: Optional[str] = None) -> List[Dict[str, Any]]:
        """Build package details from order packages or use defaults"""
        if not packages:
            # Use default package from configuration
            return [{
                "typeCode": "2BP",
                "weight": float(config.default_weight),
                "dimensions": {
                    "length": config.package_height,
                    "width": config.package_width,
                    "height": config.package_depth
                },
                "customerReferences": [
                    {
                        "typeCode": "CU",
                        "value": internal_reference
                    }
                ],
                "description": config.goods_description or "General merchandise",
                "labelDescription": config.goods_description or "General merchandise",
            }]
        
        # Build packages from order data
        dhl_packages = []
        for i, package in enumerate(packages, 1):
            # Use package dimensions if available, otherwise fallback to config defaults
            weight = float(package.weight) if hasattr(package, 'weight') and package.weight else float(config.default_weight)
            length = package.length if hasattr(package, 'length') and package.length else config.package_height
            width = package.width if hasattr(package, 'width') and package.width else config.package_width
            height = package.height if hasattr(package, 'height') and package.height else config.package_depth
            
            dhl_package = {
                "weight": weight,
                "dimensions": {
                    "length": length,
                    "width": width,
                    "height": height
                },
                "customerReferences": [
                    {
                        "typeCode": "CU",
                        "value": internal_reference
                    }
                ]
            }
            
            dhl_packages.append(dhl_package)
        
        return dhl_packages
    
    def _is_international_shipment(self, shipper_country: str, receiver_country: str) -> bool:
        """
        Determine if shipment is international based on country codes
        
        Args:
            shipper_country: Shipper country code (2-letter ISO)
            receiver_country: Receiver country code (2-letter ISO)
            
        Returns:
            True if international shipment, False if domestic
        """
        return shipper_country.upper() != receiver_country.upper()
