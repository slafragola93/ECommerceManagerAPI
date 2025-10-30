import os
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import logging
from fastapi import HTTPException

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
# generate_shipment_reference rimosso - ora si usa order.internal_reference
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
            
            # 8. Recupero internal_reference dell'ordine
            internal_reference = order_data.internal_reference
            
            # 10. Controllo idempotenza se audit abilitato
            if self.settings.shipment_audit_enabled:
                existing_request = self.shipment_request_repository.get_by_message_reference(message_ref)
                if existing_request:
                    logger.info(f"Found existing shipment request for message_ref {message_ref}")
                    return {
                        "awb": existing_request.awb
                    }
            
            # 11. Costruzione DHL payload con internal_reference dell'ordine
            dhl_payload = self.dhl_mapper.build_shipment_request(
                order_data=order_data,
                dhl_config=dhl_config,
                receiver_address=receiver_address,
                receiver_country_iso=receiver_country_iso,
                packages=packages,
                reference=internal_reference
            )
            
            # 12. Chiama a API DHL
            logger.info(f"Creating DHL shipment for order {order_id}")
            try:
                dhl_response = await self.dhl_client.create_shipment(
                    payload=dhl_payload,
                    credentials=credentials,
                    dhl_config=dhl_config,
                    message_ref=message_ref
                )
            except ValueError as e:
                # Handle DHL validation errors (400, 422)
                logger.error(f"❌ DHL Validation Error for order {order_id}: {str(e)}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"DHL Validation Error: {str(e)}"
                )
            except RuntimeError as e:
                # Handle DHL server errors (500)
                logger.error(f"❌ DHL Server Error for order {order_id}: {str(e)}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"DHL Server Error: {str(e)}"
                )
            except Exception as e:
                # Handle other DHL API errors
                logger.error(f"❌ DHL API Error for order {order_id}: {str(e)}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"DHL API Error: {str(e)}"
                )
            
            # 13. Estrazione AWB e documenti
            awb = dhl_response.get("shipmentTrackingNumber")
            documents = dhl_response.get("documents", [])
            
            # 14. Salva PDF
            saved_documents = []
            if documents:
                saved_documents = await self._save_documents(
                    awb=awb, 
                    documents=documents, 
                    order_id=order_id, 
                    carrier_api_id=carrier_api_id
                )
            
            # 15. Aggiornamento tracking e stato (2 = Presa In Carico)
            if awb:
                try:
                    self.shipping_repository.update_tracking_and_state(order_data.id_shipping, awb, 2)
                except Exception:
                    # fallback: almeno salva il tracking
                    self.shipping_repository.update_tracking(order_data.id_shipping, awb)
            
            # 16. Salva audit se abilitato
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
            
            # 14. Aggiorno stato spedizione e tracking se AWB è valido
            if awb:
                try:
                    # Recupero solo id_shipping dall'ordine (query ottimizzata)
                    from sqlalchemy import select
                    from src.models.order import Order
                    
                    stmt = select(Order.id_shipping).where(Order.id_order == order_id)
                    result = self.shipment_request_repository._session.execute(stmt)
                    id_shipping = result.scalar_one_or_none()
                    
                    if id_shipping:
                        # Recupero la spedizione tramite id_shipping
                        shipping = self.shipping_repository.get_by_id(id_shipping)
                        if shipping:
                            # Aggiorno sempre il tracking con il nuovo AWB
                            shipping.tracking = awb
                            
                            # Aggiorno lo stato solo se è in stato 1
                            if shipping.id_shipping_state == 1:
                                shipping.id_shipping_state = 2  # Cambia a "Tracking Assegnato"
                                logger.info(f"Spedizione {shipping.id_shipping} aggiornata allo stato 2 (Tracking Assegnato)")
                            
                            # Salvo le modifiche
                            self.shipping_repository.update(shipping)
                            logger.info(f"Tracking spedizione {shipping.id_shipping} aggiornato a {awb}")
                        else:
                            logger.warning(f"Nessuna spedizione trovata per l'ordine {order_id}")
                    else:
                        logger.warning(f"Nessun id_shipping trovato per l'ordine {order_id}")
                except Exception as e:
                    logger.error(f"Impossibile aggiornare la spedizione per l'ordine {order_id}: {str(e)}")
                    # Non sollevo eccezione per non bloccare la creazione spedizione
            
            return {
                "awb": awb
            }
            
        except Exception as e:
            logger.error(f"Error creating DHL shipment for order {order_id}: {str(e)}")
            raise
    
    async def _save_documents(
        self, 
        awb: str, 
        order_id: int, 
        carrier_api_id: int,
        documents: list
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
        # 1. Cleanup documenti esistenti per questo ordine
        self._cleanup_old_documents(order_id)
        
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
                
                # Creazione directory: /media/shipments/{year}/{month}/{id_order}/
                base_dir = Path("media") / "shipments" / str(year) / str(month).zfill(2) / str(order_id)
                base_dir.mkdir(parents=True, exist_ok=True)
                
                # Genero nome file con AWB incluso
                doc_type = doc.get("typeCode", "document")
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                filename = f"{doc_type}_{awb}_{timestamp}.pdf"
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
                    order_id=order_id,
                    carrier_api_id=carrier_api_id,
                    type_code=doc_type,
                    file_path=str(file_path),
                    mime_type="application/pdf",
                    sha256_hash=sha256_hash,
                    size_bytes=file_size,
                    created_at=now,
                    expires_at=now + timedelta(days=365)  # 1 year TTL
                )
                
                # Aggiungo a sessione e salvo
                self.shipment_request_repository._session.add(document)
                self.shipment_request_repository._session.commit()
                
                saved_documents.append({
                    "type_code": doc_type,
                    "file_path": str(file_path),
                    "size_bytes": file_size,
                    "sha256_hash": sha256_hash,
                    "order_id": order_id,
                    "carrier_api_id": carrier_api_id
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
    
    def _cleanup_old_documents(self, order_id: int) -> None:
        """
        Elimina documenti esistenti per un ordine prima di salvare nuovi documenti
        
        Args:
            order_id: ID dell'ordine
        """
        try:
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            import shutil
            from pathlib import Path
            
            # Recupera tutti i documenti esistenti per l'ordine
            document_repo = ShipmentDocumentRepository(self.shipment_request_repository._session)
            existing_documents = document_repo.get_by_order_id(order_id)
            
            if not existing_documents:
                return
            
            # Raggruppa documenti per cartella per eliminare una volta sola
            folders_to_delete = set()
            
            for doc in existing_documents:
                if doc.file_path:
                    try:
                        # Estrai la cartella dell'ordine dal file_path
                        # Es: media/shipments/2025/10/123/label_xxx.pdf -> media/shipments/2025/10/123
                        file_path = Path(doc.file_path)
                        order_folder = file_path.parent  # cartella {id_order}
                        folders_to_delete.add(str(order_folder))
                        
                        # Elimina il record dal database
                        document_repo.delete_by_id(doc.id)
                        
                    except Exception as e:
                        logger.warning(f"Errore nel processare il documento {doc.id}: {str(e)}")
            
            # Elimina le cartelle fisiche
            for folder_path in folders_to_delete:
                try:
                    if Path(folder_path).exists():
                        shutil.rmtree(folder_path)
                except Exception as e:
                    logger.error(f"Errore nell'eliminare la cartella {folder_path}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Errore durante la pulizia per l'ordine {order_id}: {str(e)}")
            # Non sollevo eccezione per non bloccare la creazione spedizione
    
    async def get_label_file_path(self, awb: str) -> Optional[str]:
        """
        Recupera il percorso del file PDF della label per un AWB
        
        Args:
            awb: Air Waybill number
            
        Returns:
            Percorso del file PDF o None se non trovato
        """
        try:
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            
            # Cerca il documento per AWB
            document_repo = ShipmentDocumentRepository(self.shipment_request_repository._session)
            documents = document_repo.get_by_awb(awb)
            
            if not documents:
                logger.warning(f"Nessun documento trovato per AWB: {awb}")
                return None
            
            # Cerca il documento di tipo "label" o altri tipi di documenti DHL
            for doc in documents:
                if doc.type_code in ["label", "LABEL", "shipping-label", "shipping_label"] and doc.file_path:
                    return doc.file_path
            
            # Se non trova "label", prova con qualsiasi documento PDF
            for doc in documents:
                if doc.file_path and doc.file_path.endswith('.pdf'):
                    return doc.file_path
            
            logger.warning(f"Nessun documento label trovato per AWB: {awb}")
            return None
            
        except Exception as e:
            logger.error(f"Errore nel recuperare il percorso del file per AWB {awb}: {str(e)}")
            return None
