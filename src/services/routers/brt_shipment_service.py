import os
import hashlib
import base64
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from src.core.settings import get_cache_settings
from src.core.exceptions import NotFoundException, BusinessRuleException, InfrastructureException
from src.services.interfaces.brt_shipment_service_interface import IBrtShipmentService
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.brt_configuration_repository_interface import IBrtConfigurationRepository
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.services.ecommerce.shipments.brt_client import BrtClient
from src.services.ecommerce.shipments.brt_mapper import BrtMapper
from src.models.shipment_document import ShipmentDocument

logger = logging.getLogger(__name__)


class BrtShipmentService(IBrtShipmentService):
    """BRT Shipment service for creating shipments and managing documents"""
    
    def __init__(
        self,
        order_repository: IOrderRepository,
        shipping_repository: IShippingRepository,
        carrier_api_repository: IApiCarrierRepository,
        brt_config_repository: IBrtConfigurationRepository,
        address_repository: IAddressRepository,
        country_repository: ICountryRepository,
        order_package_repository: IOrderPackageRepository,
        brt_client: BrtClient,
        brt_mapper: BrtMapper
    ):
        self.order_repository = order_repository
        self.shipping_repository = shipping_repository
        self.carrier_api_repository = carrier_api_repository
        self.brt_config_repository = brt_config_repository
        self.address_repository = address_repository
        self.country_repository = country_repository
        self.order_package_repository = order_package_repository
        self.brt_client = brt_client
        self.brt_mapper = brt_mapper
        self.settings = get_cache_settings()
    
    async def create_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Creazione spedizione BRT per ordine
        
        Args:
            order_id: ID ordine per creare spedizione
            
        Returns:
            Dict con dettagli spedizione (awb)
        """
        # 1. Recupero informazioni Ordine
        order_data = self.order_repository.get_shipment_data(order_id)
        
        # 2. Recupero info di spedizione per poi recuperare id_carrier_api
        shipping_info = self.shipping_repository.get_carrier_info(order_data.id_shipping)
        carrier_api_id = shipping_info.id_carrier_api
        
        # 3. Recupero la configurazione BRT
        brt_config = self.brt_config_repository.get_by_carrier_api_id(carrier_api_id)
        if not brt_config:
            raise NotFoundException("BrtConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id})
        
        # 4. Recupero credenziali (per consistenza con DHL, ma BRT usa brt_config)
        credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
        
        # 5. Recupero indirizzo di consegna
        receiver_address = self.address_repository.get_delivery_data(order_data.id_address_delivery)
        print(f"order_data.id_address_delivery: {order_data.id_address_delivery}")
        print(f"Receiver address: {receiver_address}")
        # 6. Recupero codice ISO paese destinatario
        print(f"id country: {receiver_address.id_country}")
        receiver_country_iso = self.country_repository.get_iso_code(receiver_address.id_country)
        print(f"Receiver country ISO: {receiver_country_iso}")
        # 7. Recupero dimensioni dei colli
        packages = self.order_package_repository.get_dimensions_by_order(order_id)
        
        # 8. Recupero internal_reference dell'ordine
        internal_reference = order_data.internal_reference or str(order_id)
        
        # 9. STEP 1: Routing per normalizzare indirizzo
        logger.info(f"BRT Routing for order {order_id}")
        routing_payload = self.brt_mapper.build_routing_request(
            brt_config=brt_config,
            receiver_address=receiver_address,
            packages=packages,
            receiver_country_iso=receiver_country_iso
        )
        
        routing_response = await self.brt_client.routing(
            payload=routing_payload,
            credentials=credentials,
            brt_config=brt_config
        )
        # Extract normalized address from routing response
        normalized_address = routing_response.get("routingData") or {}
        
        # 10. STEP 2: Create shipment
        logger.info(f"Creating BRT shipment for order {order_id}")
        create_payload = self.brt_mapper.build_create_request(
            brt_config=brt_config,
            receiver_address=receiver_address,
            packages=packages,
            reference=internal_reference,
            receiver_country_iso=receiver_country_iso,
            normalized_address=normalized_address
        )
        
        create_response = await self.brt_client.create_shipment(
            payload=create_payload,
            credentials=credentials,
            brt_config=brt_config
        )
        
        # 11. Estrazione tracking e label
        tracking = self.brt_mapper.extract_tracking_from_response(create_response)
        logger.info(f"Extracted tracking for order {order_id}: {tracking}")
        label_b64 = self.brt_mapper.extract_label_from_response(create_response)
        logger.info(f"Extracted label (base64 length) for order {order_id}: {len(label_b64) if label_b64 else 0}")
        
        if not label_b64:
            # Try to get label from confirm response if autoconfirm is enabled
            # For now, we'll check if autoconfirm is needed
            # Note: BRT config doesn't have autoconfirm field yet, so we skip for now
            pass
        
        # 12. STEP 3: Confirm shipment if needed (autoconfirm)
        # Note: BRT config doesn't have autoconfirm field in model yet
        # For now, we'll skip auto-confirm. Can be added later.
        confirm_response = None
        numeric_ref = create_payload["createData"]["numericSenderReference"]
        alphanumeric_ref = create_payload["createData"]["alphanumericSenderReference"]
        
        # 13. Salva PDF label
        if label_b64:
            await self._save_documents(
                awb=tracking or f"BRT_{order_id}",
                label_b64=label_b64,
                order_id=order_id,
                carrier_api_id=carrier_api_id
            )
            
        # 13. Aggiornamento tracking e stato (2 = Presa In Carico)
        if tracking:
            self.shipping_repository.update_tracking_and_state(order_data.id_shipping, tracking, 2)
        
        return {
            "awb": tracking or ""
        }
            
    
    async def _save_documents(
        self,
        awb: str,
        label_b64: str,
        order_id: int,
        carrier_api_id: int
    ) -> Dict[str, Any]:
        """
        Salva documenti BRT (PDF) sul filesystem e nel database
        
        Args:
            awb: Numero tracking BRT
            label_b64: Base64 encoded PDF label
            order_id: Order ID
            carrier_api_id: Carrier API ID
            
        Returns:
            Dict con metadati documento salvato
        """
        try:
            # Cleanup documenti esistenti
            self._cleanup_old_documents(order_id)
            
            # Decodifica base64
            try:
                content_bytes = base64.b64decode(label_b64)
            except Exception as e:
                logger.error(f"Error decoding BRT label base64: {str(e)}")
                return {}
            
            # Genero file path con struttura anno/mese
            now = datetime.now()
            year = now.year
            month = now.month
            
            # Creazione directory: /media/shipments/{year}/{month}/{id_order}/
            base_dir = Path("media") / "shipments" / str(year) / str(month).zfill(2) / str(order_id)
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Genero nome file con AWB incluso
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"label_{awb}_{timestamp}.pdf"
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
                type_code="label",
                file_path=str(file_path),
                mime_type="application/pdf",
                sha256_hash=sha256_hash,
                size_bytes=file_size,
                created_at=now,
                expires_at=now + timedelta(days=365)  # 1 year TTL
            )
            
            # Aggiungo a sessione e salvo
            self.order_repository.session.add(document)
            self.order_repository.session.commit()
            
            logger.info(f"Saved BRT document label for AWB {awb}: {file_path}")
            
            return {
                "type_code": "label",
                "file_path": str(file_path),
                "size_bytes": file_size,
                "sha256_hash": sha256_hash,
                "order_id": order_id,
                "carrier_api_id": carrier_api_id
            }
            
        except Exception as e:
            logger.error(f"Error saving BRT document for AWB {awb}: {str(e)}")
            raise
    
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
            document_repo = ShipmentDocumentRepository(self.order_repository.session)
            existing_documents = document_repo.get_by_order_id(order_id)
            
            if not existing_documents:
                return
            
            # Raggruppa documenti per cartella per eliminare una volta sola
            folders_to_delete = set()
            
            for doc in existing_documents:
                if doc.file_path:
                    try:
                        # Estrai la cartella dell'ordine dal file_path
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
            awb: Air Waybill number o tracking number BRT
            
        Returns:
            Percorso del file PDF o None se non trovato
        """
        try:
            from src.repository.shipment_document_repository import ShipmentDocumentRepository
            
            # Cerca il documento per AWB
            document_repo = ShipmentDocumentRepository(self.order_repository.session)
            documents = document_repo.get_by_awb(awb)
            
            if not documents:
                logger.warning(f"Nessun documento trovato per AWB: {awb}")
                return None
            
            # Cerca il documento di tipo "label"
            for doc in documents:
                if doc.type_code in ["label", "LABEL"] and doc.file_path:
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

