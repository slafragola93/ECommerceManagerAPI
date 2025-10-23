import os
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from src.core.settings import get_cache_settings
from src.services.interfaces.dhl_shipment_service_interface import IDhlShipmentService
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.dhl_configuration_repository_interface import IDhlConfigurationRepository
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.repository.interfaces.shipment_request_repository_interface import IShipmentRequestRepository
from src.services.ecommerce.shipments.dhl_client import DhlClient, generate_message_reference
from src.services.ecommerce.shipments.dhl_mapper import DhlMapper
from src.models.shipment_request import ShipmentRequest, EnvironmentEnum
from src.models.shipment_document import ShipmentDocument

logger = logging.getLogger(__name__)


class DhlShipmentService(IDhlShipmentService):
    """DHL Shipment service for creating shipments and managing documents"""
    
    def __init__(
        self,
        order_repository: IOrderRepository,
        shipping_repository: IShippingRepository,
        carrier_api_repository: IApiCarrierRepository,
        dhl_config_repository: IDhlConfigurationRepository,
        address_repository: IAddressRepository,
        country_repository: ICountryRepository,
        order_package_repository: IOrderPackageRepository,
        shipment_request_repository: IShipmentRequestRepository,
        dhl_client: DhlClient,
        dhl_mapper: DhlMapper
    ):
        self.order_repository = order_repository
        self.shipping_repository = shipping_repository
        self.carrier_api_repository = carrier_api_repository
        self.dhl_config_repository = dhl_config_repository
        self.address_repository = address_repository
        self.country_repository = country_repository
        self.order_package_repository = order_package_repository
        self.shipment_request_repository = shipment_request_repository
        self.dhl_client = dhl_client
        self.dhl_mapper = dhl_mapper
        self.settings = get_cache_settings()
    
    async def create_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Creazione spedizione DHL per ordine
        
        Args:
            order_id: ID ordine per creare spedizione
            
        Returns:
            Dict con dettagli spedizione (awb, label_path, estimated_delivery, etc.)
        """
        try:
            # 1. Recupero informazioni Ordine
            order_data = self.order_repository.get_shipment_data(order_id)
            
            # 2. Recupero info di spedizione per poi recuperare id_carrier_api
            shipping_info = self.shipping_repository.get_carrier_info(order_data.id_shipping)
            carrier_api_id = shipping_info.id_carrier_api
            
            # 3. Recupero la configurazione DHL
            dhl_config = self.dhl_config_repository.get_by_carrier_api_id(carrier_api_id)
            if not dhl_config:
                raise ValueError(f"DHL configuration not found for carrier_api_id {carrier_api_id}")
            
            # 4. Recupero credenziali DHL
            credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
            
            # 5. Recupero indirizzo di consegna e paese
            receiver_address = self.address_repository.get_delivery_data(order_data.id_address_delivery)
            receiver_country_iso = self.country_repository.get_iso_code(receiver_address.id_country)
            
            # 6. Recupero dimensioni dei colli
            packages = self.order_package_repository.get_dimensions_by_order(order_id)
            
            # 7. Genero reference per idempotenza
            message_ref = generate_message_reference()
            
            # 8. Controllo idempotenza se audit abilitato
            if self.settings.shipment_audit_enabled:
                existing_request = self.shipment_request_repository.get_by_message_reference(message_ref)
                if existing_request:
                    logger.info(f"Found existing shipment request for message_ref {message_ref}")
                    return {
                        "awb": existing_request.awb,
                        "label_path": None,  # Would need to retrieve from documents
                        "estimated_delivery": None,
                        "pickup_details": None,
                        "tracking_url": None
                    }
            
            # 9. Costruzione DHL payload
            dhl_payload = self.dhl_mapper.build_shipment_request(
                order_data=order_data,
                dhl_config=dhl_config,
                receiver_address=receiver_address,
                receiver_country_iso=receiver_country_iso,
                packages=packages
            )
            
            # 10. Chiama a API DHL
            logger.info(f"Creating DHL shipment for order {order_id}")
            dhl_response = await self.dhl_client.create_shipment(
                payload=dhl_payload,
                credentials=credentials,
                message_ref=message_ref
            )
            
            # 11. Estrazione AWB e documenti
            awb = dhl_response.get("shipmentTrackingNumber")
            documents = dhl_response.get("documents", [])
            
            # 12. Salva PDF
            saved_documents = []
            if documents:
                saved_documents = await self._save_documents(awb, documents, order_id, carrier_api_id)
            
            # 13. Aggiornamento tracking
            if awb:
                self.shipping_repository.update_tracking(order_data.id_shipping, awb)
            
            # 14. Salva audit se abilitato
            if self.settings.shipment_audit_enabled:
                self._save_audit(
                    order_id=order_id,
                    carrier_api_id=carrier_api_id,
                    request=dhl_payload,
                    response=dhl_response,
                    awb=awb,
                    environment=EnvironmentEnum.SANDBOX if credentials.use_sandbox else EnvironmentEnum.PRODUCTION,
                    message_ref=message_ref
                )
            
            # 15. Estrazione dati risposta
            estimated_delivery = None
            pickup_details = None
            tracking_url = dhl_response.get("trackingUrl")
            
            if "estimatedDeliveryDate" in dhl_response:
                estimated_delivery = dhl_response["estimatedDeliveryDate"].get("estimatedDeliveryDate")
            
            if "shipmentDetails" in dhl_response and dhl_response["shipmentDetails"]:
                pickup_details = dhl_response["shipmentDetails"][0].get("pickupDetails")
            
            return {
                "awb": awb,
                "label_path": saved_documents[0]["file_path"] if saved_documents else None,
                "estimated_delivery": estimated_delivery,
                "pickup_details": pickup_details,
                "tracking_url": tracking_url
            }
            
        except Exception as e:
            logger.error(f"Error creating DHL shipment for order {order_id}: {str(e)}")
            raise
    
    async def _save_documents(
        self, 
        awb: str, 
        documents: list, 
        order_id: int, 
        carrier_api_id: int
    ) -> list[Dict[str, Any]]:
        """
        Salva documenti DHL (PDF) sul filesystem e nel database
        
        Args:
            awb: Numero Air Waybill
            documents: Lista di documenti DHL
            order_id: Order ID
            carrier_api_id: Carrier API ID
            
        Returns:
            Lista di metadati documenti salvati
        """
        saved_documents = []
        
        for doc in documents:
            try:
                # Decodifica base64
                content_b64 = doc.get("content", "")
                if not content_b64:
                    continue
                
                content_bytes = base64.b64decode(content_b64)
                
                # Genero file path con struttura anno/mese
                now = datetime.now()
                year = now.year
                month = now.month
                
                # Creazione directory: /media/shipments/{year}/{month}/{AWB}/
                base_dir = Path("media") / "shipments" / str(year) / str(month).zfill(2) / awb
                base_dir.mkdir(parents=True, exist_ok=True)
                
                # Genero nome file
                doc_type = doc.get("typeCode", "document")
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                filename = f"{doc_type}_{timestamp}.pdf"
                file_path = base_dir / filename
                
                # Salvo file
                with open(file_path, "wb") as f:
                    f.write(content_bytes)
                
                # Calcolo metadati file
                file_size = len(content_bytes)
                sha256_hash = hashlib.sha256(content_bytes).hexdigest()
                
                # Salvo a database
                document = ShipmentDocument(
                    awb=awb,
                    type_code=doc_type,
                    file_path=str(file_path),
                    mime_type="application/pdf",
                    sha256_hash=sha256_hash,
                    size_bytes=file_size,
                    created_at=now,
                    expires_at=now + timedelta(days=365)  # 1 year TTL
                )
                
                # Aggiungo a sessione e salvo
                self.shipment_request_repository.session.add(document)
                self.shipment_request_repository.session.commit()
                
                saved_documents.append({
                    "type_code": doc_type,
                    "file_path": str(file_path),
                    "size_bytes": file_size,
                    "sha256_hash": sha256_hash
                })
                
                logger.info(f"Saved DHL document {doc_type} for AWB {awb}: {file_path}")
                
            except Exception as e:
                logger.error(f"Error saving document for AWB {awb}: {str(e)}")
                continue
        
        return saved_documents
    
    def _save_audit(
        self,
        order_id: int,
        carrier_api_id: int,
        request: Dict[str, Any],
        response: Dict[str, Any],
        awb: str,
        environment: EnvironmentEnum,
        message_ref: str
    ) -> None:
        """Salva record audit per richiesta spedizione"""
        try:
            # Redact sensitive data
            redacted_request = self._redact_sensitive_data(request)
            redacted_response = self._redact_sensitive_data(response)
            
            # Truncate JSON if too large
            max_size_kb = self.settings.shipment_audit_max_json_size_kb
            redacted_request_str = str(redacted_request)
            redacted_response_str = str(redacted_response)
            
            if len(redacted_request_str) > max_size_kb * 1024:
                redacted_request_str = redacted_request_str[:max_size_kb * 1024] + "... [TRUNCATED]"
            
            if len(redacted_response_str) > max_size_kb * 1024:
                redacted_response_str = redacted_response_str[:max_size_kb * 1024] + "... [TRUNCATED]"
            
            # Create audit record
            now = datetime.utcnow()
            expires_at = now + timedelta(days=self.settings.shipment_audit_ttl_days)
            
            audit_record = ShipmentRequest(
                id_order=order_id,
                id_carrier_api=carrier_api_id,
                awb=awb,
                message_reference=message_ref,
                request_json_redacted=redacted_request_str,
                response_json_redacted=redacted_response_str,
                environment=environment,
                status_code=200,  # Assuming success
                created_at=now,
                expires_at=expires_at
            )
            
            self.shipment_request_repository.session.add(audit_record)
            self.shipment_request_repository.session.commit()
            
            logger.info(f"Saved audit record for order {order_id}, AWB {awb}")
            
        except Exception as e:
            logger.error(f"Error saving audit record: {str(e)}")
            # Don't raise exception to avoid breaking the main flow
    
    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Riduzione dati sensibili da richiesta/risposta per audit"""
        if not isinstance(data, dict):
            return data
        
        redacted = data.copy()
        
        # Redact email addresses
        if "email" in redacted:
            redacted["email"] = "[REDACTED]"
        
        # Redact phone numbers
        if "phone" in redacted:
            redacted["phone"] = "[REDACTED]"
        
        # Redact addresses
        if "address" in redacted:
            redacted["address"] = "[REDACTED]"
        
        # Redact customer details recursively
        if "customerDetails" in redacted:
            customer_details = redacted["customerDetails"]
            if isinstance(customer_details, dict):
                if "shipperDetails" in customer_details:
                    shipper = customer_details["shipperDetails"]
                    if isinstance(shipper, dict) and "contactInformation" in shipper:
                        contact = shipper["contactInformation"]
                        if isinstance(contact, dict):
                            contact["email"] = "[REDACTED]"
                            contact["phone"] = "[REDACTED]"
                
                if "receiverDetails" in customer_details:
                    receiver = customer_details["receiverDetails"]
                    if isinstance(receiver, dict) and "contactInformation" in receiver:
                        contact = receiver["contactInformation"]
                        if isinstance(contact, dict):
                            contact["email"] = "[REDACTED]"
                            contact["phone"] = "[REDACTED]"
        
        return redacted
